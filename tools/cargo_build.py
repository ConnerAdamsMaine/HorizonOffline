#!/usr/bin/env python3
"""Resource-aware Cargo builds for Horizon (docs/build-profiles.md).

The workspace is large: a cold `horizon-client` build runs hundreds of rustc units and then links
a 100 MB binary. Letting Cargo start one rustc per logical CPU ignores RAM and is the usual
way a laptop swaps or the linker is killed on this project. This wrapper chooses a job count from
the machine's memory and the profile's per-unit cost, then runs the same `cargo build` a developer
would run, with `--locked`.

    python3 tools/cargo_build.py --profile fast              # quick optimized game + horizon-ctl
    python3 tools/cargo_build.py --profile release           # production profile (ThinLTO, 4 CGUs)
    python3 tools/cargo_build.py --profile release-max --jobs 4   # opt-in fat LTO
    python3 tools/cargo_build.py --profile bench --dry-run   # what it would run and why
    python3 tools/cargo_build.py --profile dev --no-default-features

This script does not change Cargo.toml. Set `CARGO_BUILD_JOBS` (or --jobs) to override the calculated
number, and `CARGO_BUILD_JOBS` is also respected by CI. The estimate is deliberately conservative:
linkers are single processes whose peak can exceed one rustc; `release-max` therefore reserves more.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Rough peak resident memory of one concurrent rustc/linker unit, in MiB. Measured worst cases on
# this workspace are larger than a small crate; these leave headroom for the linker and the OS.
PER_JOB_MB = {
    "dev": 900,
    "fast": 1_800,
    "release": 2_200,
    "bench": 2_400,
    "release-max": 4_000,
}
# Never leave the machine without this share of RAM for the OS, the editor and the page cache.
RESERVE = 0.25
# The game binary and its control tool; the benchmark suite builds the game only.
PACKAGES = ["-p", "horizon-client", "-p", "horizon-client-lib", "--bin", "horizon-client", "--bin", "horizon-ctl"]


class BuildError(Exception):
    pass


def total_memory_mb() -> int | None:
    """Physical memory in MiB, or None when the OS won't say.

    Always the installed physical RAM: the page file is not usable capacity for a compiler and must
    never raise the job count. Use available_memory_mb() for what other processes have left.
    """
    if sys.platform == "win32":
        import ctypes

        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.dwLength = ctypes.sizeof(status)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None
        return int(status.ullTotalPhys // (1024 * 1024))
    if sys.platform == "darwin":
        try:
            out = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, check=True)
            return int(out.stdout.strip()) // (1024 * 1024)
        except (OSError, ValueError, subprocess.CalledProcessError):
            return None
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) // 1024
    except (OSError, ValueError):
        return None
    return None


def available_memory_mb() -> int | None:
    """Free physical memory in MiB, or None. A second build, a game or the editor already running
    must reduce the job count instead of pushing the machine into the page file."""
    if sys.platform == "win32":
        import ctypes

        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.dwLength = ctypes.sizeof(status)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None
        return int(status.ullAvailPhys // (1024 * 1024))
    try:
        import psutil  # optional; the wrapper works without it
        return int(psutil.virtual_memory().available / 2 ** 20)
    except (ImportError, OSError):
        pass
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) // 1024
    except (OSError, ValueError):
        return None
    return None


def default_jobs(cores: int, memory_mb: int | None, profile: str,
                 available_mb: int | None = None) -> int:
    """How many compiler/linker units to run at once. One at least, never more than `cores`.

    `available_mb` is what the machine can spare now; without it the estimate uses the installed
    total, which is only correct when nothing else is running.
    """
    cores = max(1, int(cores))
    if memory_mb is None:
        # Unknown memory: one per core is Cargo's own default, but cap it for the expensive profiles.
        return cores if profile in {"dev", "fast"} else max(1, min(cores, 4))
    per_job = PER_JOB_MB.get(profile, 2_200)
    usable = min(memory_mb, available_mb if available_mb is not None else memory_mb)
    usable *= (1.0 - RESERVE)
    return max(1, min(cores, int(usable // per_job)))


def build_env(profile: str, jobs: int, base: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ if base is None else base)
    env["CARGO_BUILD_JOBS"] = str(jobs)
    if profile in {"fast", "dev"}:
        env.setdefault("CARGO_INCREMENTAL", "1")
    else:
        # Incremental artifacts are not reproducible and make a cold release build slower.
        env["CARGO_INCREMENTAL"] = "0"
    return env


def build_command(profile: str, extra: list[str], jobs: int, target: str | None = None) -> list[str]:
    command = [shutil.which("cargo") or "cargo", "build", "--locked", "--profile", profile, "--jobs", str(jobs)]
    if target:
        command += ["--target", target]
    command += PACKAGES
    command += extra
    return command


def check_profile(profile: str) -> str:
    if profile not in PER_JOB_MB:
        raise BuildError(f"unknown profile {profile!r}: {', '.join(PER_JOB_MB)}")
    return profile


def describe(profile: str, jobs: int, memory_mb: int | None, cores: int,
             available_mb: int | None = None) -> str:
    memory = f"{memory_mb} MiB" if memory_mb is not None else "unknown"
    free = f" ({available_mb} MiB free)" if available_mb is not None else ""
    return (f"profile {profile}: {jobs} job(s) on {cores} logical CPU(s), {memory} RAM{free}; "
            f"estimated peak compile memory about {jobs * PER_JOB_MB[profile]} MiB")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--profile", default="fast", choices=sorted(PER_JOB_MB))
    parser.add_argument("--jobs", type=int, help="override the calculated concurrency")
    parser.add_argument("--mem-per-job", type=int, help="override the profile's MiB estimate")
    parser.add_argument("--target", help="cross-compilation target")
    parser.add_argument("--no-default-features", action="store_true", help="the server feature set")
    parser.add_argument("--dry-run", action="store_true", help="print the command and resource estimate")
    parser.add_argument("--no-lock", action="store_true",
                        help="do not serialise with another wrapper build on this checkout")
    parser.add_argument("extra", nargs=argparse.REMAINDER, help="arguments after -- go to cargo build")
    args = parser.parse_args(argv)

    try:
        profile = check_profile(args.profile)
        cores = os.cpu_count() or 1
        memory = total_memory_mb()
        available = available_memory_mb()
        if args.mem_per_job:
            PER_JOB_MB[profile] = args.mem_per_job
        jobs = args.jobs or default_jobs(cores, memory, profile, available)
        if jobs < 1:
            raise BuildError("jobs must be at least 1")
        extra = [a for a in args.extra if a != "--"]
        if args.no_default_features:
            extra.append("--no-default-features")
        command = build_command(profile, extra, jobs, args.target)
        env = build_env(profile, jobs)
        print(describe(profile, jobs, memory, cores, available), file=sys.stderr)
        print(" ".join(command), file=sys.stderr)
        if args.dry_run:
            return 0
        lock = None
        if not args.no_lock:
            # One wrapper build per checkout: two concurrent 12-job builds on one machine is exactly
            # the resource exhaustion this wrapper exists to prevent.
            try:
                from . import file_lock
            except ImportError:
                import file_lock
            (ROOT / ".local").mkdir(exist_ok=True)
            lock = (ROOT / ".local" / "cargo-build.lock").open("a+")
            print("waiting for the build lock (.local/cargo-build.lock) ...", file=sys.stderr)
            file_lock.lock(lock, wait=True)
        try:
            return subprocess.call(command, cwd=ROOT, env=env)
        finally:
            if lock is not None:
                lock.close()
    except BuildError as error:
        print(f"cargo_build: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
