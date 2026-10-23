#!/usr/bin/env python3
"""Shared and per-machine configuration of the pinqloq task runner.

  runner_config.py            print the merged configuration as JSON (no secrets are stored in it)

Two files:
- `<skill>/config.json` (in pinqdoq, public): the team's board coordinates and settings that hold
  on every machine. No personal addresses.
- `~/.claude/pinqloq-task-runner/machine.json` (local, never committed): this machine's role,
  folders and the Pinq Center service token (`pinq_center`: `api_url`, `runner_token`; never printed).
  `install.py` creates it; every key has a default, so a missing
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
    "pinq_center": None,
}
# Runner roles (owner, 2026-10-23). The single place that says which runner takes which tasks:
# - "device": tasks that need an emulator or simulator, taken first (`needs_device`; unknown counts as needing one);
#   without such a task waiting, the runner takes a task without a device instead of idling.
# - "no-device": only tasks marked `needs_device: false`.
# - "light": only tasks marked `weight: "light"` (runner-3, owner 2026-10-12).
# - None: every task.
# `device_platform` is the device a device runner tries first; the other one is its fallback for shared-code proof.
# The scheduled task names (first column of install.ROUTINES) stay as they are: the panel, the start script and the
# watchers use them. Only the display label carries the role.
DEVICE_ROLE = "device"
NO_DEVICE_ROLE = "no-device"
LIGHT_ROLE = "light"
RUNNER_ROLES = {
    "runner-1": {"role": DEVICE_ROLE, "device_platform": "android"},
    "runner-2": {"role": DEVICE_ROLE, "device_platform": "ios"},
    "runner-3": {"role": LIGHT_ROLE, "device_platform": None},
    "runner-4": {"role": NO_DEVICE_ROLE, "device_platform": None},
}


def runner_display_label(runner_label):
    """`runner-1` -> `runner-1 (device, android)`; a runner without a configured role keeps its label."""
    configured = RUNNER_ROLES.get(runner_label)
    if configured is None:
        return runner_label
    parts = [configured["role"]] + ([configured["device_platform"]] if configured["device_platform"] else [])
    return "%s (%s)" % (runner_label, ", ".join(parts))


PATH_KEYS = ("workspace_dir", "worktrees_dir", "runner_dir")
# Keys older machine.json files still carry; mail_cc lost its use when the runner stopped mailing (2026-10-11).
RETIRED_KEYS = {"mail_cc"}


def read_team_config():
    return json.loads(TEAM_CONFIG_FILE.read_text())


def read_machine_config():
    stored = json.loads(MACHINE_CONFIG_FILE.read_text()) if MACHINE_CONFIG_FILE.exists() else {}
    stored = {key: value for key, value in stored.items() if key not in RETIRED_KEYS}
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
    if printable_machine["pinq_center"]:
        printable_machine["pinq_center"] = {**printable_machine["pinq_center"], "runner_token": "<hidden>"}
    print(json.dumps({"team": read_team_config(), "machine": printable_machine,
                      "machine_config_file": str(MACHINE_CONFIG_FILE),
                      "machine_config_exists": MACHINE_CONFIG_FILE.exists()}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    sys.exit(main())
