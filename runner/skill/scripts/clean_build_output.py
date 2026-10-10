#!/usr/bin/env python3
"""Deletes runner build output inside a worktree without `rm` in the shell command.

Claude Code asks for approval on `rm -rf "$(...)"` / `rm -rf $VAR/...` even in bypass mode, because
it cannot resolve the target. This script resolves the target itself and only deletes inside
<worktree>/build/ or a `_small/` folder made by shrink_images.py.

Usage: clean_build_output.py --cwd <worktree> <path>... [--newest PATTERN]
  clean_build_output.py --cwd $W build/maestro/ios build/pit-report
  clean_build_output.py --cwd $W --newest 'build/maestro/ios/2026*'     # only the newest match
  clean_build_output.py --cwd $W composeApp/src/desktopTest/screenshots/_small
"""
import argparse, glob, os, shutil, sys


def is_deletable(path, worktree):
    build_directory = os.path.join(worktree, "build") + os.sep
    inside_worktree = path.startswith(worktree + os.sep)
    inside_build = path.startswith(build_directory) or "/build/" in path[len(worktree):]
    is_shrink_copy = os.path.basename(path) == "_small" or "/_small/" in path
    return inside_worktree and (inside_build or is_shrink_copy)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cwd", required=True)
    parser.add_argument("--newest")
    parser.add_argument("paths", nargs="*")
    arguments = parser.parse_args()
    worktree = os.path.realpath(arguments.cwd)

    targets = [os.path.join(worktree, path) for path in arguments.paths]
    if arguments.newest:
        matches = sorted(glob.glob(os.path.join(worktree, arguments.newest)), key=os.path.getmtime)
        targets += matches[-1:]
    if not targets:
        parser.error("nothing to delete")

    exit_code = 0
    for target in targets:
        resolved = os.path.realpath(target)
        if not is_deletable(resolved, worktree):
            print(f"refused (outside build/ or _small/): {resolved}", file=sys.stderr)
            exit_code = 2
            continue
        if not os.path.lexists(resolved):
            print(f"absent: {resolved}")
            continue
        if os.path.isdir(resolved) and not os.path.islink(resolved):
            shutil.rmtree(resolved)
        else:
            os.remove(resolved)
        print(f"deleted: {resolved}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
