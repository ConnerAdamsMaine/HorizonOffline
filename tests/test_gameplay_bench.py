"""tools/gameplay_bench.py: statistics, comparison, validation and the scenario catalogue (no game)."""

import math
import unittest

from tools import gameplay_bench as gb


def scenario(name, samples, checks=None, frames=None):
    return {"name": name, "category": "test", "seconds": 1.0, "repeats": 1,
            "samples": samples, "checks": checks or [{"name": "ran", "expected": "1", "actual": "1",
                                                      "passed": True}],
            "frames": frames or [], "notes": []}


def suite(scenarios):
    return {"format": gb.SUITE_FORMAT, "version": gb.SUITE_VERSION, "scenarios": scenarios}


class StatisticsTests(unittest.TestCase):
    def test_summary_has_mean_stdev_and_ci(self):
        self.assertIsNone(gb.summary([]))
        one = gb.summary([5.0])
        self.assertEqual((one["n"], one["mean"], one["stdev"], one["ci95"]), (1, 5.0, None, None))
        many = gb.summary([2.0, 4.0, 6.0])
        self.assertEqual((many["mean"], many["min"], many["max"]), (4.0, 2.0, 6.0))
        self.assertEqual(many["stdev"], 2.0)
        self.assertAlmostEqual(many["ci95"], 4.969, places=3)

    def test_percentile_is_nearest_rank(self):
        self.assertEqual(gb.percentile([1, 2, 3, 4, 5], 0.5), 3)
        self.assertEqual(gb.percentile([1, 2, 3, 4, 5], 0.99), 5)
        self.assertIsNone(gb.percentile([], 0.5))

    def test_slope_of_a_flat_memory_trace_is_zero(self):
        samples = [(0.0, 100 * 2 ** 20), (60.0, 100 * 2 ** 20), (120.0, 100 * 2 ** 20)]
        self.assertAlmostEqual(gb.slope_mb_per_min(samples), 0.0)
        growing = [(0.0, 100 * 2 ** 20), (60.0, 110 * 2 ** 20), (120.0, 120 * 2 ** 20)]
        self.assertAlmostEqual(gb.slope_mb_per_min(growing), 10.0)


class DirectionTests(unittest.TestCase):
    def test_higher_is_better_only_for_throughput(self):
        for metric in ("render.avg_fps", "tick.tps", "chunks.generated_per_s"):
            self.assertEqual(gb.direction(metric), "higher", metric)
        for metric in ("tick.mspt", "render.p99_ms", "process.rss_peak_mb", "world.generated_chunks"):
            self.assertEqual(gb.direction(metric), "lower", metric)


class ComparisonTests(unittest.TestCase):
    def test_faster_frames_are_an_improvement_and_slower_frames_a_regression(self):
        before = suite([scenario("idle", {"render.avg_fps": [120.0, 121.0, 119.0]})])
        after = suite([scenario("idle", {"render.avg_fps": [90.0, 91.0, 89.0]})])
        change = gb.compare_suites(before, after)[0]
        self.assertEqual(change["change_pct"], -25.0)
        self.assertEqual(change["verdict"], "regression")
        self.assertTrue(change["regression"])
        self.assertFalse(gb.compare_suites(after, before)[0]["regression"])

    def test_latency_regression_and_threshold(self):
        before = suite([scenario("idle", {"tick.mspt": [10.0, 10.0, 10.0]})])
        after = suite([scenario("idle", {"tick.mspt": [10.2, 10.2, 10.2]})])
        self.assertFalse(gb.compare_suites(before, after)[0]["regression"], "2% under 5%")
        worse = suite([scenario("idle", {"tick.mspt": [12.0, 12.0, 12.0]})])
        change = gb.compare_suites(before, worse)[0]
        self.assertTrue(change["regression"])
        self.assertTrue(change["significant"])

    def test_significance_needs_repeats(self):
        before = suite([scenario("idle", {"tick.mspt": [10.0]})])
        after = suite([scenario("idle", {"tick.mspt": [40.0]})])
        change = gb.compare_suites(before, after)[0]
        self.assertIsNone(change["significant"])
        # A 300% difference on one sample each is not a confirmed regression.
        self.assertEqual(change["verdict"], "uncertain")
        self.assertFalse(change["regression"])

    def test_a_change_inside_the_noise_is_uncertain(self):
        before = suite([scenario("idle", {"tick.mspt": [10.0, 14.0, 12.0]})])
        after = suite([scenario("idle", {"tick.mspt": [13.0, 17.0, 15.0]})])
        change = gb.compare_suites(before, after)[0]
        self.assertGreater(change["change_pct"], 5.0)
        self.assertEqual(change["verdict"], "uncertain")
        self.assertFalse(change["regression"])
        self.assertGreater(change["noise_pct"], 5.0)

    def test_scenarios_or_metrics_on_one_side_only_are_skipped(self):
        before = suite([scenario("idle", {"tick.mspt": [10.0]}), scenario("gone", {"tick.mspt": [1.0]})])
        after = suite([scenario("idle", {"render.avg_fps": [60.0]})])
        self.assertEqual(gb.compare_suites(before, after), [])

    def test_zero_baseline_does_not_divide_by_zero(self):
        before = suite([scenario("idle", {"play.actions": [0.0]})])
        after = suite([scenario("idle", {"play.actions": [10.0]})])
        self.assertEqual(gb.compare_suites(before, after)[0]["change_pct"], 0.0)


class ValidityTests(unittest.TestCase):
    def test_a_failed_check_invalidates_only_that_scenario(self):
        good = scenario("idle", {"tick.tps": [20.0]})
        bad = scenario("walk", {"play.distance_blocks": [0.0]},
                       [{"name": "player moved", "expected": "> 3", "actual": "0", "passed": False}])
        report = suite([good, bad])
        self.assertTrue(gb.compare_suites(report, report) is not None)
        self.assertFalse(bad["checks"][0]["passed"])
        # The runner's finish() is what marks it; test the same rule directly.
        done = gb.finish(bad)
        self.assertFalse(done["valid"])
        self.assertTrue(gb.finish(good)["valid"])

    def test_scenario_catalogue_is_complete(self):
        self.assertTrue(set(gb.SCENARIOS) <= set(gb.RUNNERS))
        self.assertTrue(set(gb.SMOKE_SCENARIOS) <= set(gb.RUNNERS))
        self.assertTrue(set(gb.EXTRA_SCENARIOS) <= set(gb.RUNNERS))
        self.assertFalse(set(gb.EXTRA_SCENARIOS) & set(gb.SCENARIOS),
                         "opt-in workloads must not run in the default suite")
        for name in gb.SCENARIOS:
            self.assertTrue(callable(gb.RUNNERS[name]), name)

    def test_scaling_names_resolve_and_large_workloads_need_the_flag(self):
        runner, extra = gb.runner_for("entities_500")
        self.assertIs(runner, gb.scenario_entities)
        self.assertEqual(extra, {"count": 500})
        runner, extra = gb.runner_for("redstone_large")
        self.assertIs(runner, gb.scenario_redstone_scale)
        self.assertEqual(extra, {"size": "large"})

        class Args:
            smoke = False
            scenarios = ""
            include = ""
            entity_counts = "0,100,250,500"
            redstone_sizes = ""
            render_matrix = False
            large = False

        with self.assertRaises(SystemExit):
            gb.selected_scenarios(Args())
        args = Args()
        args.large = True
        names = gb.selected_scenarios(args)
        self.assertIn("entities_500", names)
        for count in (0, 100, 250):
            self.assertIn(f"entities_{count}", names)
        self.assertNotIn("entities", names)


class TraceTests(unittest.TestCase):
    def test_top_spans_are_ranked_by_wall_time_and_named(self):
        import json
        import tempfile
        from pathlib import Path
        events = [
            {"ph": "M", "name": "thread_name", "tid": 1, "args": {"name": "Server thread"}},
            {"ph": "X", "name": "tick", "tid": 1, "dur": 4000},
            {"ph": "X", "name": "tick", "tid": 1, "dur": 6000},
            {"ph": "X", "name": "stream", "tid": 2, "dur": 1000},
        ]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "trace.json"
            path.write_text(json.dumps(events))
            summary = gb.summarize_trace(path)
        self.assertEqual(summary["events"], 4)
        top = summary["top_spans"][0]
        self.assertEqual((top["name"], top["count"]), ("tick", 2))
        self.assertEqual(top["wall_ms"], 10.0)
        self.assertEqual(top["thread"], "Server thread")

    def test_trace_selection_is_bounded_to_one_repeat_and_named_scenarios(self):
        class Args:
            trace_dir = "traces"
            trace_repeat = 0
            trace_scenarios = "idle,entities"

        args = Args()
        self.assertIsNotNone(gb.trace_path_for(args, "idle", 0))
        self.assertIsNotNone(gb.trace_path_for(args, "entities_500", 0))
        self.assertIsNone(gb.trace_path_for(args, "walk", 0))
        self.assertIsNone(gb.trace_path_for(args, "idle", 1))
        args.trace_dir = None
        self.assertIsNone(gb.trace_path_for(args, "idle", 0))


class QualificationTests(unittest.TestCase):
    def test_outliers_are_reported_and_samples_are_not_dropped(self):
        values = [10.0, 10.1, 9.9, 10.05, 40.0]
        stat = gb.statistics_of(values)
        self.assertEqual(stat["n"], 5)
        self.assertEqual(stat["outlier_count"], 1)
        self.assertEqual(stat["outliers"][0]["value"], 40.0)
        self.assertEqual(stat["outliers"][0]["side"], "high")
        self.assertEqual(stat["outlier_method"], "tukey-1.5-iqr")
        self.assertEqual(stat["median"], 10.05)
        self.assertIsNotNone(stat["cv_pct"])
        self.assertEqual(gb.statistics_of([1.0, 2.0, 100.0])["outlier_count"], 0)
        self.assertIsNone(gb.statistics_of([]))

    def test_contamination_names_the_machine_state_and_collapsed_tick_rate(self):
        class Args:
            pass
        args = Args()
        run = {"samples": {"run.wall_s": [4.0], "tick.tps": [8.0]}}
        reasons = gb.contamination(run, 48_000, {"cpu_percent": 40.0, "available_mb": 600.0},
                                   {"cpu_percent": 0.0, "available_mb": 20_000.0}, args, 40,
                                   expected_frames_s=100.0)
        self.assertTrue(any("busy" in r for r in reasons), reasons)
        self.assertTrue(any("MiB free" in r for r in reasons), reasons)
        self.assertTrue(any("tick rate" in r for r in reasons), reasons)
        self.assertTrue(any("frames/s" in r for r in reasons), reasons)
        self.assertEqual(gb.contamination({"samples": {"run.wall_s": [4.0], "tick.tps": [20.0]}},
                                          48_000, {"cpu_percent": 2.0, "available_mb": 20_000},
                                          {"cpu_percent": 1.0, "available_mb": 19_000}, args, 400,
                                          expected_frames_s=50.0), [])

    def test_merge_run_keeps_each_repeat_and_its_failures(self):
        suite = {"scenarios": []}
        first = {"name": "idle", "category": "renderer", "seconds": 4.0,
                 "samples": {"tick.tps": [20.0]},
                 "checks": [{"name": "frames drawn", "expected": "> 10", "actual": "400", "passed": True}],
                 "frames": [], "notes": [], "contamination": [], "valid": True}
        second = {"name": "idle", "category": "renderer", "seconds": 4.0,
                  "samples": {"tick.tps": [19.0]},
                  "checks": [{"name": "frames drawn", "expected": "> 10", "actual": "0", "passed": False}],
                  "frames": [], "notes": [], "contamination": ["machine 30% busy"], "valid": False}
        gb.merge_run(suite, first, 0)
        merged = gb.merge_run(suite, second, 1)
        self.assertEqual(merged["samples"]["tick.tps"], [20.0, 19.0])
        self.assertEqual(merged["repeats"], 2)
        self.assertEqual(len(merged["runs"]), 2)
        self.assertEqual(merged["runs"][1]["samples"]["tick.tps"], [19.0])
        self.assertTrue(any(c["name"].startswith("repeat 2:") for c in merged["checks"] if not c["passed"]))
        self.assertTrue(any("repeat 2" in r for r in merged["contamination"]))
        self.assertFalse(merged["valid"])


if __name__ == "__main__":
    unittest.main()
