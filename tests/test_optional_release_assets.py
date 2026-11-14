"""Execute release shell steps with optional archives present and absent."""

import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {
    "horizon-linux-x86_64.tar.gz", "horizon-windows-x64.zip", "horizon-macos-arm64.zip",
    "horizon-macos-x64.zip", "horizon-server-linux-x86_64.tar.gz", "horizon-source.tar.gz",
}
OPTIONAL = ("horizon-windows-arm64.zip", "horizon-linux-musl-x86_64.tar.gz")


def shell_tools():
    """A shell and the GNU tools the release steps need, as absolute paths.

    Windows resolves a bare `bash` through CreateProcess's own search order, which finds
    `System32\\bash.exe` (the WSL launcher) before Git's bash on PATH; WSL's launcher fails here with
    `execvpe(/bin/bash) failed`. Running the absolute path `shutil.which` found keeps the check
    attached to the POSIX shell that is actually installed, and putting its folder first on PATH
    makes the `bash` calls inside the workflow step resolve the same way.
    """
    found = {name: shutil.which(name) for name in ("bash", "openssl", "sha256sum")}
    if not all(found.values()):
        return None
    env = dict(os.environ)
    env["PATH"] = str(Path(found["bash"]).parent) + os.pathsep + env.get("PATH", "")
    try:
        probe = subprocess.run([found["bash"], "-c", "openssl version > /dev/null"], env=env,
                               text=True, capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    return found["bash"], env if probe.returncode == 0 else None


def run_step(containing):
    workflow = (ROOT / ".github/workflows/nightly-build.yml").read_text()
    for match in re.finditer(r"^        run: \|\n((?:          .*\n|\n)+)", workflow, re.MULTILINE):
        script = "\n".join(line[10:] for line in match[1].splitlines())
        if containing in script:
            return script
    raise AssertionError(f"no workflow step containing {containing}")


TOOLS = shell_tools()


@unittest.skipUnless(TOOLS, "release shell checks require a runnable POSIX bash, OpenSSL and sha256sum")
class OptionalReleaseAssetsTests(unittest.TestCase):
    def test_sign_and_publish_with_each_optional_archive_combination(self):
        bash, path_env = TOOLS
        for mask in range(4):
            with self.subTest(mask=mask), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                dist = root / "dist"
                dist.mkdir()
                present = REQUIRED | {name for i, name in enumerate(OPTIONAL) if mask & (1 << i)}
                for name in present:
                    (dist / name).write_bytes(name.encode())
                script_dir = root / "tools/ci"
                script_dir.mkdir(parents=True)
                shutil.copy(ROOT / "tools/ci/sign_release.sh", script_dir)
                # The steps' own env from nightly-build.yml: SHORT is the commit the title and
                # SHA256SUMS.v2.sig name (ALSO_FOR, nightly-<date>-<short>).
                env = dict(path_env, EPHEMERAL="yes", SHA="0123456789abcdef", SHORT="0123456", DATE="2026-11-04",
                           ALSO_FOR="nightly-2026-11-04-0123456", SOURCE_TAG="nightly-test",
                           RELEASE_SIGNING_KEY="", RELEASE_SIGNING_KEY_NEXT="")
                signed = subprocess.run([bash, "-e", "-c", run_step("sign_release.sh nightly")],
                                        cwd=root, env=env, text=True, capture_output=True)
                self.assertEqual(signed.returncode, 0, signed.stderr)
                sums = {name.lstrip("*"): digest for digest, name in
                        (line.split() for line in (dist / "SHA256SUMS").read_text().splitlines())}
                self.assertEqual(sums, {name: hashlib.sha256(name.encode()).hexdigest() for name in present})
                self.assertTrue((dist / "SHA256SUMS.sig").stat().st_size)
                self.assertTrue((dist / "SHA256SUMS.v2.sig").stat().st_size)
                (dist / "smoke-test.json").write_text("{}")
                (dist / "nightly-notes.md").write_text("test")
                # Isolate GitHub and tag rotation; validate the exact attachment arguments
                # produced by the real workflow, including paths with display labels.
                stubs = '''
python3() { :; }
gh() {
  for arg in "$@"; do
    case "$arg" in dist/*)
      file=${arg%%#*}
      test -f "$file" || return 1
      printf '%s\\n' "$file" >> published
    esac
  done
}
'''
                published = subprocess.run([bash, "-e", "-c", stubs + run_step("gh release create nightly")],
                                           cwd=root, env=env, text=True, capture_output=True)
                self.assertEqual(published.returncode, 0, published.stderr)
                files = {Path(name).name for name in (root / "published").read_text().splitlines()}
                self.assertEqual(files, present | {"SHA256SUMS", "SHA256SUMS.sig", "SHA256SUMS.v2.sig", "smoke-test.json",
                                                   "nightly-notes.md"})
                for name in set(OPTIONAL) - present:
                    self.assertIn(f"::warning::{name} is missing", signed.stdout)
                    self.assertIn(f"::warning::{name} is missing", published.stdout)
