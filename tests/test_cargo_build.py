"""tools/cargo_build.py: the resource-aware job count and the exact Cargo command."""

import unittest
from unittest import mock

from tools import cargo_build as cb


class JobTests(unittest.TestCase):
    def test_a_large_machine_uses_every_core(self):
        self.assertEqual(cb.default_jobs(16, 64 * 1024, "fast"), 16)

    def test_a_small_machine_reduces_concurrency_for_expensive_profiles(self):
        # 8 GiB, 8 cores: fast's 1.8 GiB per job leaves 4 jobs after the 25% reserve.
        self.assertEqual(cb.default_jobs(8, 8 * 1024, "fast"), 3)
        # release-max needs a large machine.
        self.assertLessEqual(cb.default_jobs(8, 8 * 1024, "release-max"), 1)

    def test_unknown_memory_does_not_explode_the_expensive_profiles(self):
        self.assertEqual(cb.default_jobs(12, None, "dev"), 12)
        self.assertEqual(cb.default_jobs(12, None, "release"), 4)
        self.assertEqual(cb.default_jobs(1, None, "release"), 1)

    def test_available_memory_lowers_the_job_count(self):
        # 48 GiB installed but only 8 GiB free: two big builds must not be started on the same box.
        self.assertEqual(cb.default_jobs(12, 48 * 1024, "release", 8 * 1024), 2)
        self.assertEqual(cb.default_jobs(12, 48 * 1024, "release"), 12)
        # An impossible report (more free than installed) cannot raise it past the installed RAM.
        self.assertEqual(cb.default_jobs(12, 8 * 1024, "release", 64 * 1024), 2)

    def test_per_job_override_and_unknown_profile(self):
        with mock.patch.dict(cb.PER_JOB_MB, {"fast": 1024}):
            self.assertEqual(cb.default_jobs(10, 4096, "fast"), 3)
        with self.assertRaises(cb.BuildError):
            cb.check_profile("nope")


class CommandTests(unittest.TestCase):
    def test_command_is_locked_and_names_the_game_bins(self):
        command = cb.build_command("release", ["--no-default-features"], 4)
        self.assertIn("build", command)
        self.assertIn("--locked", command)
        self.assertIn("--profile", command)
        self.assertIn("release", command)
        self.assertIn("--jobs", command)
        self.assertIn("4", command)
        self.assertIn("--no-default-features", command)
        self.assertIn("horizon-client", command)
        self.assertIn("horizon-ctl", command)

    def test_environment_sets_jobs_and_disables_incremental_for_release(self):
        env = cb.build_env("release", 3, {"KEEP": "yes"})
        self.assertEqual(env["CARGO_BUILD_JOBS"], "3")
        self.assertEqual(env["CARGO_INCREMENTAL"], "0")
        self.assertEqual(env["KEEP"], "yes")
        env = cb.build_env("fast", 2, {})
        self.assertEqual(env["CARGO_INCREMENTAL"], "1")

    def test_profiles_are_the_documented_set(self):
        self.assertEqual(set(cb.PER_JOB_MB), {"dev", "fast", "release", "bench", "release-max"})

    def test_the_dry_run_description_names_free_memory(self):
        text = cb.describe("bench", 6, 48 * 1024, 12, 30 * 1024)
        self.assertIn("6 job(s)", text)
        self.assertIn("30720 MiB free", text)
        self.assertIn("14400 MiB", text)


if __name__ == "__main__":
    unittest.main()
