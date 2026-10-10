#!/usr/bin/env python3
"""Shared and per-machine configuration of the pinqloq task runner.

  runner_config.py            print the merged configuration as JSON (no secrets are stored in it)

Two files:
- `<skill>/config.json` (in pinqdoq, public): the team's board coordinates, mail server and
  addressing rules that hold on every machine. No personal addresses.
- `~/.claude/pinqloq-task-runner/machine.json` (local, never committed): this machine's role,
  folders and the mail recipients. `install.py` creates it; every key has a default, so a missing
  file means "primary runner with the default folders".

Roles:
- `primary`: the full runner (board scan, proposals, comment decisions, reminders, verification).
- `queue-only`: only works on tasks the owner queued in this machine's panel or chat. It skips all
  housekeeping, so two machines never send the same proposal or act on the same issue comment.
"""
import json
import os
import re
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
TEAM_CONFIG_FILE = SKILL_DIR / "config.json"
STATE_DIR = Path.home() / ".claude" / "pinqloq-task-runner"
MACHINE_CONFIG_FILE = STATE_DIR / "machine.json"
PRIMARY_ROLE = "primary"
QUEUE_ONLY_ROLE = "queue-only"
ROLES = (PRIMARY_ROLE, QUEUE_ONLY_ROLE)
DEFAULT_MACHINE_CONFIG = {
    "role": PRIMARY_ROLE,
    "workspace_dir": "~/StudioProjects",
    "worktrees_dir": "~/StudioProjects/.task-runner-worktrees",
    "runner_dir": "~/StudioProjects/pinqloq-runner",
    "mail_cc": [],
}
PATH_KEYS = ("workspace_dir", "worktrees_dir", "runner_dir")


def read_team_config():
    return json.loads(TEAM_CONFIG_FILE.read_text())


def read_machine_config():
    stored = json.loads(MACHINE_CONFIG_FILE.read_text()) if MACHINE_CONFIG_FILE.exists() else {}
    unknown_keys = sorted(set(stored) - set(DEFAULT_MACHINE_CONFIG))
    if unknown_keys:
        raise ValueError("%s has unknown keys: %s" % (MACHINE_CONFIG_FILE, ", ".join(unknown_keys)))
    machine = {**DEFAULT_MACHINE_CONFIG, **stored}
    if machine["role"] not in ROLES:
        raise ValueError("%s: role must be one of %s, not %r" % (MACHINE_CONFIG_FILE, ROLES, machine["role"]))
    for key in PATH_KEYS:
        machine[key] = Path(os.path.expanduser(machine[key]))
    return machine


def transcript_dir_for(runner_dir):
    """Claude Code stores a folder's sessions under ~/.claude/projects/<path, every non-alphanumeric as ->."""
    return Path.home() / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(runner_dir))


def main():
    machine = read_machine_config()
    printable_machine = {key: str(value) if key in PATH_KEYS else value for key, value in machine.items()}
    print(json.dumps({"team": read_team_config(), "machine": printable_machine,
                      "machine_config_file": str(MACHINE_CONFIG_FILE),
                      "machine_config_exists": MACHINE_CONFIG_FILE.exists()}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    sys.exit(main())
