#!/usr/bin/env python3
"""Appends one line per build/test/PIT/Maestro run to ~/.claude/pinqloq-task-runner/timings.jsonl.

Used by run_build.py and run_pit.py; timing_report.py reads the file. A failed write never fails
the run that called it.
"""
import fcntl, json, os, re, sys, time

TIMINGS_FILE = os.path.expanduser("~/.claude/pinqloq-task-runner/timings.jsonl")
MAX_COMMAND_LENGTH = 300
SECRET_LIKE = re.compile(r"(?i)(password|secret|token|apikey|api_key|otp)\s*[=:]\s*\S+")
MAESTRO_FLOW_RESULT = re.compile(r"^\[(Passed|Failed)\] (.+?) \((?:(\d+)m )?(\d+)s\)(?: \((.*)\))?\s*$")


def utc_timestamp(seconds):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(seconds))


def task_from_worktree(working_directory):
    """rindle-cmp-354 -> rindle-cmp#354; other worktree names (baselines, develop builds) stay as they are."""
    name = os.path.basename(os.path.realpath(working_directory))
    match = re.fullmatch(r"(.+)-(\d+)", name)
    return f"{match.group(1)}#{match.group(2)}" if match else name


def device_platform(text):
    match = re.search(r"\b(android|ios)\b", text)
    return match.group(1) if match else None


def classify_command(command):
    joined = " ".join(command)
    if "maestro" in joined or "run-flow" in joined:
        return "device"
    if "xcodebuild" in joined or re.search(r"assemble|compile|podspec|generateDummyFramework|dotnet build", joined):
        return "build"
    if re.search(r"[Tt]est|Roborazzi|stryker", joined):
        return "test"
    return "other"


def maestro_flow_results(lines):
    flows = []
    for line in lines:
        match = MAESTRO_FLOW_RESULT.match(line.strip())
        if match:
            minutes, seconds = int(match.group(3) or 0), int(match.group(4))
            flow = {"name": match.group(2), "passed": match.group(1) == "Passed", "seconds": minutes * 60 + seconds}
            if match.group(5):
                flow["error"] = SECRET_LIKE.sub(r"\1=<redacted>", match.group(5))[:MAX_COMMAND_LENGTH]
            flows.append(flow)
    return list({flow["name"]: flow for flow in flows}.values())


def record(kind, task, working_directory, command, start_seconds, end_seconds, exit_code, **details):
    entry = {
        "start": utc_timestamp(start_seconds),
        "end": utc_timestamp(end_seconds),
        "seconds": round(end_seconds - start_seconds, 1),
        "kind": kind,
        "task": task or task_from_worktree(working_directory),
        "worktree": os.path.basename(os.path.realpath(working_directory)),
        "command": SECRET_LIKE.sub(r"\1=<redacted>", " ".join(command))[:MAX_COMMAND_LENGTH],
        "exit": exit_code,
        **{key: value for key, value in details.items() if value not in (None, [], {})},
    }
    try:
        os.makedirs(os.path.dirname(TIMINGS_FILE), exist_ok=True)
        with open(TIMINGS_FILE, "a") as timings_file:
            fcntl.flock(timings_file, fcntl.LOCK_EX)
            timings_file.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as error:
        print(f"timings: not recorded ({error})", file=sys.stderr)
