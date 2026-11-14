#!/usr/bin/env python3
"""Automated gameplay benchmark suite for Horizon (docs/benchmark-suite.md).

`tools/perf_bench.py` measures startup, chunk loads and short scripted flights. This tool measures
what those flights do not: a live player walking, mining, crafting, fighting, and running redstone
and entity-heavy worlds, with per-scenario correctness checks, simulation tick timing, memory and
CPU sampling, and a machine-readable report that can be compared across revisions.

    python3 tools/gameplay_bench.py --build target/bench --label main
    python3 tools/gameplay_bench.py --build target/bench --smoke
    python3 tools/gameplay_bench.py --compare before.json after.json
    python3 tools/gameplay_bench.py --list

Every run:
  * starts one game from a fresh scratch game folder (never your saves or options) with audio off;
  * creates a creative world from a fixed seed, then drives it over `horizon-ctl`'s control protocol;
  * resets the game's frame statistics, performs the scenario, then measures a stationary hold so
    the frame figures are not polluted by control polling;
  * records raw samples, not only averages: tick rate, tick time, FPS, 1% and 0.1% lows, frame-time
    percentiles, RSS, CPU time, thread count, and scenario-specific counts;
  * asserts that the workload actually happened (block states changed, items were crafted, mobs took
    damage, the piston moved, chunks were generated). A failed assertion makes the report invalid.

The report is `benchmarks/gameplay/<label>-<stamp>.json` (schema: `horizon-benchmark-suite` in
`crates/horizon-bench/src/suite.rs`). `horizon-bench validate|compare` reads the same file.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import math
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

try:
    from . import lab
    from . import perf_bench as pb
except ImportError:
    import lab
    import perf_bench as pb

ROOT = lab.ROOT
WORK = ROOT / ".local/gameplay-bench"
SEED = 1234
WORLD = "GameplayBench"
SUITE_FORMAT, SUITE_VERSION = "horizon-benchmark-suite", 2
# Five repeats by default: with three the Student-t interval is so wide that a 20% regression is
# often "uncertain". `--repeats` overrides it, and a comparison says so when either side has fewer.
DEFAULT_REPEATS = 5
SCENARIOS = ("idle", "walk", "explore", "mine_place", "crafting", "combat", "redstone", "entities",
             "world_ops", "mixed")
# Opt-in, never in a default run: long soaks, scaling matrices and the instrumentation self-check.
EXTRA_SCENARIOS = ("memory_soak", "overhead", "render")
SMOKE_SCENARIOS = ("idle", "mine_place", "redstone", "world_ops")
# When set, add_frames keeps the per-frame streams for --raw-frames instead of dropping them.
RAW_FRAMES = None
# Platform where the controlled scenarios run: high above the spawn, so terrain cannot interfere.
PLATFORM_Y = 200


# --- statistics and comparison ----------------------------------------------------------------

def percentile(values, p):
    values = sorted(values)
    if not values:
        return None
    return values[min(len(values), max(1, math.ceil(len(values) * p))) - 1]


def summary(values):
    """Mean, sample standard deviation and the 95% confidence half-width (Student's t).

    Extra fields (`median`, `cv_pct`, `ci95_pct`, `iqr`) describe the same sample without deleting
    anything. `horizon_bench::suite::compare` reads only `n`, `mean` and `ci95`.
    """
    values = [v for v in values if v is not None and math.isfinite(v)]
    n = len(values)
    if not n:
        return None
    mean = sum(values) / n
    ordered = sorted(values)
    median = percentile(ordered, 0.5)
    stdev = ci95 = cv = None
    if n > 1:
        stdev = math.sqrt(sum((v - mean) ** 2 for v in values) / (n - 1))
        ci95 = (pb.T95[n - 2] if n - 1 <= len(pb.T95) else 1.96) * stdev / math.sqrt(n)
        cv = stdev / abs(mean) * 100 if mean else None
    return {"n": n, "mean": pb.rnd(mean), "median": pb.rnd(median),
            "stdev": None if stdev is None else pb.rnd(stdev),
            "min": pb.rnd(ordered[0]), "max": pb.rnd(ordered[-1]),
            "ci95": None if ci95 is None else pb.rnd(ci95),
            "ci95_pct": None if ci95 is None or not mean else pb.rnd(abs(ci95 / mean) * 100),
            "cv_pct": None if cv is None else pb.rnd(cv),
            "iqr": pb.rnd(percentile(ordered, 0.75) - percentile(ordered, 0.25))}


def outliers(values):
    """Repeat values outside Tukey's 1.5x interquartile fences, reported in place.

    The samples are never dropped: a slow repeat is evidence of a contaminated or bimodal run, not
    a value to hide. With fewer than four values the fences are not meaningful and none is returned.
    """
    values = [v for v in values if v is not None and math.isfinite(v)]
    if len(values) < 4:
        return []
    ordered = sorted(values)
    q1, q3 = percentile(ordered, 0.25), percentile(ordered, 0.75)
    spread = q3 - q1
    low, high = q1 - 1.5 * spread, q3 + 1.5 * spread
    return [{"index": i, "value": pb.rnd(v),
             "side": "high" if v > high else "low"}
            for i, v in enumerate(values) if v < low or v > high]


def statistics_of(values):
    """The report's per-metric statistics: the summary plus outliers and their method."""
    base = summary(values)
    if base is None:
        return None
    found = outliers(values)
    base["outliers"] = found
    base["outlier_count"] = len(found)
    base["outlier_method"] = "tukey-1.5-iqr"
    return base


def direction(metric):
    """`higher` for throughput figures, `lower` for times, memory and counts."""
    return "higher" if metric.endswith(("fps", "tps", "_per_s", "_throughput")) else "lower"


def compare_suites(before, after, threshold=5.0, require_significance=False):
    """The same rule as `horizon_bench::suite::compare`.

    A metric is a *confirmed* regression only when it is worse by more than the threshold and the
    difference clears the combined 95% interval. A worse change that is within the noise, or that
    cannot be judged because either side has fewer than two repeats, is reported as `uncertain` and
    never as a regression; an unchanged metric is `neutral`. With `require_significance` an
    uncertain change is still not a regression (the caller opts into the strict reading).
    """
    out = []
    old_by_name = {s["name"]: s for s in before.get("scenarios", [])}
    for new in after.get("scenarios", []):
        old = old_by_name.get(new["name"])
        if not old:
            continue
        for metric, old_values in old.get("samples", {}).items():
            new_values = new.get("samples", {}).get(metric)
            if new_values is None:
                continue
            a, b = summary(old_values), summary(new_values)
            if not a or not b:
                continue
            # A zero baseline has no meaningful percentage; call it unchanged rather than infinite.
            change = 0.0 if a["mean"] == 0 else (b["mean"] - a["mean"]) / abs(a["mean"]) * 100
            worse = change < 0 if direction(metric) == "higher" else change > 0
            significant = None
            noise = None
            if a["n"] > 1 and b["n"] > 1 and a["ci95"] is not None and b["ci95"] is not None:
                se = math.hypot(a["ci95"] / 1.96, b["ci95"] / 1.96)
                significant = abs(b["mean"] - a["mean"]) > 1.96 * se
                noise = pb.rnd((1.96 * se) / abs(a["mean"]) * 100) if a["mean"] else None
            over = abs(change) > threshold
            if not over:
                verdict = "neutral"
            elif significant is None or significant is False:
                verdict = "uncertain"
            elif worse:
                verdict = "regression"
            else:
                verdict = "improvement"
            # Only a change that clears the noise is a regression: an uncertain one is reported
            # in its own bucket so a background process cannot fail a performance job.
            regression = verdict == "regression"
            out.append({"scenario": new["name"], "metric": metric, "before": a, "after": b,
                        "change_pct": pb.rnd(change), "noise_pct": noise, "direction": direction(metric),
                        "significant": significant, "verdict": verdict, "regression": regression})
    return out


# --- process sampling -------------------------------------------------------------------------

def _windows_cpu_seconds(pid):
    import ctypes
    from ctypes import wintypes

    class FileTime(ctypes.Structure):
        _fields_ = [("low", wintypes.DWORD), ("high", wintypes.DWORD)]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    handle = kernel32.OpenProcess(0x1000, False, pid)
    if not handle:
        return None
    try:
        creation, exit_, kernel, user = FileTime(), FileTime(), FileTime(), FileTime()
        if not kernel32.GetProcessTimes(handle, ctypes.byref(creation), ctypes.byref(exit_),
                                        ctypes.byref(kernel), ctypes.byref(user)):
            return None
        ticks = ((kernel.high << 32) | kernel.low) + ((user.high << 32) | user.low)
        return ticks / 10_000_000.0
    finally:
        kernel32.CloseHandle(handle)


def private_memory(pid):
    """(private/commit MiB, virtual MiB) where the OS distinguishes them, else None.

    Working set (resident), private commit and virtual size are three different numbers; the report
    keeps them apart so a working-set plateau cannot hide a growing commit charge.
    """
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class VmCountersEx(ctypes.Structure):
            _fields_ = [("PeakVirtualSize", ctypes.c_size_t), ("VirtualSize", ctypes.c_size_t),
                        ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
                        ("PrivateUsage", ctypes.c_size_t)]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        handle = kernel32.OpenProcess(0x0400, False, pid)  # PROCESS_QUERY_INFORMATION
        if not handle:
            return None
        try:
            counters = VmCountersEx()
            returned = ctypes.c_ulong()
            # ProcessVmCounters = 3.
            status = ctypes.WinDLL("ntdll").NtQueryInformationProcess(
                handle, 3, ctypes.byref(counters), ctypes.sizeof(counters), ctypes.byref(returned))
            if status != 0:
                return None
            return counters.PrivateUsage / 2 ** 20, counters.VirtualSize / 2 ** 20
        finally:
            kernel32.CloseHandle(handle)
    try:
        status = Path(f"/proc/{pid}/status").read_text().splitlines()
    except OSError:
        return None
    values = {}
    for line in status:
        key, _, rest = line.partition(":")
        if key in ("VmRSS", "VmData", "VmSize"):
            values[key] = int(rest.split()[0]) / 1024.0
    private = values.get("VmData")
    virtual = values.get("VmSize")
    return (None if private is None else private, None if virtual is None else virtual)


def cpu_seconds(pid):
    if sys.platform == "win32":
        return _windows_cpu_seconds(pid)
    try:
        out = subprocess.run(["ps", "-o", "time=", "-p", str(pid)], capture_output=True, text=True)
        text = out.stdout.strip()
        if not text:
            return None
        return pb.cpu_seconds(text) if hasattr(pb, "cpu_seconds") else _parse_ps_time(text)
    except OSError:
        return None


def _parse_ps_time(text):
    days, _, rest = text.rpartition("-")
    seconds = 0.0
    for part in rest.split(":"):
        seconds = seconds * 60 + float(part)
    return seconds + (float(days) * 86400 if days else 0.0)


def thread_count(pid):
    try:
        import psutil
        return psutil.Process(pid).num_threads()
    except (ImportError, OSError):
        pass
    if sys.platform == "win32":
        # No cheap per-process thread count without psutil; spawning wmic every sample would
        # perturb the benchmark more than the number is worth.
        return None
    try:
        out = subprocess.run(["ps", "-o", "nlwp=", "-p", str(pid)], capture_output=True, text=True)
        return int(out.stdout.strip()) if out.stdout.strip() else None
    except (OSError, ValueError):
        return None


class ProcessSampler(threading.Thread):
    """RSS, cumulative CPU time and thread count every 0.5 s, from outside the game.

    `pause()`/`resume()` let a scenario measure its own instrumentation cost: a sampler that
    materially changed the workload would make its readings worthless.
    """

    def __init__(self, pid, interval=0.5):
        super().__init__(daemon=True)
        self.pid, self.samples, self.stop = pid, [], threading.Event()
        self.interval = max(0.05, interval)
        self.paused = threading.Event()
        self.poll_count = 0

    def run(self):
        while not self.stop.is_set():
            if not self.paused.is_set():
                self.poll_count += 1
                rss = pb.rss_bytes(self.pid)
                cpu = cpu_seconds(self.pid)
                threads = thread_count(self.pid)
                memory = private_memory(self.pid)
                if rss is not None:
                    self.samples.append((time.time(), rss, cpu, threads, memory))
            self.stop.wait(self.interval)

    def pause(self):
        self.paused.set()

    def resume(self):
        self.paused.clear()

    def window(self, begin, end):
        rows = [(t, rss, cpu, threads, memory) for t, rss, cpu, threads, memory in self.samples
                if begin <= t <= end]
        if not rows:
            return {}
        rss_mb = [rss / 2 ** 20 for _, rss, _, _, _ in rows]
        out = {"process.rss_peak_mb": max(rss_mb), "process.rss_steady_mb": percentile(rss_mb, 0.5),
               "process.rss_samples": len(rows)}
        cpus = [cpu for _, _, cpu, _, _ in rows if cpu is not None]
        if len(cpus) > 1 and end > begin:
            out["process.cpu_cores_used"] = (cpus[-1] - cpus[0]) / (end - begin)
            out["process.cpu_seconds"] = cpus[-1] - cpus[0]
        threads = [n for _, _, _, n, _ in rows if n is not None]
        if threads:
            out["process.threads_peak"] = max(threads)
        private = [m[0] for _, _, _, _, m in rows if m and m[0] is not None]
        virtual = [m[1] for _, _, _, _, m in rows if m and m[1] is not None]
        if private:
            out["process.private_peak_mb"] = max(private)
            out["process.private_steady_mb"] = percentile(private, 0.5)
        if virtual:
            out["process.virtual_peak_mb"] = max(virtual)
            out["process.virtual_steady_mb"] = percentile(virtual, 0.5)
        return out


def slope_mb_per_min(samples):
    """Least-squares slope of (t, RSS MB), for leak-ish trends over a long soak."""
    if len(samples) < 3:
        return None
    t0 = samples[0][0]
    xs = [(t - t0) / 60.0 for t, _ in samples]
    ys = [rss / 2 ** 20 for _, rss in samples]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    denom = sum((x - mx) ** 2 for x in xs)
    return None if denom == 0 else sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom


def available_mb():
    """Free physical memory, or None: a run that starts with the page file already in use is not
    comparable, and Windows' "available" excludes standby, which is what a benchmark needs."""
    try:
        import psutil
        return psutil.virtual_memory().available / 2 ** 20
    except (ImportError, OSError):
        pass
    try:
        if sys.platform == "win32":
            import ctypes

            class MemoryStatus(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            status = MemoryStatus()
            status.dwLength = ctypes.sizeof(status)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
            return status.ullAvailPhys / 2 ** 20
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) / 1024
    except (OSError, ValueError, AttributeError):
        return None
    return None


def _windows_cpu_percent(interval=0.1):
    """Share of all CPUs busy over a short sample, without psutil (Task Manager's figure)."""
    import ctypes
    from ctypes import wintypes

    class FileTime(ctypes.Structure):
        _fields_ = [("low", wintypes.DWORD), ("high", wintypes.DWORD)]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    def read():
        idle, kernel, user = FileTime(), FileTime(), FileTime()
        if not kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
            return None
        value = lambda t: (t.high << 32) | t.low
        return (value(idle), value(kernel) + value(user))

    first = read()
    time.sleep(max(0.02, interval))
    second = read()
    if not first or not second:
        return None
    idle = second[0] - first[0]
    total = second[1] - first[1]
    return None if total <= 0 else max(0.0, min(100.0, (total - idle) / total * 100.0))


def load_snapshot():
    """The machine's load before/after a scenario, for contamination detection.

    Windows has no load average; the percentage of all CPUs busy in a short sample is the closest
    equivalent and is taken outside the measured window. `None` where neither is available.
    """
    try:
        import psutil
    except ImportError:
        psutil = None
    cpu = None
    if psutil is not None:
        try:
            cpu = psutil.cpu_percent(interval=0.05)
        except (OSError, AttributeError):
            cpu = None
    elif sys.platform == "win32":
        try:
            cpu = _windows_cpu_percent(0.1)
        except (OSError, AttributeError):
            cpu = None
    snapshot = {"load_1m": pb.load_average() if hasattr(pb, "load_average") else None,
                "available_mb": available_mb()}
    if cpu is not None:
        snapshot["cpu_percent"] = cpu
    if psutil is not None:
        try:
            snapshot["swap_used_mb"] = psutil.swap_memory().used / 2 ** 20
        except (OSError, AttributeError):
            pass
    return snapshot


# A scenario is not comparison-grade when the machine was busy or short of memory while it ran. These
# are reported, not silently applied: CI may still accept the correctness result of a contaminated
# run, while a baseline must be clean.
CONTAMINATION_CPU_PCT = 15.0
CONTAMINATION_FREE_MB = 1024.0
CONTAMINATION_AVAILABLE_FRACTION = 0.05


def contamination(run, machine_mb, before, after, args, frames_drawn, expected_frames_s=0.0):
    """Reasons this repeat is not a clean measurement; empty when it is."""
    reasons = []
    if not frames_drawn:
        reasons.append("no frames drawn")
    # The measured game is itself most of the CPU a fast scene uses: subtract the process's own
    # cores (sampled over the scenario) from the system share, so only *other* work counts.
    game_cores = (run.get("samples", {}).get("process.cpu_cores_used") or [None])[-1]
    cores = os.cpu_count() or 1
    own_pct = (game_cores / cores * 100.0) if game_cores is not None else 0.0
    limit = getattr(args, "contamination_cpu_pct", CONTAMINATION_CPU_PCT)
    free_limit = getattr(args, "contamination_free_mb", CONTAMINATION_FREE_MB)
    for label, snap in (("before", before), ("after", after)):
        busy = snap.get("cpu_percent")
        if busy is not None:
            other = max(0.0, busy - own_pct)
            if other > limit:
                reasons.append(f"machine {other:.1f}% busy in other work {label} the scenario "
                               f"(system {busy:.1f}%, game {own_pct:.1f}%, limit {limit:.0f}%)")
        free = snap.get("available_mb")
        if free is not None and machine_mb:
            if free < free_limit or free < machine_mb * CONTAMINATION_AVAILABLE_FRACTION:
                reasons.append(f"only {free:.0f} MiB free {label} the scenario")
    wall = run.get("samples", {}).get("run.wall_s", [0])[-1] if run.get("samples") else 0.0
    if expected_frames_s and frames_drawn and wall:
        # A hold that lost most of its frames cannot be compared with one that did not.
        if frames_drawn / wall < expected_frames_s * 0.5:
            reasons.append(f"only {frames_drawn / wall:.1f} frames/s in {wall:.1f} s")
    tps = run.get("samples", {}).get("tick.tps", [None])[-1] if run.get("samples") else None
    if tps is not None and tps < 15.0:
        reasons.append(f"tick rate fell to {tps:.1f} tps")
    return reasons


# --- game control ------------------------------------------------------------------------------

class Game:
    def __init__(self, control, proc, game_dir):
        self.control, self.proc, self.dir = control, proc, game_dir

    def run(self, line, timeout=600):
        return self.control(line, timeout=timeout)

    def status(self):
        return self.run("status", timeout=30)

    def command(self, text):
        return self.run("command " + text)

    def wait(self, ticks):
        return self.run(f"wait {ticks}")

    def position(self):
        player = self.status().get("player")
        return player["position"] if player else None

    def block(self, pos):
        return self.run(f"block {pos[0]} {pos[1]} {pos[2]}").get("state", "")

    def check(self, scenario, name, ok, expected, actual):
        scenario["checks"].append({"name": name, "expected": str(expected),
                                   "actual": str(actual), "passed": bool(ok)})
        return bool(ok)

    def sample(self, scenario, metric, value):
        if value is None:
            return
        if isinstance(value, bool):
            value = float(value)
        try:
            value = float(value)
        except (TypeError, ValueError):
            return
        if math.isfinite(value):
            scenario["samples"].setdefault(metric, []).append(pb.rnd(value))


def teleport(game, pos, pitch=15.0, distance=16, timeout=300, min_chunks=None, hold=False):
    x, y, z = pos
    game.run(f"tp {x:.3f} {y:.3f} {z:.3f}")
    game.run(f"look 0 {pitch:.3f}")
    if hold:
        # A teleport into the air would fall out of the `near` window before the load settles.
        game.run(f"fly {x:.3f} {y:.3f} {z:.3f} {x:.3f} {y:.3f} {z:.3f} 0.1 {pitch:.3f}")
    near = lambda p: sum((a - b) ** 2 for a, b in zip(p, pos)) < 9.0
    required = pb.view_chunks(distance) if min_chunks is None else min_chunks
    pb.wait_loaded(game.control, near, timeout, required)


def hold(game, scenario, pos, pitch, seconds, phase, sampler=None, warmup=0.0, cooldown=0.0):
    """A stationary flight with explicit warm-up, measurement and cooldown phases.

    The warm-up is the same camera and the same world for `warmup` seconds; its frames are kept with
    the `warmup` phase name but its metrics are not pooled into the measurement. The cooldown lets
    the frame limiter and the allocator settle before the next scenario without polling the game.
    """
    x, y, z = pos
    if warmup > 0:
        begin = time.time()
        reply = game.run(f"fly {x:.3f} {y:.3f} {z:.3f} {x:.3f} {y:.3f} {z:.3f} {warmup:.3f} {pitch:.3f} raw")
        add_frames(game, scenario, reply, "warmup", begin, time.time(), record=False)
    before = game.status()
    begin = time.time()
    reply = game.run(f"fly {x:.3f} {y:.3f} {z:.3f} {x:.3f} {y:.3f} {z:.3f} {seconds:.3f} {pitch:.3f} raw")
    end = time.time()
    after = game.status()
    add_frames(game, scenario, reply, phase, begin, end)
    ticks = max(0, int(after.get("ticks", 0)) - int(before.get("ticks", 0)))
    wall = max(end - begin, 1e-9)
    game.sample(scenario, "tick.tps", ticks / wall)
    game.sample(scenario, "tick.mspt", reply.get("tick_ms"))
    game.sample(scenario, "tick.mspt_max", reply.get("tick_ms_max"))
    frames = reply.get("frames", 0) or 0
    tick_phase = (reply.get("phases_avg_ms") or {}).get("tick")
    if ticks and tick_phase is not None:
        game.sample(scenario, "tick.client_ms", tick_phase * frames / ticks)
    # Per-subsystem CPU time inside the frame: the renderer's own phase spans, not wall time.
    for name, value in (reply.get("phases_avg_ms") or {}).items():
        if value is not None:
            game.sample(scenario, f"cpu.phase_{name}_ms", value)
    for name, value in (reply.get("slow_phases_avg_ms") or {}).items():
        if value is not None:
            game.sample(scenario, f"cpu.slow_phase_{name}_ms", value)
    if sampler:
        for key, value in sampler.window(begin, end).items():
            if key.startswith("process."):
                game.sample(scenario, key, value)
    if cooldown > 0:
        time.sleep(cooldown)
    return reply


def add_frames(game, scenario, reply, phase, begin, end, record=True):
    series = lambda key: reply.get(key, []) or []
    entry = pb.frames(phase, 0, series("frame_ms"), series("cpu_ms"), series("gpu_ms"))
    if entry:
        scenario.setdefault("frames", []).append(entry)
        if RAW_FRAMES is not None:
            RAW_FRAMES.append({"scenario": scenario.get("name"), "phase": phase,
                               "frame_ms": list(series("frame_ms")),
                               "cpu_ms": list(series("cpu_ms")), "gpu_ms": list(series("gpu_ms"))})
        if not record:
            return entry
        game.sample(scenario, "render.avg_fps", entry["avg_fps"])
        game.sample(scenario, "render.low_1pct_fps", entry["low_1pct_fps"])
        game.sample(scenario, "render.low_01pct_fps", entry["low_01pct_fps"])
        game.sample(scenario, "render.p50_ms", entry["p50_ms"])
        game.sample(scenario, "render.p95_ms", entry["p95_ms"])
        game.sample(scenario, "render.p99_ms", entry["p99_ms"])
        game.sample(scenario, "render.p999_ms", entry["p999_ms"])
        game.sample(scenario, "render.max_ms", entry["max_ms"])
        game.sample(scenario, "render.frames", entry["frames"])
        for key in ("cpu_p50_ms", "cpu_p99_ms", "gpu_p50_ms", "gpu_p99_ms", "gpu_wait_p50_ms"):
            if entry.get(key) is not None:
                game.sample(scenario, "render." + key, entry[key])
    if record and end > begin:
        game.sample(scenario, "run.wall_s", end - begin)
    return entry


def platform_at(game, origin, distance=16, timeout=300, min_chunks=None):
    """A stone floor above the spawn plus a clear air box, then the player on it."""
    x, y, z = origin
    game.command(f"fill {x - 8} {y - 1} {z - 8} {x + 8} {y - 1} {z + 8} stone")
    game.command(f"fill {x - 8} {y} {z - 8} {x + 8} {y + 4} {z + 8} air")
    if min_chunks == 0:
        # A setup that will keep streaming (the soak's turnover ends): arrive and stand on the
        # floor; waiting for the view to go quiet there is the work the scenario measures.
        game.run(f"tp {x + 0.5:.3f} {y:.3f} {z + 0.5:.3f}")
        game.run("look 0 15")
        game.wait(20)
    else:
        teleport(game, [x + 0.5, y, z + 0.5], 15.0, distance, timeout, min_chunks=min_chunks)
    # The floor must really be there before a scenario switches to survival.
    if "stone" not in game.block([x, y - 1, z]):
        game.command(f"fill {x - 8} {y - 1} {z - 8} {x + 8} {y - 1} {z + 8} stone")
        if min_chunks == 0:
            game.run(f"tp {x + 0.5:.3f} {y:.3f} {z + 0.5:.3f}")
            game.wait(20)
        else:
            teleport(game, [x + 0.5, y, z + 0.5], 15.0, distance, timeout, min_chunks=min_chunks)


def new_scenario(name, category, seconds, repeats=1):
    return {"name": name, "category": category, "seconds": seconds, "repeats": repeats,
            "samples": {}, "checks": [], "frames": [], "notes": [], "runs": [],
            "contamination": []}


def hold_phases(args):
    """(warm-up seconds, cooldown seconds) around every measured hold."""
    return max(0.0, getattr(args, "warmup_seconds", 2.0)), max(0.0, getattr(args, "cooldown_seconds", 1.0))


def ensure_playing(game):
    """Leave a death or menu screen left by an earlier scenario; a run must start in the world."""
    screen = game.run("screen").get("screen")
    if screen == "dead":
        game.run("respawn", timeout=60)
        game.wait(5)
    elif screen not in (None, "playing", "none"):
        try:
            game.run("close")
        except RuntimeError:
            pass
    return game.run("screen").get("screen")


def give_until(game, item, count=1, tries=5):
    """`give` goes through the server thread; poll until the client sees it, rather than racing it."""
    name = item if ":" in item else f"minecraft:{item}"
    inventory = game.run("inventory")
    for _ in range(tries):
        game.run(f"give {item} {count}")
        game.wait(5)
        inventory = game.run("inventory")
        if inventory.get("counts", {}).get(name, 0) >= count:
            return inventory
    return inventory


def finish(scenario, notes=()):
    scenario["notes"].extend(notes)
    scenario["valid"] = (bool(scenario["checks"]) and all(c["passed"] for c in scenario["checks"])
                         and bool(scenario["samples"]))
    return scenario


def merge_repeats(merged, run, repeat):
    """Append one repeat's raw samples and frames; every failed check from a later repeat is kept."""
    for metric, values in run.get("samples", {}).items():
        merged["samples"].setdefault(metric, []).extend(values)
    for frame in run.get("frames", []):
        frame = dict(frame)
        frame["repeat"] = repeat
        merged["frames"].append(frame)
    if repeat == 0:
        merged["checks"] = list(run.get("checks", []))
        merged["notes"] = list(run.get("notes", []))
    else:
        for check in run.get("checks", []):
            if not check["passed"]:
                failed = dict(check)
                failed["name"] = f"repeat {repeat + 1}: {failed['name']}"
                merged["checks"].append(failed)
    return merged


# --- scenarios ---------------------------------------------------------------------------------

def scenario_idle(game, args, ctx):
    s = new_scenario("idle", "renderer", args.seconds)
    pos = game.position() or [0.0, 100.0, 0.0]
    view = [pos[0], pos[1] + 1.6, pos[2]]
    hold(game, s, view, 20.0, args.seconds, "idle", ctx["sampler"], ctx["warmup"], ctx["cooldown"])
    frames = sum(f["frames"] for f in s["frames"])
    ticks = s["samples"].get("tick.tps", [0])[-1] * args.seconds
    game.check(s, "frames drawn", frames > 10, "> 10", frames)
    game.check(s, "ticks advanced", ticks > 1, "> 1", round(ticks, 1))
    game.check(s, "tick rate plausible", s["samples"].get("tick.tps", [0])[-1] > 5, "> 5 tps",
               s["samples"].get("tick.tps", [0])[-1])
    return finish(s, ["stationary camera; the baseline every other scenario is compared with"])


def scenario_walk(game, args, ctx):
    s = new_scenario("walk", "gameplay", args.seconds)
    spawn = game.position() or [0.0, 100.0, 0.0]
    origin = [int(spawn[0]), PLATFORM_Y, int(spawn[2]) - 48]
    platform_at(game, origin, args.render_distance, args.timeout)
    start = [origin[0] + 0.5, origin[1] + 1.0, origin[2] - 6.5]
    teleport(game, start, 10.0, args.render_distance, args.timeout)
    game.run("look 0 10")
    start = game.position()
    begin = time.time()
    game.run("move forward 2 --sprint", timeout=60)
    elapsed = time.time() - begin
    end = game.position()
    distance = math.dist([start[0], start[2]], [end[0], end[2]]) if start and end else 0.0
    game.sample(s, "play.action_s", elapsed)
    game.sample(s, "play.distance_blocks", distance)
    game.sample(s, "play.walk_mps", distance / max(elapsed, 1e-9))
    s["notes"].append(f"walk start={start!r} end={end!r} distance={distance:.2f}")
    game.check(s, "player moved", distance > 3.0, "> 3 blocks", round(distance, 2))
    hold(game, s, [end[0], end[1] + 1.6, end[2]], 10.0, args.seconds, "after_walk", ctx["sampler"],
         ctx["warmup"], ctx["cooldown"])
    return finish(s, ["sprint for 2 s on a controlled stone platform"])


def scenario_explore(game, args, ctx):
    s = new_scenario("explore", "worldgen", args.explore_seconds)
    spawn = game.position() or [0.0, 100.0, 0.0]
    start = [spawn[0], max(spawn[1] + 40.0, 150.0), spawn[2]]
    # The flight itself is the load test; do not require the 80%-of-view threshold before it.
    teleport(game, start, 10.0, args.render_distance, args.timeout, min_chunks=0, hold=True)
    before = game.status()
    end = [start[0] + args.explore_blocks, start[1], start[2] + args.explore_blocks * 0.25]
    begin = time.time()
    reply = game.run(f"fly {start[0]:.3f} {start[1]:.3f} {start[2]:.3f} {end[0]:.3f} {end[1]:.3f} "
                     f"{end[2]:.3f} {args.explore_seconds:.3f} 10 raw", timeout=args.timeout)
    finish_at = time.time()
    after = game.status()
    add_frames(game, s, reply, "explore", begin, finish_at)
    generated = int(after.get("generated_chunks", 0)) - int(before.get("generated_chunks", 0))
    chunks = int(after.get("chunks", 0))
    game.sample(s, "world.generated_chunks", generated)
    game.sample(s, "world.resident_chunks", chunks)
    game.sample(s, "world.travel_blocks", math.dist(start, end))
    for key, value in ctx["sampler"].window(begin, finish_at).items():
        if key.startswith("process."):
            game.sample(s, key, value)
    game.check(s, "new terrain generated", generated > 0, "> 0 chunks", generated)
    game.check(s, "terrain resident", chunks > 0, "> 0 chunks", chunks)
    game.check(s, "frames drawn", len(s["frames"]) == 1 and s["frames"][0]["frames"] > 10,
               "> 10", s["frames"][0]["frames"] if s["frames"] else 0)
    return finish(s, [f"{args.explore_blocks} blocks of travel over fresh terrain"])


def scenario_mine_place(game, args, ctx):
    s = new_scenario("mine_place", "gameplay", args.seconds)
    spawn = game.position() or [0.0, 100.0, 0.0]
    origin = [int(spawn[0]) + 48, PLATFORM_Y, int(spawn[2]) + 48]
    platform_at(game, origin, args.render_distance, args.timeout)
    game.command(f"fill {origin[0] - 8} {origin[1]} {origin[2] - 8} {origin[0] + 8} {origin[1]} {origin[2] + 8} air")
    give_until(game, "stone", 64)
    game.run("select stone")
    placed = broken = 0
    begin = time.time()
    for i in range(8):
        x, z = origin[0] - 4 + i, origin[2] - 2
        y = origin[1]
        game.run(f"place {x} {y} {z} --item stone", timeout=60)
        state = game.block([x, y, z])
        if "stone" in state:
            placed += 1
        game.run(f"break {x} {y} {z}", timeout=60)
        if "air" in game.block([x, y, z]).lower():
            broken += 1
    elapsed = time.time() - begin
    game.sample(s, "play.action_s", elapsed)
    game.sample(s, "play.placed", placed)
    game.sample(s, "play.broken", broken)
    game.sample(s, "play.ops_per_s", (placed + broken) / max(elapsed, 1e-9))
    game.check(s, "blocks placed", placed >= 6, ">= 6", placed)
    game.check(s, "blocks broken", broken >= 6, ">= 6", broken)
    hold(game, s, [origin[0], origin[1] + 2.6, origin[2] - 6], 15.0, args.seconds, "after_mining",
         ctx["sampler"], ctx["warmup"], ctx["cooldown"])
    return finish(s, ["place and break stone on a controlled platform"])


def _item_name(stack):
    item = (stack or {}).get("item")
    return item.split(":")[-1] if isinstance(item, str) else ""


def scenario_crafting(game, args, ctx):
    s = new_scenario("crafting", "gameplay", args.seconds)
    spawn = game.position() or [0.0, 100.0, 0.0]
    origin = [int(spawn[0]) - 48, PLATFORM_Y, int(spawn[2]) + 48]
    platform_at(game, origin, args.render_distance, args.timeout)
    ensure_playing(game)
    # The creative inventory has no crafting grid: craft as a survival player, then restore.
    game.command("clear")
    game.wait(5)
    game.command("gamemode survival")
    game.wait(5)
    inventory = give_until(game, "oak_log", 4)
    ensure_playing(game)
    game.run("open-inventory", timeout=30)
    game.wait(2)
    slot = None
    for group in ("hotbar", "main"):
        for entry in inventory.get(group, []):
            if _item_name(entry) == "oak_log":
                slot = entry.get("slot")
                break
        if slot is not None:
            break
    if slot is None:
        s["notes"].append(f"inventory after give: {inventory!r}")
        game.check(s, "oak_log in inventory", False, "oak_log", "missing")
        game.run("close")
        return finish(s)
    game.run(f"click-slot {slot}", timeout=30)
    game.run("click-slot 100", timeout=30)
    screen = game.run("screen")
    output = next((slot for slot in screen.get("slots", []) if slot.get("slot") == 200), {})
    output_item = _item_name(output)
    s["notes"].append(f"crafted {output_item or 'nothing'} from the log in slot {slot}")
    game.check(s, "craft result", output_item == "oak_planks", "oak_planks", output_item or "empty")
    if output_item:
        # Shift-click the result: vanilla crafts the whole stack into the inventory.
        game.run("click-slot 200 shift", timeout=30)
    game.run("close")
    counts = game.run("inventory").get("counts", {})
    planks = counts.get("minecraft:oak_planks", counts.get("oak_planks", 0))
    game.sample(s, "play.oak_logs_given", 4)
    game.sample(s, "play.oak_planks", planks)
    game.check(s, "planks obtained", planks >= 1, ">= 1", planks)
    game.command("gamemode creative")
    hold(game, s, [origin[0], origin[1] + 2.6, origin[2] - 4], 20.0, args.seconds, "after_crafting",
         ctx["sampler"], ctx["warmup"], ctx["cooldown"])
    return finish(s, ["one oak log into the survival crafting grid and the result taken"])


def scenario_combat(game, args, ctx):
    s = new_scenario("combat", "entities", args.seconds)
    spawn = game.position() or [0.0, 100.0, 0.0]
    origin = [int(spawn[0]) + 48, PLATFORM_Y, int(spawn[2]) - 48]
    platform_at(game, origin, args.render_distance, args.timeout)
    x, y, z = origin[0] + 2, origin[1] + 1, origin[2]
    game.command(f"summon zombie {x} {y} {z} {{NoAI:1b,PersistenceRequired:1b,Silent:1b}}")
    game.wait(5)
    found = game.run("entities 8 zombie").get("entities", [])
    if not found:
        game.check(s, "zombie summoned", False, "1 zombie", "0")
        return finish(s)
    mob = found[0]
    before_health = float(mob.get("health", 20.0))
    game.run(f"look-at entity {mob['id']}", timeout=30)
    begin = time.time()
    hits = 0
    for _ in range(8):
        game.run(f"attack {mob['id']}", timeout=30)
        hits += 1
        game.wait(4)
        after = game.run("entities 8 zombie").get("entities", [])
        current = next((m for m in after if m.get("id") == mob["id"]), None)
        if current is None or float(current.get("health", 0)) < before_health:
            break
    elapsed = time.time() - begin
    after = game.run("entities 8 zombie").get("entities", [])
    current = next((m for m in after if m.get("id") == mob["id"]), None)
    after_health = 0.0 if current is None else float(current.get("health", 0))
    game.sample(s, "play.attacks", hits)
    game.sample(s, "play.action_s", elapsed)
    game.sample(s, "combat.health_before", before_health)
    game.sample(s, "combat.health_after", after_health)
    s["notes"].append(f"target {mob['id']}: health {before_health} -> {after_health}")
    game.check(s, "target took damage", after_health < before_health, f"< {before_health}", after_health)
    hold(game, s, [origin[0], origin[1] + 2.6, origin[2] - 6], 15.0, args.seconds, "after_combat",
         ctx["sampler"], ctx["warmup"], ctx["cooldown"])
    return finish(s, ["attack a summoned zombie until its health falls"])


def scenario_redstone(game, args, ctx):
    s = new_scenario("redstone", "simulation", args.seconds)
    spawn = game.position() or [0.0, 100.0, 0.0]
    origin = [int(spawn[0]) - 48, PLATFORM_Y, int(spawn[2]) - 48]
    platform_at(game, origin, args.render_distance, args.timeout)
    x, y, z = origin
    # Piston: powered from the west, extends east, retracts when the source is removed.
    # Everything sits on the floor at y - 1: a repeater needs a solid block below it.
    game.command(f"setblock {x} {y} {z} piston[facing=east]")
    game.command(f"setblock {x - 1} {y} {z} redstone_block")
    game.wait(20)
    extended = game.block([x + 1, y, z])
    game.command(f"setblock {x - 1} {y} {z} air")
    game.wait(20)
    retracted = game.block([x + 1, y, z])
    game.check(s, "piston extends", "piston_head" in extended or "moving_piston" in extended,
               "piston_head", extended.split("[")[0])
    game.check(s, "piston retracts", "air" in retracted, "air", retracted.split("[")[0])
    # Repeater drives a lamp after its delay; removing the source turns it off.
    rx, rz = x + 5, z
    # RepeaterBlock.FACING is its input side (the back of the arrow); the output is opposite.
    game.command(f"setblock {rx} {y} {rz} repeater[facing=east,delay=4]")
    game.command(f"setblock {rx - 1} {y} {rz} redstone_lamp")
    game.command(f"setblock {rx + 1} {y} {rz} redstone_block")
    game.wait(30)
    lit = game.block([rx - 1, y, rz])
    source_state = game.block([rx + 1, y, rz])
    repeater_state = game.block([rx, y, rz])
    game.command(f"setblock {rx + 1} {y} {rz} air")
    game.wait(30)
    unlit = game.block([rx - 1, y, rz])
    game.check(s, "repeater lights lamp", "lit=true" in lit, "lit=true", lit.split("[")[0])
    game.check(s, "lamp turns off", "lit=false" in unlit or "air" in unlit, "lit=false", unlit.split("[")[0])
    # Hopper pushes into the chest below it.
    hx, hz = x + 10, z
    game.command(f"setblock {hx} {y + 1} {hz} hopper[facing=down]")
    game.command(f"setblock {hx} {y} {hz} chest")
    added = game.run(f"container {hx} {y + 1} {hz} minecraft:redstone 5").get("slots", [])
    # Nudge the hopper's neighbour so its scheduled tick is refreshed after the direct block-entity write.
    game.command(f"setblock {hx + 1} {y + 1} {hz} air")
    game.wait(100)
    chest = game.run(f"container {hx} {y} {hz}").get("slots", [])
    hopper = game.run(f"container {hx} {y + 1} {hz}").get("slots", [])
    moved = sum(int(slot.get("count", 0)) for slot in chest
                if slot and _item_name(slot) == "redstone")
    game.sample(s, "redstone.piston_extended", 1 if "piston_head" in extended or "moving_piston" in extended else 0)
    game.sample(s, "redstone.lamp_lit", 1 if "lit=true" in lit else 0)
    game.sample(s, "redstone.hopper_moved", moved)
    s["notes"].append(f"lamp lit={('lit=true' in lit)}; repeater powered={('powered=true' in repeater_state)}; "
                      f"hopper had {sum(int(slot.get('count', 0)) for slot in added if slot)} item(s), "
                      f"chest ended with {moved}")
    game.check(s, "hopper transfers", moved >= 1, ">= 1 item", moved)
    hold(game, s, [x + 4, y + 3, z - 6], 20.0, args.seconds, "after_redstone", ctx["sampler"],
         ctx["warmup"], ctx["cooldown"])
    return finish(s, ["piston, repeater/lamp and hopper/chest, each state asserted"])


def scenario_entities(game, args, ctx, count=None):
    count = args.mobs if count is None else count
    name = "entities" if count == args.mobs else f"entities_{count}"
    s = new_scenario(name, "entities", args.seconds)
    spawn = game.position() or [0.0, 100.0, 0.0]
    origin = [int(spawn[0]) + 48, PLATFORM_Y, int(spawn[2])]
    platform_at(game, origin, args.render_distance, args.timeout)
    kinds = ("zombie", "cow", "pig", "sheep")
    begin = time.time()
    for i in range(count):
        x = origin[0] - 6 + (i % 13)
        z = origin[2] - 6 + ((i // 13) % 13)
        y = origin[1] + 1 + (i // 169) * 2
        game.command(f"summon {kinds[i % len(kinds)]} {x}.5 {y} {z}.5 "
                     "{NoAI:1b,NoGravity:1b,PersistenceRequired:1b,Silent:1b}")
    elapsed = time.time() - begin
    status = game.status()
    mobs = int(status.get("mobs", 0))
    game.sample(s, "play.spawn_s", elapsed)
    game.sample(s, "entities.mobs", mobs)
    game.sample(s, "entities.spawned", count)
    if count:
        game.check(s, "mobs spawned", mobs >= count * 0.8, f">= {int(count * 0.8)}", mobs)
    else:
        # Natural animals may be around; a leftover population from an earlier scenario would not be.
        game.check(s, "no summoned population", mobs < 50, "< 50 mobs", mobs)
    hold(game, s, [origin[0], origin[1] + 4.6, origin[2] - 12], 15.0, args.seconds, "dense_entities",
         ctx["sampler"], ctx["warmup"], ctx["cooldown"])
    game.check(s, "frames drawn", sum(f["frames"] for f in s["frames"]) > 10, "> 10",
               sum(f["frames"] for f in s["frames"]))
    return finish(s, [f"{count} still, no-AI mobs in view"])


def scenario_mixed(game, args, ctx):
    s = new_scenario("mixed", "soak", args.soak_seconds)
    spawn = game.position() or [0.0, 100.0, 0.0]
    origin = [int(spawn[0]), PLATFORM_Y, int(spawn[2])]
    platform_at(game, origin, args.render_distance, args.timeout)
    game.command("clear")
    game.wait(5)
    give_until(game, "stone", 64)
    game.run("select stone")
    teleport(game, [origin[0] + 6.5, origin[1] + 1.0, origin[2] + 0.5], 15.0,
             args.render_distance, args.timeout)
    before = game.status()
    begin = time.time()
    game.run("stats reset")
    actions = 0
    deadline = begin + args.soak_seconds
    while time.time() < deadline:
        game.run(f"tp {origin[0] + 6:.1f} {origin[1] + 1:.1f} {origin[2] + 0.5:.1f}")
        game.run("look 45 20")
        for dx, dz in ((4, 1), (5, 1), (4, 2), (5, 2)):
            game.run(f"place {origin[0] + dx} {origin[1]} {origin[2] + dz} --item stone", timeout=30)
            game.run(f"break {origin[0] + dx} {origin[1]} {origin[2] + dz}", timeout=30)
            actions += 2
        game.run("open-inventory", timeout=30)
        game.run("close")
        actions += 1
        if actions % 12 == 0:
            game.command(f"summon cow {origin[0] + 4}.5 {origin[1] + 1} {origin[2]}.5 "
                         "{NoAI:1b,PersistenceRequired:1b,Silent:1b}")
            game.run("attack", timeout=30)
            actions += 1
        if time.time() - begin > 5:
            game.run(f"tp {spawn[0]:.1f} {spawn[1]:.1f} {spawn[2]:.1f}")
            game.run("wait 5")
            game.run(f"tp {origin[0] + 6:.1f} {origin[1] + 1:.1f} {origin[2] + 0.5:.1f}")
        time.sleep(0.1)
    raw = game.run("stats raw")
    after = game.status()
    elapsed = time.time() - begin
    add_frames(game, s, raw, "mixed", begin, time.time())
    ticks = max(0, int(after.get("ticks", 0)) - int(before.get("ticks", 0)))
    game.sample(s, "play.actions", actions)
    game.sample(s, "play.action_s", elapsed)
    game.sample(s, "tick.tps", ticks / max(elapsed, 1e-9))
    game.sample(s, "run.wall_s", elapsed)
    for key, value in ctx["sampler"].window(begin, time.time()).items():
        if key.startswith("process."):
            game.sample(s, key, value)
    game.sample(s, "memory.rss_slope_mb_per_min",
                slope_mb_per_min([(t, rss) for t, rss, *_ in ctx["sampler"].samples if begin <= t]))
    check = s["checks"]
    game.check(s, "actions completed", actions > 10, "> 10", actions)
    game.check(s, "ticks advanced", ticks > 20, "> 20", ticks)
    game.check(s, "frames drawn", bool(s["frames"]) and s["frames"][0]["frames"] > 10, "> 10",
               s["frames"][0]["frames"] if s["frames"] else 0)
    return finish(s, ["teleports, mining, placing, inventory and combat in one continuous session"])


def scenario_world_ops(game, args, ctx):
    """Cold and warm loads, generation and sustained chunk turnover, measured as work completed."""
    s = new_scenario("world_ops", "worldgen", args.world_ops_cycles)
    spawn = game.position() or [0.0, 100.0, 0.0]
    cycles = max(1, args.world_ops_cycles)
    stride = 900
    # A cold load must actually generate: wait for the whole view rather than for "nothing queued
    # yet", which is true the instant the teleport lands. The warm revisit then finds it resident.
    required = pb.view_chunks(args.render_distance)
    last = None
    for i in range(cycles):
        x = spawn[0] + stride * (i + 1)
        z = spawn[2] - stride * (i + 1) * 0.5
        point = [x, max(spawn[1] + 40.0, 160.0), z]
        last = point
        before = game.status()
        begin = time.time()
        teleport(game, point, 10.0, args.render_distance, args.timeout, min_chunks=required, hold=True)
        cold_s = time.time() - begin
        after = game.status()
        generated = int(after.get("generated_chunks", 0)) - int(before.get("generated_chunks", 0))
        meshed = int(after.get("meshed_sections", 0)) - int(before.get("meshed_sections", 0))
        game.sample(s, "world.cold_load_ms", cold_s * 1000.0)
        game.sample(s, "world.cold_generated_chunks", generated)
        game.sample(s, "world.cold_meshed_sections", meshed)
        game.sample(s, "world.resident_chunks", int(after.get("chunks", 0)))
        # The same point again: the columns stay resident, so this is the cache-warm path.
        begin = time.time()
        teleport(game, point, 10.0, args.render_distance, args.timeout, min_chunks=required, hold=True)
        warm_s = time.time() - begin
        game.sample(s, "world.warm_load_ms", warm_s * 1000.0)
        game.check(s, f"cycle {i + 1} generated terrain", generated > 0, "> 0 chunks", generated)
        game.check(s, f"cycle {i + 1} chunks resident", int(after.get("chunks", 0)) >= required,
                   f">= {required} chunks", int(after.get("chunks", 0)))
    cold = s["samples"].get("world.cold_load_ms", [])
    warm = s["samples"].get("world.warm_load_ms", [])
    if cold and warm:
        game.sample(s, "world.warm_speedup", (sum(cold) / len(cold)) / max(sum(warm) / len(warm), 1e-9))
    hold(game, s, [last[0], last[1] + 1.6, last[2]], 10.0, args.seconds,
         "after_world_ops", ctx["sampler"], ctx["warmup"], ctx["cooldown"])
    return finish(s, [f"{cycles} cold teleports with a warm revisit each, {args.render_distance} chunks"])


def scenario_memory_soak(game, args, ctx):
    """Extended mixed gameplay, then a settle and a cleanup: slope, peak and retained memory."""
    s = new_scenario("memory_soak", "memory", args.soak_seconds)
    spawn = game.position() or [0.0, 100.0, 0.0]
    origin = [int(spawn[0]) + 96, PLATFORM_Y, int(spawn[2]) + 96]
    # The turnover loop will keep chunks streaming, so these setups wait only for the player to
    # arrive, not for the whole view; the soak itself is the load test.
    platform_at(game, origin, args.render_distance, args.timeout, min_chunks=0)
    give_until(game, "stone", 64)
    game.run("select stone")
    if ctx["sampler"].samples:
        base_rss = ctx["sampler"].samples[-1][1] / 2 ** 20
    else:
        base_rss = None
    begin = time.time()
    game.run("stats reset")
    actions = 0
    deadline = begin + args.soak_seconds
    direction = 1
    while time.time() < deadline:
        # Sustained chunk turnover: alternate between two far points so terrain is reloaded.
        x = origin[0] + direction * 640
        # Hover in place: a plain teleport into the air would fall for the ticks it takes the far
        # chunk to load, and the floor built afterwards would be above the player.
        game.run(f"fly {x + 6.5:.1f} {PLATFORM_Y + 1:.1f} {origin[2] + 0.5:.1f} "
                 f"{x + 6.5:.1f} {PLATFORM_Y + 1:.1f} {origin[2] + 0.5:.1f} 0.4 20 raw")
        game.run("look 45 20")
        game.wait(40)
        game.command(f"fill {x} {PLATFORM_Y - 1} {origin[2] - 5} {x + 10} {PLATFORM_Y - 1} "
                     f"{origin[2] + 5} stone")
        game.wait(5)
        game.command(f"fill {x} {PLATFORM_Y} {origin[2] - 5} {x + 10} {PLATFORM_Y + 3} "
                     f"{origin[2] + 5} air")
        # The player's camera looks towards -X/+Z (yaw 45): these are the faces in front of it.
        for dx, dz in ((4, 1), (5, 1), (4, 2), (5, 2)):
            game.run(f"place {x + dx} {PLATFORM_Y} {origin[2] + dz} --item stone", timeout=30)
            game.run(f"break {x + dx} {PLATFORM_Y} {origin[2] + dz}", timeout=30)
            actions += 2
        game.run("open-inventory", timeout=30)
        game.run("close")
        direction = -direction
        time.sleep(0.05)
    raw = game.run("stats raw")
    add_frames(game, s, raw, "memory_soak", begin, time.time())
    window = [(t, rss) for t, rss, *_ in ctx["sampler"].samples if begin <= t]
    peak = max((rss for _, rss in window), default=None)
    retained = (ctx["sampler"].samples[-1][1] / 2 ** 20) if ctx["sampler"].samples else None
    elapsed = time.time() - begin
    slope = slope_mb_per_min(window)
    game.sample(s, "memory.rss_slope_mb_per_min", slope)
    game.sample(s, "memory.rss_base_mb", base_rss)
    game.sample(s, "memory.rss_peak_mb", None if peak is None else peak / 2 ** 20)
    game.sample(s, "memory.rss_retained_mb", retained)
    game.sample(s, "memory.rss_growth_mb",
                None if base_rss is None or retained is None else retained - base_rss)
    for key, value in ctx["sampler"].window(begin, time.time()).items():
        if key.startswith("process."):
            game.sample(s, key, value)
    game.sample(s, "play.actions", actions)
    game.sample(s, "run.wall_s", elapsed)
    # Cleanup: kill spawned entities, return to the platform and let the caches settle.
    game.command("kill @e[type=!player]")
    game.run(f"tp {origin[0] + 0.5:.1f} {PLATFORM_Y + 1:.1f} {origin[2] + 0.5:.1f}")
    game.wait(40)
    cleaned = (ctx["sampler"].samples[-1][1] / 2 ** 20) if ctx["sampler"].samples else None
    game.sample(s, "memory.rss_after_cleanup_mb", cleaned)
    game.check(s, "actions completed", actions > 10, "> 10", actions)
    game.check(s, "frames drawn", sum(f["frames"] for f in s["frames"]) > 10, "> 10",
               sum(f["frames"] for f in s["frames"]))
    game.check(s, "memory slope measured", slope is not None, "a number", slope)
    # 512 MiB/min is a runaway, not a cache: ordinary gameplay stays far below it.
    game.check(s, "memory does not run away", slope is None or slope < 512, "< 512 MiB/min", slope)
    return finish(s, [f"{args.soak_seconds:.0f} s of mixed gameplay with chunk turnover, cleanup sampled"])


def scenario_overhead(game, args, ctx):
    """The same hold with the sampler paused and running: the instrumentation's own cost."""
    s = new_scenario("overhead", "instrumentation", args.seconds)
    pos = game.position() or [0.0, 100.0, 0.0]
    view = [pos[0], pos[1] + 1.6, pos[2]]
    ctx["sampler"].pause()
    off = hold(game, s, view, 20.0, args.seconds, "sampler_off", None)
    ctx["sampler"].resume()
    on = hold(game, s, view, 20.0, args.seconds, "sampler_on", ctx["sampler"])
    if off and on and off.get("avg_fps") and on.get("avg_fps"):
        cost = (on["avg_fps"] - off["avg_fps"]) / off["avg_fps"] * 100
        game.sample(s, "overhead.sampler_cost_pct", cost)
        game.sample(s, "overhead.fps_sampler_off", off["avg_fps"])
        game.sample(s, "overhead.fps_sampler_on", on["avg_fps"])
        game.check(s, "both phases drew frames", off["frames"] > 10 and on["frames"] > 10,
                   "> 10 each", f"{off['frames']}/{on['frames']}")
    else:
        game.check(s, "both phases drew frames", False, "> 10 each", "missing frames")
    return finish(s, ["sampler paused vs running; a cost above a few percent would distort every reading"])


REDSTONE_SIZES = {"small": 1, "medium": 16, "large": 64, "extreme": 256}


def scenario_redstone_scale(game, args, ctx, size="small"):
    """Piston cells driven from one bus: every state transition is asserted, and the count is fixed."""
    cells = REDSTONE_SIZES[size]
    s = new_scenario(f"redstone_{size}" if size != "small" else "redstone", "simulation", args.seconds)
    spawn = game.position() or [0.0, 100.0, 0.0]
    origin = [int(spawn[0]) - 64, PLATFORM_Y, int(spawn[2]) - 64]
    platform_at(game, origin, args.render_distance, args.timeout)
    columns = 16
    positions = []
    begin = time.time()
    for i in range(cells):
        x = origin[0] + (i % columns) * 3
        z = origin[2] + (i // columns) * 3
        positions.append((x, z))
        game.command(f"setblock {x} {origin[1]} {z} piston[facing=east]")
        game.command(f"setblock {x - 1} {origin[1]} {z} redstone_block")
    powered = time.time()
    game.wait(60)
    extended = 0
    for x, z in positions:
        state = game.block([x + 1, origin[1], z])
        if "piston_head" in state or "moving_piston" in state:
            extended += 1
    for x, z in positions:
        game.command(f"setblock {x - 1} {origin[1]} {z} air")
    unpowered = time.time()
    game.wait(60)
    retracted = sum(1 for x, z in positions
                    if "air" in game.block([x + 1, origin[1], z]).lower())
    game.sample(s, "redstone.cells", cells)
    game.sample(s, "redstone.extended", extended)
    game.sample(s, "redstone.retracted", retracted)
    game.sample(s, "redstone.state_transitions", cells * 2)
    game.sample(s, "redstone.power_on_s", powered - begin)
    game.sample(s, "redstone.power_off_s", unpowered - powered)
    game.check(s, "every piston extended", extended == cells, f"== {cells}", extended)
    game.check(s, "every piston retracted", retracted == cells, f"== {cells}", retracted)
    hold(game, s, [origin[0], origin[1] + 4.6, origin[2] - 10], 20.0, args.seconds, "after_redstone",
         ctx["sampler"], ctx["warmup"], ctx["cooldown"])
    return finish(s, [f"{cells} piston cells on one bus, {cells * 2} state transitions asserted"])


def scenario_render(game, args, ctx):
    """One render configuration (the runner relaunches the game for each): frame distribution only."""
    label = ctx.get("config_label", "default")
    s = new_scenario(f"render@{label}", "renderer", args.seconds)
    pos = game.position() or [0.0, 100.0, 0.0]
    view = [pos[0], pos[1] + 1.6, pos[2]]
    hold(game, s, view, 20.0, args.seconds, "render", ctx["sampler"], ctx["warmup"], ctx["cooldown"])
    status = game.status()
    game.sample(s, "render.render_distance", status.get("render_distance"))
    game.sample(s, "render.resident_chunks", status.get("chunks"))
    frames = sum(f["frames"] for f in s["frames"])
    game.check(s, "frames drawn", frames > 10, "> 10", frames)
    game.check(s, "chunks resident", int(status.get("chunks", 0)) > 0, "> 0",
               int(status.get("chunks", 0)))
    return finish(s, [f"window {label}"])


RUNNERS = {
    "idle": scenario_idle,
    "walk": scenario_walk,
    "explore": scenario_explore,
    "mine_place": scenario_mine_place,
    "crafting": scenario_crafting,
    "combat": scenario_combat,
    "redstone": scenario_redstone,
    "entities": scenario_entities,
    "world_ops": scenario_world_ops,
    "mixed": scenario_mixed,
    "memory_soak": scenario_memory_soak,
    "overhead": scenario_overhead,
    "render": scenario_render,
}


# --- run bookkeeping ---------------------------------------------------------------------------

def git_info():
    try:
        commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                                capture_output=True, text=True, check=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain"],
                                    capture_output=True, text=True, check=True).stdout.strip())
        return commit, dirty
    except (OSError, subprocess.CalledProcessError):
        return None, None


def tool_version(command):
    try:
        return subprocess.run([command, "-V"], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def rustc_version():
    return tool_version("rustc")


def rustc_host():
    try:
        out = subprocess.run(["rustc", "-vV"], capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    for line in out.splitlines():
        if line.startswith("host: "):
            return line.split(": ", 1)[1].strip()
    return None


def sha256_file(path, chunk=4 * 2 ** 20):
    """The binary's identity: same source, same profile and same compiler should give the same bytes."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while block := handle.read(chunk):
            digest.update(block)
    return digest.hexdigest()


def binary_info(path):
    stat = Path(path).stat()
    return {"path": str(path), "bytes": stat.st_size,
            "modified": datetime.datetime.fromtimestamp(stat.st_mtime, datetime.timezone.utc)
            .strftime("%Y-%m-%dT%H:%M:%SZ"),
            "sha256": sha256_file(path)}


def summarize_trace(path, top=12):
    """Top named spans from a Chrome trace written by the game's `trace` command.

    The events carry wall duration per named step on each thread (`spans::trace`), so the summary
    says where a measured scene spent its time without a platform profiler. A trace is bounded by
    the seconds it was given, and only `--trace-repeat` is traced.
    """
    try:
        events = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return {"file": str(path), "error": str(error)}
    threads = {}
    spans = {}
    for event in events if isinstance(events, list) else []:
        if event.get("ph") == "M" and event.get("name") == "thread_name":
            threads[event.get("tid")] = (event.get("args") or {}).get("name")
        elif event.get("ph") == "X" and "dur" in event:
            key = (event.get("name"), event.get("tid"))
            entry = spans.setdefault(key, {"name": event.get("name"), "tid": event.get("tid"),
                                           "count": 0, "wall_ms": 0.0, "max_ms": 0.0})
            entry["count"] += 1
            entry["wall_ms"] += float(event["dur"]) / 1000.0
            entry["max_ms"] = max(entry["max_ms"], float(event["dur"]) / 1000.0)
    ranked = sorted(spans.values(), key=lambda e: e["wall_ms"], reverse=True)[:top]
    for entry in ranked:
        entry["thread"] = threads.get(entry["tid"]) or f"tid {entry['tid']}"
        entry["wall_ms"] = pb.rnd(entry["wall_ms"])
        entry["max_ms"] = pb.rnd(entry["max_ms"])
    return {"file": str(path), "events": len(events) if isinstance(events, list) else 0,
            "threads": sorted(name for name in threads.values() if name), "top_spans": ranked}


def hardware(status):
    renderer = status.get("renderer") or {}
    display = status.get("display") or {}
    info = {
        "os": {"win32": "windows", "darwin": "macos"}.get(sys.platform, sys.platform),
        "os_version": platform.version(),
        "arch": platform.machine(),
        "cpu": platform.processor() or None,
        "cpu_threads": os.cpu_count(),
        "ram_mb": _ram_mb(),
        "gpu": {
            "name": renderer.get("gpu", ""),
            "vendor": renderer.get("vendor", ""),
            "driver": renderer.get("driver", ""),
            "backend": (renderer.get("backend") or "").lower(),
            "kind": renderer.get("device_type", ""),
        } if renderer else None,
        "display": {"width": display.get("width"), "height": display.get("height"),
                    "scale": display.get("scale", 1.0),
                    "refresh_hz": display.get("refresh_hz")} if display else None,
    }
    try:
        import psutil
        info["cpu_physical_cores"] = psutil.cpu_count(logical=False)
        info["cpu_mhz"] = round(psutil.cpu_freq().max or 0) or None if psutil.cpu_freq() else None
        info["python"] = platform.python_version()
        info["psutil"] = psutil.__version__
    except (ImportError, OSError, AttributeError):
        pass
    return info


def _ram_mb():
    try:
        if sys.platform == "win32":
            import ctypes

            class MemoryStatus(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            status = MemoryStatus()
            status.dwLength = ctypes.sizeof(status)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
            return int(status.ullTotalPhys // (1024 * 1024))
        if sys.platform == "darwin":
            return int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True,
                                      check=True).stdout.strip()) // (1024 * 1024)
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) // 1024
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    return None


def build_binary(build):
    build = Path(build)
    if not build.is_absolute():
        build = ROOT / build
    name = "horizon-client.exe" if sys.platform == "win32" else "horizon-client"
    path = build / name
    if not path.exists():
        raise SystemExit(f"no game at {path}: build it with `python3 tools/cargo_build.py --profile bench`")
    return path


def set_priority(pid, level="high"):
    """Raise the game above ordinary background work so frame stalls measure the game, not the OS
    scheduler. `normal` leaves the default; an unsupported platform is a no-op."""
    if sys.platform != "win32" or level == "normal":
        return False
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    handle = kernel32.OpenProcess(0x0200, False, pid)  # PROCESS_SET_INFORMATION
    if not handle:
        return False
    try:
        return bool(kernel32.SetPriorityClass(handle, 0x00000080))  # HIGH_PRIORITY_CLASS
    finally:
        kernel32.CloseHandle(handle)


def launch(args, build, game_dir, width, height, render_distance):
    """One game process on a fresh game folder, so every pass sees a cold world and empty caches."""
    shutil.rmtree(game_dir, ignore_errors=True)
    game_dir.mkdir(parents=True, exist_ok=True)
    pb.write_options(game_dir, render_distance)
    sock = pb.control_path()
    sock.unlink(missing_ok=True)
    binary = build_binary(build)
    command = [str(binary), "--resources", str(Path(args.resources).resolve()),
               "--control-socket", str(sock), "--game-dir", str(game_dir),
               "--no-pause", "--weather", "clear", "--time", "6000"]
    if (width, height) != (1280, 720):
        command += ["--width", str(width), "--height", str(height)]
    if args.offscreen:
        command.append("--offscreen")
    env = lab.game_env(HORIZON_TELEMETRY_URL="off")
    log = (game_dir.parent / "game.log").open("w")
    proc = subprocess.Popen(command, cwd=game_dir, env=env, stdout=log, stderr=subprocess.STDOUT)
    set_priority(proc.pid, getattr(args, "priority", "high"))
    sampler = ProcessSampler(proc.pid, getattr(args, "sampler_interval", 0.5))
    sampler.start()
    control = pb.Control(sock)
    try:
        title, _ = pb.poll(control, lambda s: s.get("screen") == "title" and s.get("renderer"),
                           args.timeout)
        control(f"open {WORLD} {args.seed} creative")
        pb.wait_loaded(control, lambda p: True, args.timeout, pb.view_chunks(render_distance))
    except Exception:
        sampler.stop.set()
        try:
            proc.kill()
        except OSError:
            pass
        log.close()
        raise
    return Game(control, proc, game_dir), sampler, title, log, sock


def stop(game, sampler, log, sock):
    sampler.stop.set()
    try:
        game.run("quit", timeout=60)
    except (OSError, ValueError, RuntimeError):
        pass
    try:
        game.proc.wait(timeout=60)
    except subprocess.TimeoutExpired:
        game.proc.kill()
        game.proc.wait()
    log.close()
    sock.unlink(missing_ok=True)


def cleanup(game):
    """Return to a neutral state between scenarios: no screen, no mobs, default time and weather."""
    try:
        if game.run("screen").get("screen") not in (None, "playing", "none", "title"):
            game.run("close")
    except (OSError, RuntimeError):
        pass
    for line in ("gamemode creative", "kill @e[type=!player]", "weather clear", "time 6000"):
        try:
            game.command(line)
        except (OSError, RuntimeError):
            pass
    try:
        game.wait(2)
    except (OSError, RuntimeError):
        pass


def configurations(args):
    """(width, height, render distance, label) for each run. One entry unless the operator asks for more."""
    resolutions = pb.parse_sizes(args.resolutions) if args.resolutions else [(args.width, args.height)]
    distances = [int(v) for v in args.render_distances.split(",") if v] if args.render_distances else [args.render_distance]
    configs = [(w, h, d) for w, h in resolutions for d in distances]
    many = len(configs) > 1
    return [(w, h, d, (f"{w}x{h}rd{d}" if many else "")) for w, h, d in configs]


def selected_scenarios(args):
    if args.smoke:
        names = list(SMOKE_SCENARIOS)
    else:
        names = [s.strip() for s in args.scenarios.split(",") if s.strip()] if args.scenarios else list(SCENARIOS)
        if "all" in names:
            names = list(SCENARIOS) + list(EXTRA_SCENARIOS)
        names += [s.strip() for s in args.include.split(",") if s.strip()]
    if args.entity_counts:
        counts = [int(v) for v in args.entity_counts.split(",") if v]
        if any(c > 250 for c in counts) and not args.large:
            raise SystemExit("entity counts above 250 are opt-in: pass --large")
        if "entities" in names:
            names.remove("entities")
        names += [f"entities_{c}" for c in counts]
    if args.redstone_sizes:
        sizes = [v.strip() for v in args.redstone_sizes.split(",") if v.strip()]
        unknown = [v for v in sizes if v not in REDSTONE_SIZES]
        if unknown:
            raise SystemExit(f"unknown redstone sizes: {', '.join(unknown)} (small, medium, large, extreme)")
        if any(s == "extreme" for s in sizes) and not args.large:
            raise SystemExit("the extreme redstone circuit is opt-in: pass --large")
        if "redstone" in names:
            names.remove("redstone")
        names += ["redstone" if s == "small" else f"redstone_{s}" for s in sizes]
    if args.render_matrix:
        if "render" not in names:
            names.append("render")
    return names


def runner_for(name):
    base = name.split("@", 1)[0]
    if base in RUNNERS:
        return RUNNERS[base], {}
    if base.startswith("entities_") and base[len("entities_"):].isdigit():
        return scenario_entities, {"count": int(base[len("entities_"):])}
    if base.startswith("redstone_") and base[len("redstone_"):] in REDSTONE_SIZES:
        return scenario_redstone_scale, {"size": base[len("redstone_"):]}
    raise KeyError(base)


def suite_skeleton(args, label, build):
    commit, dirty = git_info()
    binary = build_binary(build)
    machine = load_snapshot()
    return {
        "format": SUITE_FORMAT, "version": SUITE_VERSION,
        "created": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "label": label,
        "run": {"commit": commit, "dirty": dirty, "profile": args.profile_name,
                "build_dir": Path(build).name or str(build),
                "rustc": rustc_version(), "cargo": tool_version("cargo"),
                "target": os.environ.get("CARGO_BUILD_TARGET") or rustc_host()
                or f"{platform.machine()}-{sys.platform}",
                "python": sys.version.split()[0], "features": [],
                "binary": binary_info(binary), "command": sys.argv},
        "conditions": {
            "seed": str(SEED), "simulation_distance": 12, "offscreen": bool(args.offscreen),
            "repeats": args.repeats, "warmup_s": args.warmup_seconds,
            "cooldown_s": args.cooldown_seconds, "sampler_interval_s": args.sampler_interval,
            "vsync": False, "fps_cap": 260, "power": None,
            "load_avg_1m": machine.get("load_1m"),
            "contamination_cpu_pct": args.contamination_cpu_pct,
            "contamination_free_mb": args.contamination_free_mb,
            "priority": args.priority,
        },
        "environment": {"started": utc_stamp(), "load_before": machine,
                        "cpu_count": os.cpu_count(), "ram_mb": _ram_mb()},
        "hardware": {}, "scenarios": [],
    }


def utc_stamp():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def merge_run(suite, run, repeat):
    """Merge one repeat into the suite's scenario entry, keeping its raw samples and failed checks."""
    name = run["name"]
    merged = next((s for s in suite["scenarios"] if s["name"] == name), None)
    if merged is None:
        merged = new_scenario(name, run.get("category", "failed"), run.get("seconds", 0.0))
        suite["scenarios"].append(merged)
    for metric, values in run.get("samples", {}).items():
        merged["samples"].setdefault(metric, []).extend(values)
    for frame in run.get("frames", []):
        frame = dict(frame)
        frame["repeat"] = repeat
        merged["frames"].append(frame)
    detail = {"repeat": repeat, "samples": run.get("samples", {}), "frames": len(run.get("frames", [])),
              "checks": run.get("checks", []), "notes": run.get("notes", []),
              "contamination": run.get("contamination", [])}
    merged.setdefault("runs", []).append(detail)
    if repeat == 0:
        merged["checks"] = list(run.get("checks", []))
        merged["notes"] = list(run.get("notes", []))
    else:
        for check in run.get("checks", []):
            if not check["passed"]:
                failed = dict(check)
                failed["name"] = f"repeat {repeat + 1}: {failed['name']}"
                merged["checks"].append(failed)
    if run.get("profile"):
        merged["profile"] = run["profile"]
    for reason in run.get("contamination", []):
        tagged = f"repeat {repeat + 1}: {reason}"
        if tagged not in merged["contamination"]:
            merged["contamination"].append(tagged)
    merged["repeats"] = max(merged.get("repeats", 0), repeat + 1)
    if not run.get("valid", False):
        merged["contaminated_valid"] = False
    finish(merged)
    return merged


def scenario_stats(suite):
    """Per-metric statistics and outliers, computed from the raw samples at report time."""
    for scenario in suite["scenarios"]:
        scenario["stats"] = {metric: value for metric, values in scenario.get("samples", {}).items()
                             if (value := statistics_of(values)) is not None}


def trace_path_for(args, name, repeat):
    """Where this repeat's bounded trace goes, or None when tracing is off/not selected."""
    if not args.trace_dir or repeat != args.trace_repeat:
        return None
    selected = [s.strip().split("@")[0] for s in args.trace_scenarios.split(",") if s.strip()]
    base = name.split("@")[0]
    if selected and not any(base == s or base.startswith(s + "_") for s in selected):
        return None
    directory = Path(args.trace_dir)
    if not directory.is_absolute():
        directory = ROOT / directory
    return directory / f"{re.sub(r'[^A-Za-z0-9_.-]+', '-', name)}-{repeat}.json"


def run_pass(args, suite, names, build, config, repeat, baseline=False):
    """Launch one game for one (build, configuration) and run every selected scenario once."""
    width, height, distance, label = config
    suffix = f"@{label}" if label else ""
    game = sampler = log = sock = None
    try:
        game, sampler, title, log, sock = launch(args, build, WORK / f"game-{repeat}-{label or 'default'}",
                                                 width, height, distance)
        if not suite["hardware"]:
            suite["hardware"] = hardware(title)
            suite["conditions"].update({"render_distance": distance, "window": [width, height],
                                        "backend": (suite["hardware"].get("gpu") or {}).get("backend")})
        ctx = {"sampler": sampler, "warmup": args.warmup_seconds, "cooldown": args.cooldown_seconds,
               "config_label": label}
        for name in names:
            runner, extra = runner_for(name)
            print(f"[{name}{suffix}] repeat {repeat + 1}/{args.repeats} ...", flush=True)
            before = load_snapshot()
            tracer = trace_path_for(args, name, repeat)
            local_trace = None
            if tracer:
                # The control protocol splits on spaces, so the game is told a path relative to its
                # own folder (never the checkout's, which may contain spaces); the finished trace is
                # moved to --trace-dir afterwards.
                local_trace = game.dir / "traces" / tracer.name
                local_trace.parent.mkdir(parents=True, exist_ok=True)
                game.run(f"trace traces/{tracer.name} {int(args.trace_seconds)}", timeout=30)
            try:
                ensure_playing(game)
                run = runner(game, args, ctx, **extra) if extra else runner(game, args, ctx)
            except Exception as error:
                # A scenario that could not run is a failed workload, not a fast one. Keep it in the
                # report so the failure is visible and the remaining scenarios still run.
                run = new_scenario(name, "failed", 0.0)
                run["checks"].append({"name": "scenario completed", "expected": "no exception",
                                      "actual": f"{type(error).__name__}: {error}", "passed": False})
                run["notes"].append("the scenario aborted; no measurement is valid")
                run["valid"] = False
            after = load_snapshot()
            if tracer and local_trace:
                try:
                    game.run("trace stop", timeout=30)
                except (OSError, RuntimeError):
                    pass
                if local_trace.exists() and local_trace.stat().st_size:
                    tracer.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(local_trace), str(tracer))
                    run.setdefault("profile", {})["trace"] = summarize_trace(tracer)
                else:
                    run.setdefault("profile", {})["trace"] = {
                        "file": str(tracer), "error": "the game wrote no trace file"}
            if suffix:
                run["name"] = run["name"] + suffix
            frames = sum(f.get("frames", 0) for f in run.get("frames", []))
            run["contamination"].extend(contamination(run, suite.get("environment", {}).get("ram_mb"),
                                                      before, after, args, frames, expected_frames_s=5.0))
            run = finish(run)
            merged = merge_run(suite, run, repeat)
            state = "valid" if merged.get("valid") else "INVALID"
            dirty = merged.get("contamination")
            print(f"[{name}{suffix}] {state}; "
                  f"{(merged['samples'].get('render.avg_fps') or ['-'])[-1]} fps; "
                  f"{len(merged['checks'])} check(s){'; CONTAMINATED: ' + ', '.join(dirty) if dirty else ''}",
                  flush=True)
            cleanup(game)
        if baseline:
            suite["comparison_kind"] = "baseline"
    finally:
        if game:
            stop(game, sampler, log, sock)


def markdown(suite, comparisons=None):
    lines = [f"# Gameplay benchmark: {suite.get('label') or 'run'}", ""]
    run = suite.get("run") or {}
    hw = suite.get("hardware") or {}
    cond = suite.get("conditions") or {}
    binary = run.get("binary") or {}
    lines += [f"- Commit: `{run.get('commit') or 'unknown'}`{' (dirty)' if run.get('dirty') else ''}",
              f"- Profile: `{run.get('profile') or 'unknown'}`; {run.get('rustc') or 'rustc unknown'}",
              f"- Binary: {binary.get('bytes', '?')} bytes, sha256 `{binary.get('sha256') or 'unknown'}`",
              f"- Machine: {hw.get('os', '?')} {hw.get('os_version', '')}, {hw.get('cpu') or 'CPU unknown'}, "
              f"{hw.get('ram_mb') or '?'} MiB, {hw.get('cpu_threads') or '?'} thread(s)",
              f"- GPU: {((hw.get('gpu') or {}).get('name') or 'unknown')} "
              f"({((hw.get('gpu') or {}).get('backend') or '?')}), driver "
              f"{((hw.get('gpu') or {}).get('driver') or 'unknown')}",
              f"- Conditions: window {cond.get('window') or '?'}, render distance "
              f"{cond.get('render_distance') or '?'}, seed {cond.get('seed') or '?'}, "
              f"{suite.get('conditions', {}).get('repeats') or '?'} repeat(s), "
              f"warm-up {cond.get('warmup_s', '?')} s, cooldown {cond.get('cooldown_s', '?')} s",
              ""]
    lines += ["| scenario | valid | checks | avg FPS | 1% low | p99 ms | tick mspt | tps | RSS MB | contamination |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for s in suite.get("scenarios", []):
        def pick(metric):
            stat = (s.get("stats") or {}).get(metric)
            if stat and stat.get("mean") is not None:
                if stat.get("ci95") is not None:
                    return f"{stat['mean']:.3g} ±{stat['ci95']:.3g}"
                return f"{stat['mean']:.3g}"
            samples = s.get("samples", {}).get(metric) or [None]
            return samples[-1]
        reasons = "; ".join(s.get("contamination") or []) or "-"
        lines.append(f"| {s['name']} | {'yes' if s.get('valid') else 'NO'} | "
                     f"{sum(1 for c in s.get('checks', []) if c['passed'])}/{len(s.get('checks', []))} | "
                     f"{pick('render.avg_fps') or '-'} | {pick('render.low_1pct_fps') or '-'} | "
                     f"{pick('render.p99_ms') or '-'} | {pick('tick.mspt') or '-'} | "
                     f"{pick('tick.tps') or '-'} | {pick('process.rss_steady_mb') or '-'} | {reasons} |")
    lines += ["", "## Statistics (mean, 95% CI, coefficient of variation; repeats, raw samples kept)", "",
              "| scenario | metric | n | mean | ci95 | cv% | outliers |", "|---|---|---:|---:|---:|---:|---|"]
    for s in suite.get("scenarios", []):
        for metric, stat in (s.get("stats") or {}).items():
            if stat["n"] < 1:
                continue
            lines.append(f"| {s['name']} | {metric} | {stat['n']} | {stat['mean']} | "
                         f"±{stat.get('ci95') or '-'} | {stat.get('cv_pct') or '-'} | "
                         f"{stat.get('outlier_count', 0)} |")
    lines += ["", "## Correctness checks", ""]
    for s in suite.get("scenarios", []):
        for c in s.get("checks", []):
            lines.append(f"- {'PASS' if c['passed'] else 'FAIL'} `{s['name']}`: {c['name']} "
                         f"(expected {c['expected']}, got {c['actual']})")
    if comparisons:
        lines += ["", "## Comparison (confirmed regressions vs noise)", "",
                  "| scenario | metric | before | after | change | noise | verdict | regression |",
                  "|---|---|---:|---:|---:|---:|---|---|"]
        for c in comparisons:
            lines.append(f"| {c['scenario']} | {c['metric']} | {c['before']['mean']:.3f} | "
                         f"{c['after']['mean']:.3f} | {c['change_pct']:+.1f}% | "
                         f"±{c.get('noise_pct') if c.get('noise_pct') is not None else '-'}% | "
                         f"{c.get('verdict', '')} | {'YES' if c['regression'] else ''} |")
    return "\n".join(lines) + "\n"


def write_report(suite, args, comparisons=None, label=None):
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
    stable = label is None and getattr(args, "out", None)
    label = re.sub(r"[^A-Za-z0-9_.-]+", "-", label or suite.get("label") or "run")
    if stable:
        # A stable path for CI (--out): the report and its Markdown beside it.
        json_path = Path(args.out)
        if not json_path.is_absolute():
            json_path = ROOT / json_path
        json_path.parent.mkdir(parents=True, exist_ok=True)
        md_path = json_path.with_suffix(".md")
    else:
        directory = Path(args.out_dir)
        if not directory.is_absolute():
            directory = ROOT / directory
        directory.mkdir(parents=True, exist_ok=True)
        json_path = directory / f"{label}-{stamp}.json"
        md_path = directory / f"{label}-{stamp}.md"
    json_path.write_text(json.dumps(suite, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(markdown(suite, comparisons), encoding="utf-8")
    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    return json_path


def raw_frames(suite, args):
    """Keep the per-frame streams next to the report when asked; bounded by the number of frames taken."""
    if not args.raw_frames:
        return
    directory = Path(args.raw_frames)
    if not directory.is_absolute():
        directory = ROOT / directory
    directory.mkdir(parents=True, exist_ok=True)
    for s in suite["scenarios"]:
        for entry, repeat in zip(s.get("frames", []), [f.get("repeat", 0) for f in s.get("frames", [])]):
            if entry.get("histogram") is None:
                continue
            path = directory / f"{re.sub(r'[^A-Za-z0-9_.-]+', '-', s['name'])}-{repeat}-{entry['phase']}.json"
            path.write_text(json.dumps(entry) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--build", default="target/release", help="folder holding horizon-client (bench profile builds there)")
    parser.add_argument("--baseline-build", default=None,
                        help="a second build to alternate with --build, for a paired comparison")
    parser.add_argument("--resources", default=str(lab.RESOURCES))
    parser.add_argument("--label", default="gameplay")
    parser.add_argument("--scenarios", default="",
                        help="comma list; default is the core suite; 'all' adds the opt-in scenarios")
    parser.add_argument("--include", default="", help="extra opt-in scenarios (memory_soak, overhead)")
    parser.add_argument("--smoke", action="store_true", help="four short scenarios, for CI")
    parser.add_argument("--list", action="store_true", help="print the core scenario names")
    parser.add_argument("--seconds", type=float, default=8.0, help="stationary hold per scenario")
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS,
                        help=f"measured passes per scenario (default {DEFAULT_REPEATS})")
    parser.add_argument("--warmup-seconds", type=float, default=2.0, help="warm-up hold before each measurement")
    parser.add_argument("--cooldown-seconds", type=float, default=1.0, help="settle time after each measurement")
    parser.add_argument("--sampler-interval", type=float, default=0.5, help="process sampling period, seconds")
    parser.add_argument("--explore-seconds", type=float, default=20.0)
    parser.add_argument("--explore-blocks", type=float, default=512.0)
    parser.add_argument("--soak-seconds", type=float, default=20.0)
    parser.add_argument("--world-ops-cycles", type=int, default=4)
    parser.add_argument("--mobs", type=int, default=200)
    parser.add_argument("--entity-counts", default="", help="0,100,250,500,1000,2000 (above 250 needs --large)")
    parser.add_argument("--redstone-sizes", default="", help="small,medium,large,extreme (extreme needs --large)")
    parser.add_argument("--render-matrix", action="store_true", help="add the render scenario for each configuration")
    parser.add_argument("--resolutions", default="", help="1280x720,1920x1080: one pass per resolution")
    parser.add_argument("--render-distances", default="", help="8,12,16: one pass per distance")
    parser.add_argument("--large", action="store_true", help="allow the opt-in large workloads")
    parser.add_argument("--render-distance", type=int, default=12)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--offscreen", action="store_true")
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--out-dir", default="benchmarks/gameplay")
    parser.add_argument("--out", default=None, help="write the report at this exact path (CI)")
    parser.add_argument("--raw-frames", default=None, help="folder for the per-frame streams")
    parser.add_argument("--trace-dir", default=None,
                        help="write one bounded Chrome trace per selected scenario and --trace-repeat")
    parser.add_argument("--trace-scenarios", default="idle,mine_place,redstone,entities",
                        help="scenario prefixes to trace")
    parser.add_argument("--trace-repeat", type=int, default=0, help="only this repeat is traced")
    parser.add_argument("--trace-seconds", type=float, default=20.0,
                        help="the trace's hard time bound, seconds")
    parser.add_argument("--profile-name", default=None,
                        help="the Cargo profile the binary was built with (default: from --build)")
    parser.add_argument("--priority", choices=["high", "normal"], default="high",
                        help="the game's process priority (Windows); high reduces scheduler stalls")
    parser.add_argument("--contamination-cpu-pct", type=float, default=CONTAMINATION_CPU_PCT,
                        help="other CPU use above which a measurement is reported contaminated")
    parser.add_argument("--contamination-free-mb", type=float, default=CONTAMINATION_FREE_MB,
                        help="free physical memory below which a measurement is contaminated")
    parser.add_argument("--no-fail", action="store_true", help="exit 0 even when a check fails")
    parser.add_argument("--compare", nargs=2, metavar=("BEFORE", "AFTER"),
                        help="compare two suite files instead of running")
    parser.add_argument("--threshold", type=float, default=5.0)
    parser.add_argument("--require-significance", action="store_true")
    args = parser.parse_args(argv)

    if args.list:
        print("\n".join(SCENARIOS))
        return 0
    if args.compare:
        before = json.loads(Path(args.compare[0]).read_text(encoding="utf-8"))
        after = json.loads(Path(args.compare[1]).read_text(encoding="utf-8"))
        comparisons = compare_suites(before, after, args.threshold, args.require_significance)
        print("| scenario | metric | before | after | change | noise | verdict | regression |")
        print("|---|---|---:|---:|---:|---:|---|---|")
        for c in comparisons:
            print(f"| {c['scenario']} | {c['metric']} | {c['before']['mean']:.3f} | "
                  f"{c['after']['mean']:.3f} | {c['change_pct']:+.1f}% | "
                  f"±{c['noise_pct'] if c['noise_pct'] is not None else '-'}% | {c['verdict']} | "
                  f"{'YES' if c['regression'] else ''} |")
        regressions = sum(1 for c in comparisons if c["regression"])
        uncertain = sum(1 for c in comparisons if c["verdict"] == "uncertain")
        print(f"\n{len(comparisons)} metric(s), {regressions} confirmed regression(s) over {args.threshold}%, "
              f"{uncertain} uncertain")
        return 0 if args.no_fail or not regressions else 1

    selected = selected_scenarios(args)
    unknown = []
    for name in selected:
        try:
            runner_for(name)
        except KeyError:
            unknown.append(name)
    if unknown:
        parser.error(f"unknown scenarios: {', '.join(unknown)}")
    global RAW_FRAMES
    RAW_FRAMES = [] if args.raw_frames else None
    if args.smoke:
        args.repeats = min(args.repeats, 2)
        args.seconds = min(args.seconds, 4.0)
        args.explore_seconds = min(args.explore_seconds, 6.0)
        args.soak_seconds = min(args.soak_seconds, 8.0)
        args.world_ops_cycles = min(args.world_ops_cycles, 2)
        args.warmup_seconds = min(args.warmup_seconds, 1.0)
        args.cooldown_seconds = min(args.cooldown_seconds, 0.2)
    if args.repeats < 1:
        parser.error("--repeats must be at least 1")
    if args.profile_name is None:
        args.profile_name = "fast" if Path(args.build).name == "fast" else "bench"
    configs = configurations(args)
    builds = [("candidate", args.build)]
    if args.baseline_build:
        builds.append(("baseline", args.baseline_build))

    suites = {kind: suite_skeleton(args, args.label if kind == "candidate" else f"{args.label}-baseline", build)
              for kind, build in builds}
    try:
        for repeat in range(args.repeats):
            # Alternate the order of the two builds so drift over the session cannot favour one.
            order = list(builds) if repeat % 2 == 0 else list(reversed(builds))
            for kind, build in order:
                suite = suites[kind]
                for config in configs:
                    run_pass(args, suite, selected, build, config, repeat, baseline=(kind == "baseline"))
    finally:
        environment = suites["candidate"]["environment"]
        environment["ended"] = utc_stamp()
        environment["load_after"] = load_snapshot()

    candidate = suites["candidate"]
    scenario_stats(candidate)
    errors = []
    for s in candidate["scenarios"]:
        if not s.get("valid"):
            errors.extend(f"{s['name']}: {c['name']}" for c in s["checks"] if not c["passed"])
    comparisons = None
    if args.baseline_build:
        baseline = suites["baseline"]
        scenario_stats(baseline)
        # Candidate is "after": a slower candidate is the regression.
        comparisons = compare_suites(baseline, candidate, args.threshold, args.require_significance)
        write_report(baseline, args, label=f"{args.label}-baseline")
    path = write_report(candidate, args, comparisons)
    raw_frames(candidate, args)
    if comparisons is not None:
        confirmed = sum(1 for c in comparisons if c["regression"])
        uncertain = sum(1 for c in comparisons if c["verdict"] == "uncertain")
        print(f"{confirmed} confirmed regression(s), {uncertain} uncertain, "
              f"{len(comparisons)} metric(s) compared")
    contaminated = [f"{s['name']}: {reason}" for s in candidate["scenarios"]
                    for reason in s.get("contamination", [])]
    if contaminated:
        print("contaminated measurements (not comparison-grade): " + "; ".join(contaminated),
              file=sys.stderr)
    if errors:
        print("invalid scenarios: " + ", ".join(errors), file=sys.stderr)
        return 0 if args.no_fail else 1
    print(f"all {len(candidate['scenarios'])} scenarios valid; report {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
