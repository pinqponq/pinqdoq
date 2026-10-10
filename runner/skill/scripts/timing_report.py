#!/usr/bin/env python3
"""Summarises timings.jsonl per task: time per kind (build/test/pit/device), slowest steps,
failed runs and Maestro flow retries.

Usage: timing_report.py [--task rindle-cmp#354] [--days 7] [--top 5] [--brief] [--from-logs]
  --brief      one line per task, for the runs.log line (e.g. "build 18m, test 3m, pit 2m, device 16m (2 retries)")
  --from-logs  also read older runs from <worktree>/build/runner-logs/*.log (start from the file name,
               end from the file's last write; marked "~" as approximate)
"""
import argparse, glob, json, os, re, time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import runner_config
import timings

WORKTREES_DIR = str(runner_config.read_machine_config()["worktrees_dir"])
LOG_TIMESTAMP = re.compile(r"(\d{8}T\d{6}Z)\.log$")
KINDS = ("build", "test", "pit", "device", "other")


def parse_time(text):
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def normalize_task(task):
    return re.sub(r"^pinqponq/", "", task or "?")


def read_recorded_entries():
    if not os.path.exists(timings.TIMINGS_FILE):
        return []
    with open(timings.TIMINGS_FILE) as timings_file:
        return [json.loads(line) for line in timings_file if line.strip()]


def read_log_entries(recorded_logs):
    entries = []
    for path in glob.glob(os.path.join(WORKTREES_DIR, "*", "build", "runner-logs", "*.log")):
        match = LOG_TIMESTAMP.search(path)
        if not match or os.path.realpath(path) in recorded_logs:
            continue
        start = datetime.strptime(match.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).timestamp()
        end = os.path.getmtime(path)
        with open(path, errors="replace") as log_file:
            lines = log_file.read().splitlines()
        step = os.path.basename(path)[:match.start() - len(os.path.dirname(path)) - 1].strip("-")
        kind = timings.classify_command([step])
        flows = timings.maestro_flow_results(lines) if kind == "device" else []
        failed = any("BUILD FAILED" in line or "Flow Failed" in line or "Flows Failed" in line for line in lines)
        worktree = path.split(os.sep + "build" + os.sep)[0]
        entries.append({
            "start": timings.utc_timestamp(start), "seconds": round(max(end - start, 0), 1), "kind": kind,
            "task": timings.task_from_worktree(worktree), "command": step, "exit": 1 if failed else 0,
            "flows": flows, "approximate": True,
        })
    return entries


def format_duration(seconds):
    minutes, remainder = divmod(int(round(seconds)), 60)
    return f"{minutes}m{remainder:02d}s" if minutes else f"{remainder}s"


def flow_retries(entries):
    """Runs of the same flow after a failed run of it: each is one retry."""
    failed_before = set()
    retries = defaultdict(int)
    errors = defaultdict(list)
    for entry in sorted(entries, key=lambda item: item["start"]):
        platform = timings.device_platform(entry["command"].replace("-", " ")) or "?"
        for flow in entry.get("flows") or []:
            flow_key = f"{platform}: {flow['name']}"
            if flow_key in failed_before:
                retries[flow_key] += 1
            if not flow["passed"]:
                failed_before.add(flow_key)
                errors[flow_key].append(flow.get("error", "?"))
    return {key: (count, errors[key]) for key, count in retries.items()}


def summarize_task(entries):
    seconds_by_kind = defaultdict(float)
    for entry in entries:
        seconds_by_kind[entry["kind"]] += entry["seconds"]
    return seconds_by_kind, [entry for entry in entries if entry["exit"] != 0], flow_retries(entries)


def brief_line(task, entries):
    seconds_by_kind, failed, retries = summarize_task(entries)
    parts = [f"{kind} {format_duration(seconds_by_kind[kind])}" for kind in KINDS if seconds_by_kind[kind]]
    notes = []
    if failed:
        notes.append(f"{len(failed)} failed runs")
    if retries:
        notes.append(f"{sum(count for count, _ in retries.values())} flow retries")
    approximate = "~" if any(entry.get("approximate") for entry in entries) else ""
    return f"{task}: {approximate}{', '.join(parts)}" + (f" ({', '.join(notes)})" if notes else "")


def print_task_report(task, entries, top):
    seconds_by_kind, failed, retries = summarize_task(entries)
    total = sum(seconds_by_kind.values())
    first, last = min(entry["start"] for entry in entries), max(entry["start"] for entry in entries)
    print(f"## {task}  ({len(entries)} runs, {format_duration(total)} total, {first} → {last})\n")
    print("| Kind | Runs | Time | Failed |\n|---|---|---|---|")
    for kind in KINDS:
        kind_entries = [entry for entry in entries if entry["kind"] == kind]
        if kind_entries:
            failed_count = sum(1 for entry in kind_entries if entry["exit"] != 0)
            print(f"| {kind} | {len(kind_entries)} | {format_duration(seconds_by_kind[kind])} | {failed_count} |")
    print(f"\nSlowest {top}:")
    for entry in sorted(entries, key=lambda item: -item["seconds"])[:top]:
        marker = "~" if entry.get("approximate") else ""
        status = "FAIL" if entry["exit"] != 0 else "ok"
        print(f"- {marker}{format_duration(entry['seconds'])} {entry['kind']} {status}: {entry['command'][:90]}")
    if retries:
        print("\nFlow retries (runs after a failed run of the same flow):")
        for name, (count, errors) in sorted(retries.items(), key=lambda item: -item[1][0]):
            print(f"- {count}× {name[:110]}")
            for error in dict.fromkeys(errors):
                print(f"  - failed: {error[:140]}")
    pit_runs = [entry["pit"] for entry in entries if entry.get("pit")]
    if pit_runs:
        print("\nPIT: " + ", ".join(f"{run['score']}% ({run['killed']}/{run['total']})" for run in pit_runs))
    print()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task")
    parser.add_argument("--days", type=float, default=7)
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument("--brief", action="store_true")
    parser.add_argument("--from-logs", action="store_true")
    arguments = parser.parse_args()

    entries = read_recorded_entries()
    if arguments.from_logs:
        entries += read_log_entries({os.path.realpath(entry["log"]) for entry in entries if entry.get("log")})
    since = datetime.now(timezone.utc) - timedelta(days=arguments.days)
    wanted_task = normalize_task(arguments.task) if arguments.task else None
    by_task = defaultdict(list)
    for entry in entries:
        task = normalize_task(entry["task"])
        if parse_time(entry["start"]) >= since and (wanted_task is None or task == wanted_task):
            by_task[task].append(entry)
    if not by_task:
        print("no timings recorded" + (f" for {wanted_task}" if wanted_task else ""))
        return
    ordered_tasks = sorted(by_task, key=lambda task: max(entry["start"] for entry in by_task[task]), reverse=True)
    for task in ordered_tasks:
        if arguments.brief:
            print(brief_line(task, by_task[task]))
        else:
            print_task_report(task, by_task[task], arguments.top)


if __name__ == "__main__":
    main()
