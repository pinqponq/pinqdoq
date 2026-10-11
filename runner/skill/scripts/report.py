#!/usr/bin/env python3
"""Run reports for the pinqloq web panel (the runner sends no mail since 2026-10-11).

Each run that has something to say adds one report; the panel lists them newest first.

  report.py add <session>  < report.json   append one report; the JSON object holds
                                            "title" (one line), optional "task" (task key), "pr_url",
                                            and "sections": {"<heading>": ["<markdown line>", ...]}
  report.py list [--limit N]                print the newest reports as JSON (newest first)
"""
import fcntl
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

STATE_DIR = Path.home() / ".claude" / "pinqloq-task-runner"
REPORTS_FILE = STATE_DIR / "reports.jsonl"
REPORTS_LOCK_FILE = STATE_DIR / "reports.jsonl.lock"
MAX_KEPT_REPORTS = 300
DEFAULT_LIST_LIMIT = 30


def validate_report(report):
    if not isinstance(report, dict) or not str(report.get("title", "")).strip():
        raise ValueError("report needs a non-empty title")
    sections = report.get("sections", {})
    if not isinstance(sections, dict) or not all(isinstance(lines, list) for lines in sections.values()):
        raise ValueError("sections must map a heading to a list of lines")


def read_reports():
    try:
        lines = REPORTS_FILE.read_text().splitlines()
    except FileNotFoundError:
        return []
    return [json.loads(line) for line in lines if line.strip()]


def add_report(session, report):
    validate_report(report)
    entry = {"at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "session": session, **report}
    with open(REPORTS_LOCK_FILE, "w") as lock_handle:
        fcntl.flock(lock_handle, fcntl.LOCK_EX)
        reports = (read_reports() + [entry])[-MAX_KEPT_REPORTS:]
        temporary_file = REPORTS_FILE.with_suffix(".jsonl.tmp")
        temporary_file.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in reports))
        temporary_file.replace(REPORTS_FILE)
    print("report added")


def main():
    arguments = sys.argv[1:]
    if len(arguments) == 2 and arguments[0] == "add":
        try:
            add_report(arguments[1], json.load(sys.stdin))
        except ValueError as error:
            sys.exit("report.py: %s" % error)
        return
    if arguments and arguments[0] == "list":
        limit = int(arguments[arguments.index("--limit") + 1]) if "--limit" in arguments else DEFAULT_LIST_LIMIT
        print(json.dumps(list(reversed(read_reports()))[:limit], ensure_ascii=False, indent=1))
        return
    print(__doc__, file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
