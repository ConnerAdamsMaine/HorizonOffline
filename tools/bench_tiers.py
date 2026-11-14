#!/usr/bin/env python3
"""The four benchmark/verification tiers (docs/benchmark-suite.md, "Tiers").

Every change runs tier 1: formatting, Clippy on the benchmark crate, its tests and the Python
statistics/schema tests. Tier 2 adds a real game: the smoke gameplay scenarios plus the workload
assertions. Tier 3 runs repeated gameplay, scaling workloads and a comparison against the approved
baseline. Tier 4 is the long soak and high-density work, run on release candidates and by hand.

    python3 tools/bench_tiers.py --tier 1
    python3 tools/bench_tiers.py --tier 2 --build target/release
    python3 tools/bench_tiers.py --tier 3 --baseline benchmarks/gameplay/baseline-qualified.json
    python3 tools/bench_tiers.py --tier 4 --large
    python3 tools/bench_tiers.py --tier all --dry-run

Each tier prints the commands it runs and stops at the first failure. Performance tiers write their
report under `benchmarks/gameplay/`; a run this tool considers contaminated is printed but does not
fail a correctness tier.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASELINE = ROOT / "benchmarks/gameplay/baseline-qualified.json"
DEFAULT_REPORT_DIR = ROOT / "benchmarks/gameplay"


def commands(tier: int, args) -> list[list[str]]:
    python = sys.executable
    binary = args.build
    if tier == 1:
        return [
            ["cargo", "fmt", "--all", "--", "--check"],
            ["cargo", "clippy", "-p", "horizon-bench", "--all-targets", "--", "-D", "warnings"],
            ["cargo", "test", "-p", "horizon-bench", "--lib", "--bins"],
            [python, "-m", "unittest", "tests.test_gameplay_bench", "tests.test_perf_bench",
             "tests.test_cargo_build", "tests.test_bench_tiers"],
        ]
    if tier == 2:
        return [
            ["cargo", "test", "-p", "horizon-bench", "--lib", "--bins"],
            [python, "tools/gameplay_bench.py", "--smoke", "--repeats", "1", "--seconds", "3",
             "--warmup-seconds", "1", "--cooldown-seconds", "0", "--build", binary,
             "--label", "tier2-smoke", "--out-dir", str(DEFAULT_REPORT_DIR), *args.extra],
        ]
    if tier == 3:
        report = DEFAULT_REPORT_DIR / "tier3-latest.json"
        run = [python, "tools/gameplay_bench.py", "--build", binary, "--repeats",
               str(args.repeats), "--seconds", "8",
               "--entity-counts", "0,100,250",
               "--redstone-sizes", "small,medium,large",
               "--render-distances", "8,12",
               "--scenarios", "idle,walk,explore,mine_place,crafting,combat,redstone,entities,"
               "world_ops,mixed",
               "--label", "tier3", "--out-dir", str(DEFAULT_REPORT_DIR),
               "--out", str(report), *args.extra]
        out = [python, "tools/gameplay_bench.py", "--compare", str(args.baseline), str(report),
               "--threshold", str(args.threshold), "--require-significance"]
        if args.baseline.exists():
            return [run, out]
        print(f"tier 3: no baseline at {args.baseline}; running without a comparison", file=sys.stderr)
        return [run]
    if tier == 4:
        return [
            [python, "tools/gameplay_bench.py", "--build", binary, "--repeats",
             str(args.repeats), "--seconds", "15",
             "--include", "memory_soak,overhead",
             "--entity-counts", "500,1000,2000", "--large",
             "--redstone-sizes", "extreme",
             "--resolutions", "1280x720,1920x1080",
             "--soak-seconds", str(args.soak_seconds),
             "--label", "tier4", "--out-dir", str(DEFAULT_REPORT_DIR), *args.extra],
        ]
    raise SystemExit(f"unknown tier {tier}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tier", default="1", choices=["1", "2", "3", "4", "all"])
    parser.add_argument("--build", default="target/release", help="folder holding the game binary")
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--threshold", type=float, default=5.0)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--soak-seconds", type=float, default=300.0)
    parser.add_argument("--large", action="store_true", help="tier 4's high-density workloads")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("extra", nargs=argparse.REMAINDER, help="arguments after -- go to gameplay_bench")
    args = parser.parse_args(argv)
    args.extra = [a for a in args.extra if a != "--"]

    tiers = [1, 2, 3, 4] if args.tier == "all" else [int(args.tier)]
    env = dict(os.environ)
    env.setdefault("HORIZON_TELEMETRY_URL", "off")
    for tier in tiers:
        print(f"=== tier {tier} ===", flush=True)
        for command in commands(tier, args):
            printable = " ".join(str(c) for c in command)
            print(printable, flush=True)
            if args.dry_run:
                continue
            result = subprocess.run(command, cwd=ROOT, env=env)
            if result.returncode != 0:
                print(f"tier {tier}: {command[1] if len(command) > 1 else command[0]} failed "
                      f"({result.returncode})", file=sys.stderr)
                return result.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
