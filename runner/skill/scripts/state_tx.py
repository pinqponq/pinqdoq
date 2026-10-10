#!/usr/bin/env python3
"""Locked read-modify-write access to the runner's state.json.

Several runner sessions can be active at once, so a session must never write state.json from a
copy it read earlier: that would drop whatever another session wrote in between. Every change goes
through this script, which takes an exclusive file lock, re-reads the file, applies the change and
replaces the file atomically.

  state_tx.py get [dotted.path]                  print the whole state or one value as JSON
  state_tx.py task <task-key>  < patch.json      JSON merge patch into tasks[<task-key>] (null deletes a key)
  state_tx.py patch            < patch.json      JSON merge patch into the root
  state_tx.py append <list> '<json value>'       append to a top-level list (skipped if already present)
  state_tx.py remove <list> '<json value>'       remove a value from a top-level list
  state_tx.py clear <list>                       empty a top-level list
  state_tx.py summary                            one line per active task + pending lists (read this, not `get`)
  state_tx.py keys                               every known task key, active and archived (new-card detection)
  state_tx.py statuses                           {task key: status} for active and archived tasks
  state_tx.py archive [--days N]                 move merged/skipped/declined/done tasks untouched for N days
                                                 (default 3) to state-archive.json; prints the moved keys
  state_tx.py archived <task-key>                print one archived task
  state_tx.py restore <task-key>                 move an archived task back into state.json
  state_tx.py next-question                      reserve the next question number and print it ("S21")
"""
import fcntl
import json
import os
import re
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

STATE_DIR = Path.home() / ".claude" / "pinqloq-task-runner"
STATE_FILE = STATE_DIR / "state.json"
STATE_LOCK_FILE = STATE_DIR / "state.json.lock"
LAST_BACKUP_FILE = STATE_DIR / "state.json.bak-last"
ARCHIVE_FILE = STATE_DIR / "state-archive.json"
EMPTY_STATE = {"tasks": {}, "proposals": []}
ARCHIVABLE_STATUSES = {"merged", "skipped", "declined", "done"}
DEFAULT_ARCHIVE_AFTER_DAYS = 3
SUMMARY_FIELDS = ["pr_url", "backend_pr", "core_pr", "blocked_by", "queue_priority", "pending_backend_verification"]


@contextmanager
def locked_state():
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with open(STATE_LOCK_FILE, "a") as lock_stream:
        fcntl.flock(lock_stream, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_stream, fcntl.LOCK_UN)


def read_state():
    if not STATE_FILE.exists():
        return json.loads(json.dumps(EMPTY_STATE))
    return json.loads(STATE_FILE.read_text())


def write_state(state):
    if STATE_FILE.exists():
        LAST_BACKUP_FILE.write_text(STATE_FILE.read_text())
    temporary_file = STATE_FILE.with_name("state.json.tmp.%d" % os.getpid())
    temporary_file.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n")
    os.replace(str(temporary_file), str(STATE_FILE))


def read_archive():
    if not ARCHIVE_FILE.exists():
        return {"tasks": {}}
    return json.loads(ARCHIVE_FILE.read_text())


def write_archive(archive):
    temporary_file = ARCHIVE_FILE.with_name("state-archive.json.tmp.%d" % os.getpid())
    temporary_file.write_text(json.dumps(archive, ensure_ascii=False, indent=2) + "\n")
    os.replace(str(temporary_file), str(ARCHIVE_FILE))


def parse_timestamp(timestamp):
    parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def is_archivable(task, cutoff):
    if task.get("status") not in ARCHIVABLE_STATUSES:
        return False
    updated_at = task.get("updated_at")
    return updated_at is None or parse_timestamp(updated_at) < cutoff


def archive_finished_tasks(archive_after_days):
    cutoff = datetime.now(timezone.utc) - timedelta(days=archive_after_days)
    with locked_state():
        state = read_state()
        archive = read_archive()
        moved_keys = [key for key, task in state.get("tasks", {}).items() if is_archivable(task, cutoff)]
        if not moved_keys:
            return []
        for key in moved_keys:
            archive["tasks"][key] = state["tasks"].pop(key)
        write_archive(archive)
        write_state(state)
        return moved_keys


def restore_task(task_key):
    with locked_state():
        state = read_state()
        archive = read_archive()
        if task_key not in archive["tasks"]:
            return False
        state.setdefault("tasks", {})[task_key] = archive["tasks"].pop(task_key)
        write_state(state)
        write_archive(archive)
        return True


def read_task_statuses():
    with locked_state():
        state = read_state()
        archive = read_archive()
    statuses = {key: task.get("status") for key, task in archive["tasks"].items()}
    statuses.update({key: task.get("status") for key, task in state.get("tasks", {}).items()})
    return statuses


def summarize_task(task_key, task):
    parts = [task_key, task.get("status", "?"), (task.get("updated_at") or "")[:16]]
    parts += ["%s=%s" % (field, json.dumps(task[field], ensure_ascii=False))
              for field in SUMMARY_FIELDS if task.get(field) not in (None, [], "")]
    if task.get("open_questions"):
        parts.append("open_questions=%d" % len(task["open_questions"]))
    return "  ".join(parts)


def print_summary():
    with locked_state():
        state = read_state()
        archive = read_archive()
    for task_key, task in sorted(state.get("tasks", {}).items(), key=lambda item: item[1].get("status", "")):
        print(summarize_task(task_key, task))
    print("pending_report=%s" % json.dumps(state.get("pending_report", []), ensure_ascii=False))
    print("pending_announcements=%d" % len(state.get("pending_announcements", [])))
    print("archived_tasks=%d (state_tx.py archived <key>)" % len(archive["tasks"]))


QUESTION_NUMBER_PATTERN = re.compile(r"\bS(\d+)\b")


def highest_used_question_number(state, archive):
    # Seeds the counter from every question number already mailed, so the first reserved number
    # never repeats one the team has seen.
    text = json.dumps(state, ensure_ascii=False) + json.dumps(archive, ensure_ascii=False)
    return max([int(number) for number in QUESTION_NUMBER_PATTERN.findall(text)] or [0])


def reserve_question_number():
    with locked_state():
        state = read_state()
        last_number = state.get("last_question_number")
        if last_number is None:
            last_number = highest_used_question_number(state, read_archive())
        state["last_question_number"] = last_number + 1
        write_state(state)
        return state["last_question_number"]


def merge_patch(target, patch):
    if not isinstance(patch, dict):
        return patch
    merged = dict(target) if isinstance(target, dict) else {}
    for key, value in patch.items():
        if value is None:
            merged.pop(key, None)
        else:
            merged[key] = merge_patch(merged.get(key), value)
    return merged


def read_value(state, dotted_path):
    value = state
    for part in dotted_path.split("."):
        value = value[part]
    return value


def update_state(change):
    with locked_state():
        state = read_state()
        updated_state = change(state)
        write_state(updated_state)
        return updated_state


def main():
    arguments = sys.argv[1:]
    command = arguments[0] if arguments else ""

    if command == "get":
        with locked_state():
            state = read_state()
        print(json.dumps(read_value(state, arguments[1]) if len(arguments) > 1 else state, ensure_ascii=False, indent=2))
        return

    if command == "next-question":
        print("S%d" % reserve_question_number())
        return

    if command == "summary":
        print_summary()
        return

    if command == "keys":
        print("\n".join(sorted(read_task_statuses())))
        return

    if command == "statuses":
        print(json.dumps(read_task_statuses(), ensure_ascii=False, indent=1))
        return

    if command == "archive":
        archive_after_days = DEFAULT_ARCHIVE_AFTER_DAYS
        if "--days" in arguments:
            archive_after_days = float(arguments[arguments.index("--days") + 1])
        moved_keys = archive_finished_tasks(archive_after_days)
        print("archived %d%s" % (len(moved_keys), (": " + ", ".join(moved_keys)) if moved_keys else ""))
        return

    if command == "archived" and len(arguments) == 2:
        with locked_state():
            archived_task = read_archive()["tasks"].get(arguments[1])
        if archived_task is None:
            print("not archived: %s" % arguments[1])
            sys.exit(4)
        print(json.dumps(archived_task, ensure_ascii=False, indent=2))
        return

    if command == "restore" and len(arguments) == 2:
        if not restore_task(arguments[1]):
            print("not archived: %s" % arguments[1])
            sys.exit(4)
        print("restored")
        return

    if command == "task" and len(arguments) == 2:
        task_key = arguments[1]
        patch = json.load(sys.stdin)

        def change(state):
            state.setdefault("tasks", {})[task_key] = merge_patch(state["tasks"].get(task_key, {}), patch)
            return state

        print(json.dumps(update_state(change)["tasks"][task_key], ensure_ascii=False, indent=2))
        return

    if command == "patch":
        patch = json.load(sys.stdin)
        update_state(lambda state: merge_patch(state, patch))
        print("ok")
        return

    if command in ("append", "remove") and len(arguments) == 3:
        list_name = arguments[1]
        value = json.loads(arguments[2])

        def change(state):
            values = state.setdefault(list_name, [])
            if command == "append" and value not in values:
                values.append(value)
            if command == "remove":
                state[list_name] = [existing for existing in values if existing != value]
            return state

        print(json.dumps(update_state(change)[list_name], ensure_ascii=False))
        return

    if command == "clear" and len(arguments) == 2:
        list_name = arguments[1]

        def change(state):
            state[list_name] = []
            return state

        update_state(change)
        print("ok")
        return

    print(__doc__, file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
