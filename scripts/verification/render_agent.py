#!/usr/bin/env python3
"""Renders the verification subagent from agent-template.md.

  render_agent.py pinqloq [--out PATH]
  render_agent.py generic --scripts-dir DIR [--name NAME] [--out PATH]

`pinqloq` produces runner/agents/pin-test.md exactly: the task runner's lock key, its state file and
the forwarding scripts under ~/.claude/skills/pinqloq-task-runner/scripts. Change the template, then
rerun `render_agent.py pinqloq --out runner/agents/pin-test.md`; a test fails while the two differ.
`generic` drops everything that needs the task runner and points at DIR, the folder that holds these
scripts on that machine (e.g. `.pinq-doq/scripts/verification` or an absolute path). Without --out
the agent is printed.

Template syntax: `{{key}}` is replaced by the profile's value, `[[pinqloq:text]]` and
`[[generic:text]]` keep their text only for that profile (on one line, never nested), and a line
that only held blocks of the other profile is dropped.
"""
import argparse
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATE_FILE = SCRIPT_DIR / "agent-template.md"
PINQLOQ_PROFILE_NAME = "pinqloq"
GENERIC_PROFILE_NAME = "generic"
PROFILE_NAMES = (PINQLOQ_PROFILE_NAME, GENERIC_PROFILE_NAME)
PINQLOQ_VALUES = {"name": "pin-test", "scripts_dir": "~/.claude/skills/pinqloq-task-runner/scripts"}
DEFAULT_GENERIC_NAME = "verification-runner"
CONDITIONAL_BLOCK = re.compile(r"\[\[(" + "|".join(PROFILE_NAMES) + r"):(.*?)\]\]")
PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


def render_line(line, profile_name):
    return CONDITIONAL_BLOCK.sub(lambda match: match.group(2) if match.group(1) == profile_name else "", line)


def is_only_other_profile_blocks(line, rendered_line):
    return CONDITIONAL_BLOCK.search(line) is not None and not rendered_line.strip()


def fill_placeholders(text, values):
    missing_keys = sorted(set(PLACEHOLDER.findall(text)) - set(values))
    if missing_keys:
        raise SystemExit(f"{TEMPLATE_FILE}: no value for {missing_keys}")
    return PLACEHOLDER.sub(lambda match: values[match.group(1)], text)


def render(template_text, profile_name, values):
    if profile_name not in PROFILE_NAMES:
        raise SystemExit(f"unknown profile {profile_name!r}; known: {list(PROFILE_NAMES)}")
    rendered_lines = []
    for line in template_text.splitlines(keepends=True):
        rendered_line = render_line(line, profile_name)
        if is_only_other_profile_blocks(line, rendered_line):
            continue
        rendered_lines.append(rendered_line)
    return fill_placeholders("".join(rendered_lines), values)


def profile_values(arguments):
    if arguments.profile == PINQLOQ_PROFILE_NAME:
        if arguments.scripts_dir or arguments.name:
            raise SystemExit("the pinqloq profile has fixed --scripts-dir and --name; use the generic profile to change them")
        return dict(PINQLOQ_VALUES)
    scripts_dir = (arguments.scripts_dir or "").strip().rstrip("/")
    if not scripts_dir:
        raise SystemExit("the generic profile needs --scripts-dir, the folder that holds run_build.py on that machine")
    return {"name": arguments.name or DEFAULT_GENERIC_NAME, "scripts_dir": scripts_dir}


def parse_arguments():
    parser = argparse.ArgumentParser(description="Render the verification subagent from agent-template.md.")
    parser.add_argument("profile", choices=PROFILE_NAMES)
    parser.add_argument("--scripts-dir")
    parser.add_argument("--name")
    parser.add_argument("--out")
    return parser.parse_args()


def main():
    arguments = parse_arguments()
    agent_text = render(TEMPLATE_FILE.read_text(), arguments.profile, profile_values(arguments))
    if not arguments.out:
        sys.stdout.write(agent_text)
        return
    output_path = Path(arguments.out).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(agent_text)
    print(f"wrote {output_path}")


if __name__ == "__main__":
    main()
