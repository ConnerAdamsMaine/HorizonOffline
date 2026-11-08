import contextlib
import io
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import sync_upstream as su


@unittest.skipUnless(shutil.which("git"), "requires Git")
class SyncUpstreamTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="horizon-sync-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.upstream = self.root / "upstream.git"
        self.origin = self.root / "fork.git"
        self.writer = self.root / "writer"
        for remote in (self.upstream, self.origin):
            su.git(self.root, "init", "--bare", "--initial-branch=main", str(remote))
        su.git(self.root, "init", "--initial-branch=main", str(self.writer))
        self.identity(self.writer)
        self.commit(self.writer, "shared.txt", "base\n")
        su.git(self.writer, "remote", "add", "upstream", str(self.upstream))
        su.git(self.writer, "remote", "add", "origin", str(self.origin))
        su.git(self.writer, "push", "upstream", "main")
        su.git(self.writer, "push", "origin", "main")
        self.fork = self.root / "checkout"
        su.git(self.root, "clone", str(self.origin), str(self.fork))
        self.identity(self.fork)

    def identity(self, root):
        su.git(root, "config", "user.name", "Sync fixture")
        su.git(root, "config", "user.email", "fixture@example.invalid")

    def commit(self, root, name, contents):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")
        su.git(root, "add", name)
        su.git(root, "commit", "-m", "fixture change")
        return su.git(root, "rev-parse", "HEAD").stdout.strip()

    def origin_head(self):
        return su.git(self.root, "--git-dir", str(self.origin), "rev-parse", "main").stdout.strip()

    def test_already_synced_fork_keeps_its_own_commits(self):
        before = self.commit(self.fork, "offline.txt", "fork customization\n")
        su.git(self.fork, "push", "origin", "main")
        result = su.sync(self.fork, str(self.upstream))
        self.assertEqual(result["status"], "up_to_date")
        self.assertEqual(self.origin_head(), before)
        self.assertEqual((self.fork / "offline.txt").read_text(), "fork customization\n")

    def test_clean_merge_preserves_fork_changes_and_pushes_upstream_code(self):
        self.commit(self.fork, "offline.txt", "fork customization\n")
        su.git(self.fork, "push", "origin", "main")
        upstream = self.commit(self.writer, "crates/demo/src/lib.rs", "pub fn upstream_feature() {}\n")
        su.git(self.writer, "push", "upstream", "main")
        result = su.sync(self.fork, str(self.upstream))
        self.assertEqual(result["status"], "updated")
        self.assertTrue(result["launcher_changed"])
        self.assertEqual(self.origin_head(), result["head"])
        self.assertEqual((self.fork / "offline.txt").read_text(), "fork customization\n")
        self.assertEqual((self.fork / "crates/demo/src/lib.rs").read_text(), "pub fn upstream_feature() {}\n")
        self.assertEqual(su.git(self.fork, "merge-base", "--is-ancestor", upstream, "HEAD").returncode, 0)

    def test_docs_only_merge_does_not_request_a_launcher_release(self):
        self.commit(self.writer, "docs/change.md", "upstream documentation\n")
        su.git(self.writer, "push", "upstream", "main")
        result = su.sync(self.fork, str(self.upstream))
        self.assertEqual(result["status"], "updated")
        self.assertFalse(result["launcher_changed"])

    def test_conflict_leaves_the_fork_and_remote_unchanged(self):
        before = self.commit(self.fork, "shared.txt", "fork version\n")
        su.git(self.fork, "push", "origin", "main")
        self.commit(self.writer, "shared.txt", "upstream version\n")
        su.git(self.writer, "push", "upstream", "main")
        result = su.sync(self.fork, str(self.upstream))
        self.assertEqual(result["status"], "conflict")
        self.assertEqual(result["conflicts"], ["shared.txt"])
        self.assertEqual(self.origin_head(), before)
        self.assertEqual(su.git(self.fork, "rev-parse", "HEAD").stdout.strip(), before)
        self.assertEqual((self.fork / "shared.txt").read_text(), "fork version\n")
        self.assertEqual(su.git(self.fork, "status", "--porcelain").stdout, "")

    def test_dirty_checkout_and_unpublished_work_are_preserved(self):
        path = self.fork / "local.txt"
        path.write_text("local work\n")
        with self.assertRaisesRegex(ValueError, "clean checkout"):
            su.sync(self.fork, str(self.upstream))
        self.assertEqual(path.read_text(), "local work\n")
        before = self.commit(self.fork, "local.txt", "unpublished work\n")
        with self.assertRaisesRegex(ValueError, "match origin/main"):
            su.sync(self.fork, str(self.upstream))
        self.assertEqual(su.git(self.fork, "rev-parse", "HEAD").stdout.strip(), before)
        self.assertEqual(path.read_text(), "unpublished work\n")

    def test_conflicted_cli_reports_failure_and_leaves_the_fork_clean(self):
        before = self.commit(self.fork, "shared.txt", "fork version\n")
        su.git(self.fork, "push", "origin", "main")
        self.commit(self.writer, "shared.txt", "upstream version\n")
        su.git(self.writer, "push", "upstream", "main")
        output, error = io.StringIO(), io.StringIO()
        github_output = self.root / "github-output"
        summary = self.root / "summary"
        args = ["sync_upstream.py", "--root", str(self.fork), "--upstream", str(self.upstream)]
        with mock.patch("sys.argv", args), mock.patch.dict(su.os.environ, {
            "GITHUB_OUTPUT": str(github_output), "GITHUB_STEP_SUMMARY": str(summary),
        }), contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            code = su.main()
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(output.getvalue())["conflicts"], ["shared.txt"])
        self.assertIn("merge conflicts", error.getvalue())
        self.assertIn("status=conflict\n", github_output.read_text())
        self.assertIn("shared.txt", summary.read_text())
        self.assertEqual(self.origin_head(), before)
        self.assertEqual(su.git(self.fork, "status", "--porcelain").stdout, "")

    def test_concurrent_remote_push_is_not_overwritten(self):
        self.commit(self.writer, "upstream.txt", "upstream change\n")
        su.git(self.writer, "push", "upstream", "main")
        other = self.root / "other-checkout"
        su.git(self.root, "clone", str(self.origin), str(other))
        self.identity(other)
        concurrent = self.commit(other, "concurrent.txt", "another contributor\n")
        real_git = su.git

        def race(root, *args, **kwargs):
            if args and args[0] == "push" and Path(root) == self.fork:
                real_git(other, "push", "origin", "main")
            return real_git(root, *args, **kwargs)

        with mock.patch.object(su, "git", side_effect=race):
            with self.assertRaises(subprocess.CalledProcessError):
                su.sync(self.fork, str(self.upstream))
        self.assertEqual(self.origin_head(), concurrent)


if __name__ == "__main__":
    unittest.main()
