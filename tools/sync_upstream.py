"""Merge upstream main into a clean fork checkout and push only conflict-free merges."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

UPSTREAM = "https://github.com/horizon-rust/horizon.git"


def git(root, *args, check=True):
    return subprocess.run(["git", *args], cwd=root, check=check, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def sync(root, upstream=UPSTREAM):
    root = Path(root)
    if git(root, "branch", "--show-current").stdout.strip() != "main":
        raise ValueError("Sync requires the main branch.")
    if git(root, "status", "--porcelain").stdout:
        raise ValueError("Sync requires a clean checkout; local work was not changed.")
    git(root, "fetch", "--no-tags", "origin", "main")
    before = git(root, "rev-parse", "HEAD").stdout.strip()
    if before != git(root, "rev-parse", "origin/main").stdout.strip():
        raise ValueError("The checkout must match origin/main. Retry from a fresh checkout.")
    git(root, "fetch", "--no-tags", upstream, "main:refs/remotes/upstream/main")
    upstream_head = git(root, "rev-parse", "upstream/main").stdout.strip()
    result = {"status": "up_to_date", "head": before, "upstream": upstream_head,
              "conflicts": [], "launcher_changed": False}
    ancestor = git(root, "merge-base", "--is-ancestor", upstream_head, "HEAD", check=False)
    if ancestor.returncode == 0:
        return result
    if ancestor.returncode != 1:
        ancestor.check_returncode()
    merged = git(root, "merge", "--no-ff", "--no-commit", upstream_head, check=False)
    if merged.returncode:
        conflicts = git(root, "diff", "--name-only", "--diff-filter=U").stdout.splitlines()
        if conflicts:
            git(root, "merge", "--abort")
            result.update(status="conflict", conflicts=conflicts)
            return result
        merged.check_returncode()
    changed = git(root, "diff", "--cached", "--name-only").stdout.splitlines()
    result["launcher_changed"] = any(
        path.startswith(("launcher/", "crates/", "packaging/icons/")) or path in
        ("tools/setup_launcher.ps1", ".github/workflows/offline-launcher.yml")
        for path in changed)
    git(root, "commit", "-m", "Merge upstream main into offline fork",
        "-m", f"Automatic conflict-free sync from horizon-rust/horizon@{upstream_head}.",
        "-m", "Co-Authored-By: OpenCode (GPT-6.1 Sol) <noreply@openai.com>")
    # A concurrent fork push is rejected by Git. Never force-push or overwrite its work.
    git(root, "push", "origin", "HEAD:main")
    result.update(status="updated", head=git(root, "rev-parse", "HEAD").stdout.strip())
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--upstream", default=UPSTREAM)
    args = parser.parse_args()
    try:
        result = sync(args.root, args.upstream)
    except (ValueError, subprocess.CalledProcessError) as error:
        print(getattr(error, "stderr", None) or str(error), file=sys.stderr)
        return 1
    print(json.dumps(result))
    if output := os.environ.get("GITHUB_OUTPUT"):
        with open(output, "a", encoding="utf-8") as out:
            for key in ("status", "head", "launcher_changed"):
                value = str(result[key]).lower() if isinstance(result[key], bool) else result[key]
                out.write(f"{key}={value}\n")
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(summary, "a", encoding="utf-8") as out:
            out.write(f"## Upstream sync: {result['status']}\n\n")
            out.write(f"Upstream: `{result['upstream']}`\n\nFork: `{result['head']}`\n")
            if result["conflicts"]:
                out.write("\nThe fork was not changed. Resolve these files manually:\n\n```text\n")
                out.write("\n".join(result["conflicts"]) + "\n```\n")
    if result["status"] == "conflict":
        print("Upstream sync blocked by merge conflicts: " + ", ".join(result["conflicts"]),
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
