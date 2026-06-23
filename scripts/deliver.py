#!/usr/bin/env python3
"""Deliver pinq-doq rules/ and skills/ into a consumer's .claude/ — cross-platform.

Run from the consumer project root:

    python .pinq-doq/scripts/deliver.py

What it does (idempotent — `update` just re-runs it):
- Mirrors `.pinq-doq/rules/` -> `.claude/rules/` (full overwrite + prune; this dir is
  owned entirely by pinq-doq).
- Merges each `.pinq-doq/skills/<name>/` into `.claude/skills/`, pruning only
  pinq-doq-managed skills that no longer ship upstream (tracked in
  `.claude/skills/.pinq-doq-skills`) — the project's own skills are never touched.
- Writes `.claude/.pinq-doq-version` (source SHA + UTC timestamp) so staleness is detectable.

Standard library only, so it runs the same on macOS, Linux, and Windows (incl. native
PowerShell) — no `rsync`/`cp` dependency.
"""
import argparse
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

IGNORE = shutil.ignore_patterns(".git", "__pycache__", "*.pyc")


def mirror_rules(mount: Path, claude: Path) -> None:
    src = mount / "rules"
    if not src.is_dir():
        sys.exit(f"error: {src} not found — is pinq-doq mounted at the given path?")
    dst = claude / "rules"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=IGNORE)


def merge_skills(mount: Path, claude: Path) -> list:
    src = mount / "skills"
    dst = claude / "skills"
    dst.mkdir(parents=True, exist_ok=True)
    manifest = dst / ".pinq-doq-skills"
    upstream = sorted(p.name for p in src.iterdir() if p.is_dir()) if src.is_dir() else []
    # Prune pinq-doq-managed skills that no longer ship upstream.
    if manifest.exists():
        for name in manifest.read_text(encoding="utf-8").split():
            if name and name not in upstream:
                shutil.rmtree(dst / name, ignore_errors=True)
    # (Re)deliver each upstream skill; leave the project's own skills alone.
    for name in upstream:
        target = dst / name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(src / name, target, ignore=IGNORE)
    manifest.write_text("".join(f"{name}\n" for name in upstream), encoding="utf-8")
    return upstream


def write_stamp(mount: Path, claude: Path) -> str:
    try:
        sha = subprocess.check_output(
            ["git", "-C", str(mount), "rev-parse", "HEAD"]
        ).decode().strip()
    except Exception:
        sha = "unknown"
    claude.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (claude / ".pinq-doq-version").write_text(
        f"source_sha: {sha}\ndelivered_at: {now}\n", encoding="utf-8"
    )
    return sha


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Copy pinq-doq rules/ and skills/ into .claude/ (idempotent)."
    )
    parser.add_argument("--project-root", default=".", help="Consumer project root (default: cwd).")
    parser.add_argument(
        "--mount", default=".pinq-doq",
        help="pinq-doq mount path relative to the project root (default: .pinq-doq).",
    )
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    mount = (root / args.mount).resolve()
    claude = root / ".claude"
    if not mount.is_dir():
        sys.exit(f"error: mount {mount} not found — add pinq-doq as a submodule first.")

    mirror_rules(mount, claude)
    skills = merge_skills(mount, claude)
    sha = write_stamp(mount, claude)
    print(f"pinq-doq delivered: rules mirrored; skills={skills or 'none'}; source_sha={sha[:10]}")


if __name__ == "__main__":
    main()
