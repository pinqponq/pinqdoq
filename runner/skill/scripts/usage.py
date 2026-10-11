#!/usr/bin/env python3
"""Plan usage snapshot for the web panel's header and auto-start.

Only a Claude Code session can read the plan limits (its `get_usage` tool), so every runner run records
what it saw here and the panel reads the file.

  usage.py record --five-hour <percent> --five-hour-resets <ISO-8601> --weekly <percent> --weekly-resets <ISO-8601>
"""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

LIVE_USAGE_FILE = Path.home() / ".claude" / "pinqloq-task-runner" / "usage-live.json"


def normalize_timestamp(text):
    moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def record(arguments):
    snapshot = {
        "captured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "get_usage",
        "five_hour": {"percent": arguments.five_hour, "resets_at": normalize_timestamp(arguments.five_hour_resets)},
        "weekly": {"percent": arguments.weekly, "resets_at": normalize_timestamp(arguments.weekly_resets)},
    }
    temporary_file = LIVE_USAGE_FILE.with_suffix(".json.tmp.%d" % os.getpid())
    temporary_file.write_text(json.dumps(snapshot) + "\n")
    os.replace(str(temporary_file), str(LIVE_USAGE_FILE))
    print("usage recorded")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("command", choices=["record"])
    parser.add_argument("--five-hour", type=int, required=True)
    parser.add_argument("--five-hour-resets", required=True)
    parser.add_argument("--weekly", type=int, required=True)
    parser.add_argument("--weekly-resets", required=True)
    record(parser.parse_args())


if __name__ == "__main__":
    main()
