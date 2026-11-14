"""tools/bench_tiers.py: the commands each verification tier runs, without running them."""

import tempfile
import unittest
from pathlib import Path

from tools import bench_tiers as bt


class Args:
    build = "target/release"
    baseline = Path("benchmarks/gameplay/baseline-qualified.json")
    threshold = 5.0
    repeats = 3
    soak_seconds = 300.0
    large = False
    extra = []


class TierCommandTests(unittest.TestCase):
    def test_tier_one_is_source_only(self):
        commands = bt.commands(1, Args())
        joined = [" ".join(c) for c in commands]
        self.assertTrue(any("fmt" in c for c in joined))
        self.assertTrue(any("clippy" in c for c in joined))
        self.assertTrue(any("horizon-bench" in c and "test" in c for c in joined))
        self.assertTrue(any("test_gameplay_bench" in c for c in joined))
        for command in joined:
            self.assertNotIn("gameplay_bench.py --", command, "tier 1 must not start a game")

    def test_tier_two_runs_the_smoke_scenarios(self):
        commands = bt.commands(2, Args())
        run = next(c for c in commands if "tools/gameplay_bench.py" in " ".join(c))
        self.assertIn("--smoke", run)
        self.assertIn("--repeats", run)

    def test_tier_three_compares_against_a_baseline_when_present(self):
        with tempfile.TemporaryDirectory() as folder:
            baseline = Path(folder) / "baseline.json"
            baseline.write_text("{}")
            args = Args()
            args.baseline = baseline
            commands = bt.commands(3, args)
        self.assertEqual(len(commands), 2)
        compare = " ".join(commands[1])
        self.assertIn("--compare", compare)
        self.assertIn(str(baseline), compare)
        self.assertIn("--require-significance", compare)

    def test_large_workloads_are_opt_in(self):
        commands = bt.commands(4, Args())
        run = " ".join(commands[0])
        self.assertIn("--large", run)
        self.assertIn("2000", run)
        self.assertIn("memory_soak", run)


if __name__ == "__main__":
    unittest.main()
