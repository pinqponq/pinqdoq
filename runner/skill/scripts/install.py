#!/usr/bin/env python3
"""Install the pinqloq task runner on this machine from a pinqdoq checkout.

  python3 <pinqdoq>/runner/skill/scripts/install.py [--role primary|queue-only] [--workspace DIR]
          [--worktrees DIR] [--runner-dir DIR] [--mail-cc ADDRESS ...] [--replace] [--dry-run]

What it does (idempotent, run it again after moving the checkout):
1. Links ~/.claude/skills/pinqloq-task-runner and ~/.claude/agents/pin-*.md to the checkout, so `git pull` in pinqdoq updates the runner. An existing real file or folder at
   one of those places is left alone unless --replace is given; then it is moved (never deleted) to
   ~/.claude/pinqloq-trash/<timestamp>/.
2. Creates the state folder and machine.json (role, folders, mail CC). An existing machine.json is
   never overwritten; differing options are reported.
3. Creates the runner folder with its README and .claude/settings.local.json (permissions + the
   pinq-ponq git/gh identity) from templates/. An existing settings file is never overwritten.
4. Writes the routine prompts to <state>/routines/ for creating the scheduled tasks.
5. Runs doctor.py.

It never handles secrets: the SMTP password, the pinq-ponq gh login, the pinqloq MCP key and
test-accounts.json are set up by hand (doctor.py says what is missing).
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner_config  # noqa: E402

RUNNER_DIR_IN_REPO = runner_config.SKILL_DIR.parent
CLAUDE_DIR = Path.home() / ".claude"
TRASH_DIR = CLAUDE_DIR / "pinqloq-trash"
ROUTINES = [("pinqloq-task-runner", "runner-1", "scheduled"),
            ("pinqloq-task-runner-2", "runner-2", "manual"),
            ("pinqloq-task-runner-3", "runner-3", "manual")]
RUNNER_FOLDER_README = """# pinqloq-runner

Working folder for the pinqloq task runner routines (runner-1/2/3). Installed by pinqdoq
`runner/skill/scripts/install.py`; the runner itself lives in the pinqdoq checkout.
The runner never edits files here; it works in git worktrees under the machine's `worktrees_dir`.
`.claude/settings.local.json` holds this folder's permission mode and the pinq-ponq identity, so it
applies only to runner sessions.
"""


def link_targets():
    links = [(CLAUDE_DIR / "skills" / "pinqloq-task-runner", RUNNER_DIR_IN_REPO / "skill")]
    links += [(CLAUDE_DIR / "agents" / agent.name, agent) for agent in sorted((RUNNER_DIR_IN_REPO / "agents").glob("pin-*.md"))]
    return links


def move_to_trash(path, trash_session_dir, dry_run):
    destination = trash_session_dir / path.relative_to(CLAUDE_DIR)
    if not dry_run:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), str(destination))
    return destination


def install_link(link_path, target, replace, trash_session_dir, dry_run):
    if link_path.is_symlink():
        if link_path.resolve() == target.resolve():
            return "ok      %s" % link_path
        if not dry_run:
            link_path.unlink()
    elif link_path.exists():
        if not replace:
            return "SKIPPED %s exists as a real file/folder (run with --replace to move it to the trash)" % link_path
        destination = move_to_trash(link_path, trash_session_dir, dry_run)
        print("moved   %s -> %s" % (link_path, destination))
    if not dry_run:
        link_path.parent.mkdir(parents=True, exist_ok=True)
        link_path.symlink_to(target)
    return "linked  %s -> %s" % (link_path, target)


def write_machine_config(arguments, dry_run):
    requested = {"role": arguments.role, "workspace_dir": arguments.workspace, "worktrees_dir": arguments.worktrees,
                 "runner_dir": arguments.runner_dir, "mail_cc": arguments.mail_cc}
    requested = {key: value for key, value in requested.items() if value is not None}
    config_file = runner_config.MACHINE_CONFIG_FILE
    if config_file.exists():
        stored = json.loads(config_file.read_text())
        differing = {key: value for key, value in requested.items() if stored.get(key) != value}
        if differing:
            return "KEPT    %s; edit it by hand to change: %s" % (config_file, json.dumps(differing, ensure_ascii=False))
        return "ok      %s" % config_file
    machine_config = {**runner_config.DEFAULT_MACHINE_CONFIG, **requested}
    if not dry_run:
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(json.dumps(machine_config, indent=2, ensure_ascii=False) + "\n")
    return "created %s (role %s)" % (config_file, machine_config["role"])


def worktrees_storage_dir(worktrees_dir):
    """The folder that physically holds the worktrees (it may be a link to an external disk)."""
    return Path(os.path.realpath(worktrees_dir)).parent


def render_settings(machine):
    template_text = (RUNNER_DIR_IN_REPO / "templates" / "settings.local.json").read_text()
    replacements = {"{HOME}": str(Path.home()), "{WORKSPACE_DIR}": str(machine["workspace_dir"]),
                    "{WORKTREES_STORAGE_DIR}": str(worktrees_storage_dir(machine["worktrees_dir"]))}
    for placeholder, value in replacements.items():
        template_text = template_text.replace(placeholder, value)
    json.loads(template_text)
    return template_text


def write_runner_folder(machine, dry_run):
    runner_dir = machine["runner_dir"]
    settings_file = runner_dir / ".claude" / "settings.local.json"
    readme_file = runner_dir / "README.md"
    results = []
    settings_text = render_settings(machine)
    if settings_file.exists():
        same = json.loads(settings_file.read_text()) == json.loads(settings_text)
        results.append("ok      %s" % settings_file if same else
                       "KEPT    %s differs from templates/settings.local.json; compare them by hand" % settings_file)
    else:
        if not dry_run:
            settings_file.parent.mkdir(parents=True, exist_ok=True)
            settings_file.write_text(settings_text)
        results.append("created %s" % settings_file)
    if not readme_file.exists() or readme_file.read_text() != RUNNER_FOLDER_README:
        if not dry_run:
            runner_dir.mkdir(parents=True, exist_ok=True)
            readme_file.write_text(RUNNER_FOLDER_README)
        results.append("wrote   %s" % readme_file)
    return results


def write_routine_prompts(machine, dry_run):
    template_text = (RUNNER_DIR_IN_REPO / "templates" / "routine.md").read_text()
    routines_dir = runner_config.STATE_DIR / "routines"
    for task_id, runner_label, session_prefix in ROUTINES:
        prompt = (template_text.replace("{TASK_ID}", task_id).replace("{RUNNER_LABEL}", runner_label)
                  .replace("{SESSION_PREFIX}", session_prefix).replace("{WORKSPACE_DIR}", str(machine["workspace_dir"])))
        if not dry_run:
            routines_dir.mkdir(parents=True, exist_ok=True)
            (routines_dir / (task_id + ".md")).write_text(prompt)
    return ["wrote   %s/*.md: in a Claude Code chat say \"create the runner routines from %s\" "
            "(task ids %s, folder %s, manual, permission mode bypass)"
            % (routines_dir, routines_dir, ", ".join(task_id for task_id, _, _ in ROUTINES), machine["runner_dir"])]


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--role", choices=runner_config.ROLES)
    parser.add_argument("--workspace")
    parser.add_argument("--worktrees")
    parser.add_argument("--runner-dir")
    parser.add_argument("--mail-cc", nargs="+")
    parser.add_argument("--replace", action="store_true", help="move existing real files at the link places to the trash")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main():
    arguments = parse_arguments()
    dry_run = arguments.dry_run
    trash_session_dir = TRASH_DIR / datetime.now().strftime("%Y%m%d-%H%M%S")
    print(write_machine_config(arguments, dry_run))
    machine = runner_config.read_machine_config()
    if not dry_run:
        runner_config.STATE_DIR.mkdir(parents=True, exist_ok=True)
        machine["worktrees_dir"].mkdir(parents=True, exist_ok=True)
    for link_path, target in link_targets():
        print(install_link(link_path, target, arguments.replace, trash_session_dir, dry_run))
    for line in write_runner_folder(machine, dry_run) + write_routine_prompts(machine, dry_run):
        print(line)
    if dry_run:
        print("dry run: nothing was changed")
        return 0
    sys.stdout.flush()
    return subprocess.run([sys.executable, str(Path(__file__).resolve().parent / "doctor.py")]).returncode


if __name__ == "__main__":
    sys.exit(main())
