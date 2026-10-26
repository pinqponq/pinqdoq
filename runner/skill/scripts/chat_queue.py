#!/usr/bin/env python3
"""Queue a task the owner gave in chat, without an issue behind it.

  chat_queue.py add --repo <folder> --title <title> [--priority N] [--weight light] [--needs-device true|false]
               < description.txt
      stores the task in state.json as `selected`, so `locks.py claim` can pick it, and prints its key

The key is `local/<repo>#<n>`: <repo> is the repository's folder under the machine's `workspace_dir`,
<n> the next number no local task used yet. It keeps the `<name>#<number>` shape the locks, the
timings and the worktree names (`<repo>-<n>`) are built from. The description is stored in the task,
because there is no issue to read it from. Read the description from stdin, so quotes and line
breaks need no shell quoting.
"""
import argparse
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner_config  # noqa: E402
import state_tx  # noqa: E402

LOCAL_OWNER = "local"
LOCAL_KEY_PATTERN = re.compile(r"^%s/[^#]+#(\d+)$" % LOCAL_OWNER)
SELECTED_STATUS = "selected"
LIGHT_WEIGHT = "light"


def next_local_number(task_keys):
    used_numbers = [int(match.group(1)) for match in map(LOCAL_KEY_PATTERN.match, task_keys) if match]
    return max(used_numbers, default=0) + 1


def find_repository_dir(repository_name):
    if "/" in repository_name or repository_name.startswith("."):
        raise SystemExit("--repo is the repository's folder name under workspace_dir, not a path: %r" % repository_name)
    repository_dir = runner_config.read_machine_config()["workspace_dir"] / repository_name
    inside_work_tree = subprocess.run(["git", "-C", str(repository_dir), "rev-parse", "--is-inside-work-tree"],
                                      capture_output=True, text=True)
    if inside_work_tree.returncode != 0:
        raise SystemExit("%s is not a git checkout; clone the repository there first" % repository_dir)
    return repository_dir


def build_task(arguments, description, repository_dir):
    task = {
        "title": arguments.title,
        "status": SELECTED_STATUS,
        "source": "chat",
        "description": description,
        "repo_dir": str(repository_dir),
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if arguments.priority is not None:
        task["queue_priority"] = arguments.priority
    if arguments.weight:
        task["weight"] = arguments.weight
    if arguments.needs_device is not None:
        task["needs_device"] = arguments.needs_device == "true"
    return task


def add_task(arguments, description):
    if not arguments.title.strip():
        raise SystemExit("--title is empty")
    if not description.strip():
        raise SystemExit("the description on stdin is empty; describe what the task must do")
    repository_dir = find_repository_dir(arguments.repo)
    task = build_task(arguments, description.strip(), repository_dir)
    with state_tx.locked_state():
        state = state_tx.read_state()
        archived_keys = state_tx.read_archive().get("tasks", {}).keys()
        task_key = "%s/%s#%d" % (LOCAL_OWNER, arguments.repo, next_local_number(list(state["tasks"]) + list(archived_keys)))
        state["tasks"][task_key] = task
        state_tx.write_state(state)
    return task_key


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    subcommands = parser.add_subparsers(dest="command", required=True)
    add_parser = subcommands.add_parser("add")
    add_parser.add_argument("--repo", required=True)
    add_parser.add_argument("--title", required=True)
    add_parser.add_argument("--priority", type=int, help="lower is claimed first (claim's default is 1000)")
    add_parser.add_argument("--weight", choices=[LIGHT_WEIGHT])
    add_parser.add_argument("--needs-device", choices=["true", "false"])
    return parser.parse_args()


def main():
    arguments = parse_arguments()
    print(add_task(arguments, sys.stdin.read()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
