#!/usr/bin/env python3
"""Local web panel for the pinqloq task runner.

  python3 ~/.claude/pinqloq-panel/server.py [--port 8787]

Serves index.html and a small JSON API on 127.0.0.1 only. It reads the runner's files directly and
changes state.json only through state_tx.py. It never reads test-accounts.json or any secret.
"""
import json
import re
import subprocess
import sys
import threading
import time
from collections import Counter, deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

PANEL_DIR = Path(__file__).resolve().parent
STATE_DIR = Path.home() / ".claude" / "pinqloq-task-runner"
SCRIPTS_DIR = Path.home() / ".claude" / "skills" / "pinqloq-task-runner" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
import runner_config  # noqa: E402

TRANSCRIPT_DIR = runner_config.transcript_dir_for(runner_config.read_machine_config()["runner_dir"])
SCHEDULED_TASK_DIR = Path.home() / ".claude" / "scheduled-tasks"
LOCK_DIR = STATE_DIR / "locks"
START_REQUESTS_FILE = STATE_DIR / "start-requests.jsonl"
APP_USAGE_HISTORY_FILE = Path.home() / "Library" / "Application Support" / "Claude" / "plan-usage-history.json"
LIVE_USAGE_FILE = STATE_DIR / "usage-live.json"
USAGE_HISTORY_DAYS = 7

DEFAULT_PORT = 8787
LOCK_MAX_AGE_SECONDS = 75 * 60
ACTIVE_SESSION_SECONDS = 10 * 60
SESSION_LOOKBACK_SECONDS = 36 * 3600
MAX_LISTED_SESSIONS = 20
RECENT_EVENT_COUNT = 40
RECENT_SUBAGENT_EVENT_COUNT = 15
RUNS_LOG_LINE_COUNT = 60
SUMMARY_TEXT_LENGTH = 240

RUNNER_TASK_NAMES = ["pinqloq-task-runner", "pinqloq-task-runner-2", "pinqloq-task-runner-3"]
RUNNER_GITHUB_LOGIN = "pinq-ponq"
RUNNER_LABELS = {"pinqloq-task-runner": "runner-1", "pinqloq-task-runner-2": "runner-2", "pinqloq-task-runner-3": "runner-3"}
TASK_KEY_PATTERN = re.compile(r"^[\w.-]+/[\w.-]+#\d+$")
TASK_KEY_MENTION_PATTERN = re.compile(r"pinqponq/[\w.-]+#\d+")
MAX_MODEL_TURN_SECONDS = 30 * 60
METRICS_DEFAULT_DAYS = 7
MAX_METRICS_SESSIONS = 80
SCHEDULED_TASK_NAME_PATTERN = re.compile(r'<scheduled-task name=\\?"([\w-]+)\\?"')
RUNNER_SESSION_PATTERN = re.compile(r"\b((?:scheduled|manual)-\d{14})\b")
QUEUEABLE_STATUSES = {None, "proposed", "skipped", "declined", "selected"}
PRIORITY_EDITABLE_STATUSES = {"selected", "in_progress", "changes_requested"}
MAX_ANSWER_LENGTH = 2000
CLAIMABLE_STATUS_ORDER = ["changes_requested", "in_progress", "selected"]


def utc_now_text():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_json_file(path, default_value):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default_value


def shorten(text, length=SUMMARY_TEXT_LENGTH):
    single_line = " ".join(str(text).split())
    return single_line if len(single_line) <= length else single_line[: length - 1] + "…"


class TranscriptSummary:
    """Incrementally parsed view of one session transcript (.jsonl), re-reading only appended bytes."""

    def __init__(self, path, recent_event_count):
        self.path = path
        self.read_offset = 0
        self.tool_call_count = 0
        self.peak_context_tokens = 0
        self.input_tokens = 0
        self.cache_creation_tokens = 0
        self.cache_read_tokens = 0
        self.ended_turn = False
        self.output_tokens = 0
        self.model_seconds = 0.0
        self.tool_seconds = Counter()
        self.tool_counts = Counter()
        self.task_key_mentions = Counter()
        self.seen_message_ids = set()
        self.pending_tool_uses = {}
        self.last_user_epoch = None
        self.started_at = None
        self.last_event_at = None
        self.last_message_epoch = 0
        self.scheduled_task_name = None
        self.runner_session = None
        self.events = deque(maxlen=recent_event_count)

    def refresh(self):
        file_size = self.path.stat().st_size
        if file_size < self.read_offset:
            self.__init__(self.path, self.events.maxlen)
        if file_size == self.read_offset:
            return
        with open(self.path, "rb") as stream:
            stream.seek(self.read_offset)
            appended_bytes = stream.read()
        last_newline = appended_bytes.rfind(b"\n")
        if last_newline < 0:
            return
        self.read_offset += last_newline + 1
        for raw_line in appended_bytes[: last_newline + 1].splitlines():
            self.consume_line(raw_line)

    def consume_line(self, raw_line):
        if self.scheduled_task_name is None and b"<scheduled-task name=" in raw_line:
            name_match = SCHEDULED_TASK_NAME_PATTERN.search(raw_line.decode("utf-8", "replace"))
            if name_match:
                self.scheduled_task_name = name_match.group(1)
        if self.runner_session is None and (b"scheduled-" in raw_line or b"manual-" in raw_line) and b"session" in raw_line:
            session_match = RUNNER_SESSION_PATTERN.search(raw_line.decode("utf-8", "replace"))
            if session_match:
                self.runner_session = session_match.group(1)
        try:
            entry = json.loads(raw_line)
        except ValueError:
            return
        if entry.get("type") == "cost-state":
            return
        timestamp = entry.get("timestamp")
        if timestamp:
            self.started_at = self.started_at or timestamp
            self.last_event_at = timestamp
        entry_type = entry.get("type")
        if entry_type not in ("assistant", "user") or not timestamp:
            return
        entry_epoch = parse_timestamp(timestamp)
        self.last_message_epoch = entry_epoch
        message = entry.get("message") or {}
        if entry_type == "user":
            self.consume_user_message(message, entry_epoch)
            return
        self.consume_assistant_message(message, timestamp, entry_epoch)

    def consume_user_message(self, message, entry_epoch):
        self.last_user_epoch = entry_epoch
        self.ended_turn = False
        content = message.get("content")
        if not isinstance(content, list):
            return
        for content_block in content:
            if content_block.get("type") != "tool_result":
                continue
            pending_tool_use = self.pending_tool_uses.pop(content_block.get("tool_use_id"), None)
            if pending_tool_use:
                tool_label, started_epoch = pending_tool_use
                self.tool_seconds[tool_label] += max(0.0, entry_epoch - started_epoch)

    def consume_assistant_message(self, message, timestamp, entry_epoch):
        message_id = message.get("id")
        if message_id not in self.seen_message_ids:
            self.seen_message_ids.add(message_id)
            self.consume_usage(message.get("usage") or {})
            if self.last_user_epoch is not None and 0 <= entry_epoch - self.last_user_epoch < MAX_MODEL_TURN_SECONDS:
                self.model_seconds += entry_epoch - self.last_user_epoch
            self.last_user_epoch = None
        for content_block in message.get("content") or []:
            self.consume_content_block(content_block, timestamp, entry_epoch)
        self.ended_turn = message.get("stop_reason") == "end_turn"

    def consume_usage(self, usage):
        context_tokens = (usage.get("input_tokens", 0) + usage.get("cache_read_input_tokens", 0)
                          + usage.get("cache_creation_input_tokens", 0))
        self.peak_context_tokens = max(self.peak_context_tokens, context_tokens)
        self.input_tokens += usage.get("input_tokens", 0)
        self.cache_creation_tokens += usage.get("cache_creation_input_tokens", 0)
        self.cache_read_tokens += usage.get("cache_read_input_tokens", 0)
        self.output_tokens += usage.get("output_tokens", 0)

    def consume_content_block(self, content_block, timestamp, entry_epoch):
        block_type = content_block.get("type")
        if block_type == "text" and content_block.get("text", "").strip():
            self.events.append({"at": timestamp, "kind": "text", "summary": shorten(content_block["text"])})
        elif block_type == "tool_use":
            self.tool_call_count += 1
            tool_name = content_block.get("name", "")
            tool_input = content_block.get("input") or {}
            tool_label = metric_label_for_tool(tool_name, tool_input)
            self.tool_counts[tool_label] += 1
            self.pending_tool_uses[content_block.get("id")] = (tool_label, entry_epoch)
            for task_key in TASK_KEY_MENTION_PATTERN.findall(json.dumps(tool_input)):
                self.task_key_mentions[task_key] += 1
            self.events.append({"at": timestamp, "kind": "agent" if tool_name in ("Agent", "Task") else "tool",
                                "tool": tool_name, "summary": describe_tool_call(tool_name, tool_input)})

    def metrics(self):
        return {
            "tool_calls": self.tool_call_count,
            "peak_context_tokens": self.peak_context_tokens,
            "input_tokens": self.input_tokens,
            "cache_creation_tokens": self.cache_creation_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "output_tokens": self.output_tokens,
            "model_seconds": round(self.model_seconds),
            "wall_seconds": round(parse_timestamp(self.last_event_at) - parse_timestamp(self.started_at)) if self.started_at else 0,
            "tool_seconds": {label: round(seconds) for label, seconds in self.tool_seconds.most_common()},
            "tool_counts": dict(self.tool_counts.most_common()),
            "main_task": self.task_key_mentions.most_common(1)[0][0] if self.task_key_mentions else None,
            "pending_tool": self.describe_pending_tool(),
        }

    def describe_pending_tool(self):
        if not self.pending_tool_uses:
            return None
        tool_label, started_epoch = max(self.pending_tool_uses.values(), key=lambda pending: pending[1])
        return {"tool": tool_label, "waiting_seconds": int(time.time() - started_epoch)}


def parse_timestamp(timestamp):
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).timestamp()


def metric_label_for_tool(tool_name, tool_input):
    if tool_name in ("Agent", "Task"):
        return "Agent: " + current_agent_type(tool_input.get("subagent_type", "agent"))
    if tool_name.startswith("mcp__"):
        return "MCP: " + tool_name.split("__", 2)[-1]
    return tool_name


def describe_tool_call(tool_name, tool_input):
    """Short, secret-free description: the tool's own description field or a path, never a full command."""
    if tool_name in ("Agent", "Task"):
        return "%s: %s" % (current_agent_type(tool_input.get("subagent_type", "agent")), tool_input.get("description", ""))
    if tool_input.get("description"):
        return shorten(tool_input["description"])
    for path_field in ("file_path", "path", "notebook_path"):
        if tool_input.get(path_field):
            return Path(str(tool_input[path_field])).name
    if tool_name == "Skill":
        return tool_input.get("skill", "")
    if tool_input.get("pattern"):
        return shorten(tool_input["pattern"], 80)
    return ""


class TranscriptIndex:
    def __init__(self):
        self.summaries = {}
        self.refresh_lock = threading.Lock()

    def summary_for(self, path, recent_event_count):
        summary = self.summaries.get(path)
        if summary is None:
            summary = self.summaries[path] = TranscriptSummary(path, recent_event_count)
        summary.refresh()
        return summary

    def list_sessions(self):
        with self.refresh_lock:
            return [self.describe_session(path, time.time(), include_events=True)
                    for path in self.recent_transcript_files(SESSION_LOOKBACK_SECONDS, MAX_LISTED_SESSIONS)]

    def list_session_metrics(self, days):
        with self.refresh_lock:
            return [self.describe_session(path, time.time(), include_events=False)
                    for path in self.recent_transcript_files(days * 86400, MAX_METRICS_SESSIONS)]

    def recent_transcript_files(self, lookback_seconds, limit):
        now = time.time()
        transcript_files = [path for path in TRANSCRIPT_DIR.glob("*.jsonl") if now - path.stat().st_mtime < lookback_seconds]
        transcript_files.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        return transcript_files[:limit]

    def describe_session(self, path, now, include_events):
        summary = self.summary_for(path, RECENT_EVENT_COUNT)
        seconds_since_write = now - summary.last_message_epoch
        pending_tool_use_ids = set(summary.pending_tool_uses)
        subagents = [self.describe_subagent(subagent_file, now, include_events, pending_tool_use_ids)
                     for subagent_file in sorted(path.with_suffix("").glob("subagents/*.jsonl"),
                                                 key=lambda subagent_path: subagent_path.stat().st_mtime)]
        held_lock_sessions = {lock["session"] for lock in read_locks() if not lock["stale"]}
        is_active = not summary.ended_turn and (seconds_since_write < ACTIVE_SESSION_SECONDS or any(agent["active"] for agent in subagents)
                     or (summary.runner_session is not None and summary.runner_session in held_lock_sessions))
        description = {
            "id": path.stem,
            "scheduled_task": summary.scheduled_task_name,
            "runner_session": summary.runner_session,
            "active": is_active,
            "seconds_since_write": int(seconds_since_write),
            "started_at": summary.started_at,
            "last_event_at": summary.last_event_at,
            "subagents": subagents,
            **summary.metrics(),
        }
        if include_events:
            description["events"] = list(summary.events)
        return description

    def describe_subagent(self, path, now, include_events, pending_tool_use_ids):
        summary = self.summary_for(path, RECENT_SUBAGENT_EVENT_COUNT)
        metadata = read_json_file(path.with_suffix(".meta.json"), {})
        seconds_since_write = now - summary.last_message_epoch
        description = {
            "id": path.stem,
            "type": current_agent_type(metadata.get("agentType", "agent")),
            "description": metadata.get("description", ""),
            # Finished when the parent has received the Agent tool's result, so a just-ended agent never looks alive.
            "active": metadata.get("toolUseId") in pending_tool_use_ids and seconds_since_write < ACTIVE_SESSION_SECONDS,
            "seconds_since_write": int(seconds_since_write),
            "started_at": summary.started_at,
            "last_event_at": summary.last_event_at,
            **summary.metrics(),
        }
        if include_events:
            description["events"] = list(summary.events)
        return description


def read_timing_totals(days):
    """Build/test/PIT/Maestro seconds per task and kind from timings.jsonl (written by the runner scripts)."""
    cutoff_epoch = time.time() - days * 86400
    totals = {}
    try:
        timing_lines = (STATE_DIR / "timings.jsonl").read_text().splitlines()
    except OSError:
        return []
    for raw_line in timing_lines:
        try:
            timing = json.loads(raw_line)
        except ValueError:
            continue
        if not timing.get("start") or parse_timestamp(timing["start"]) < cutoff_epoch:
            continue
        task_totals = totals.setdefault(timing.get("task") or "-", {"task": timing.get("task") or "-", "kinds": {}, "failed": 0})
        kind_totals = task_totals["kinds"].setdefault(timing.get("kind", "other"), {"seconds": 0, "count": 0})
        kind_totals["seconds"] += timing.get("seconds") or 0
        kind_totals["count"] += 1
        task_totals["failed"] += 1 if timing.get("exit") not in (0, None) else 0
    return sorted(totals.values(), key=lambda task_totals: -sum(kind["seconds"] for kind in task_totals["kinds"].values()))


def read_locks():
    locks = []
    now = time.time()
    for lock_file in sorted(LOCK_DIR.glob("*.lock")):
        try:
            content = lock_file.read_text().strip()
            age_seconds = now - lock_file.stat().st_mtime
        except OSError:
            continue
        session_match = re.search(r"session=(\S+)", content)
        locks.append({"name": lock_file.stem, "session": session_match.group(1) if session_match else None,
                      "age_seconds": int(age_seconds), "stale": age_seconds > LOCK_MAX_AGE_SECONDS})
    return locks


def read_runs_log():
    try:
        lines = (STATE_DIR / "runs.log").read_text().splitlines()
    except OSError:
        return []
    return list(reversed(lines[-RUNS_LOG_LINE_COUNT:]))


def read_runs_log_all():
    try:
        return (STATE_DIR / "runs.log").read_text().splitlines()[-400:]
    except OSError:
        return []


def read_start_requests():
    if not START_REQUESTS_FILE.exists():
        return []
    requests = []
    for raw_line in START_REQUESTS_FILE.read_text().splitlines():
        try:
            requests.append(json.loads(raw_line))
        except ValueError:
            continue
    return requests[-20:]


def epoch_to_text(epoch_seconds):
    return datetime.fromtimestamp(epoch_seconds, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_plan_usage():
    samples = read_json_file(APP_USAGE_HISTORY_FILE, {}).get("samples", [])
    cutoff_epoch = datetime.now(timezone.utc).timestamp() - USAGE_HISTORY_DAYS * 86400
    history = [{"at": epoch_to_text(sample["t"] / 1000), "five_hour": sample["u"].get("fh"), "weekly": sample["u"].get("sd")}
               for sample in samples if sample.get("t", 0) / 1000 >= cutoff_epoch and "u" in sample]
    current = None
    if history:
        latest = history[-1]
        current = {"captured_at": latest["at"], "source": "app",
                   "five_hour": {"percent": latest["five_hour"], "resets_at": None},
                   "weekly": {"percent": latest["weekly"], "resets_at": None}}
    live_usage = read_json_file(LIVE_USAGE_FILE, None)
    if live_usage and (current is None or live_usage.get("captured_at", "") > current["captured_at"]):
        current = {**live_usage, "source": "live"}
        history.append({"at": live_usage["captured_at"], "five_hour": live_usage["five_hour"]["percent"],
                        "weekly": live_usage["weekly"]["percent"]})
    return {"current": current, "history": history}


def build_tasks_view():
    state = read_json_file(STATE_DIR / "state.json", {"tasks": {}})
    board_items = read_json_file(STATE_DIR / "board_items.json", [])
    board_by_key = {item.get("key"): item for item in board_items if item.get("key")}
    tasks = []
    for task_key, task in state.get("tasks", {}).items():
        board_item = board_by_key.get(task_key, {})
        tasks.append({
            "key": task_key,
            "title": task.get("title") or board_item.get("title", ""),
            "status": task.get("status"),
            "column": board_item.get("status"),
            "queue_priority": task.get("queue_priority"),
            "updated_at": task.get("updated_at"),
            "pr_url": task.get("pr_url"),
            "blocked_by": task.get("blocked_by") or [],
            "open_questions": len(task.get("open_questions") or []),
            "questions": task.get("open_questions") or [],
            "selected_via": task.get("selected_via"),
            "skip_reason": task.get("skip_reason"),
            "needs_verification": bool(task.get("pending_backend_verification")) or task.get("status") == "verification_blocked",
        })
    queue = sorted((task for task in tasks if task["status"] in CLAIMABLE_STATUS_ORDER),
                   key=lambda task: (CLAIMABLE_STATUS_ORDER.index(task["status"]),
                                     task["queue_priority"] if task["queue_priority"] is not None else 1000,
                                     task["updated_at"] or ""))
    state_by_key = {task["key"]: task for task in tasks}
    board = [{"key": item["key"], "title": item.get("title", ""), "column": item.get("status"),
              "state": item.get("state"), "runner_status": (state_by_key.get(item["key"]) or {}).get("status")}
             for item in board_items if item.get("key") and RUNNER_GITHUB_LOGIN in (item.get("assignees") or [])]
    board_file = STATE_DIR / "board_items.json"
    board_updated_at = (datetime.fromtimestamp(board_file.stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                        if board_file.exists() else None)
    return {"tasks": tasks, "queue": queue, "board": board, "board_updated_at": board_updated_at,
            "last_housekeeping_at": state.get("last_housekeeping_at")}


def run_state_tx(arguments, input_text=None):
    completed = subprocess.run([sys.executable, str(SCRIPTS_DIR / "state_tx.py")] + arguments,
                               input=input_text, capture_output=True, text=True, timeout=30)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "state_tx.py failed")
    return completed.stdout


def current_task_status(task_key):
    statuses = json.loads(run_state_tx(["statuses"]))
    return statuses.get(task_key)


def queue_task(request_body):
    task_key = str(request_body.get("key", ""))
    priority = int(request_body.get("priority", 5))
    if not TASK_KEY_PATTERN.match(task_key):
        raise ValueError("geçersiz task anahtarı")
    status = current_task_status(task_key)
    if status not in QUEUEABLE_STATUSES:
        raise ValueError("%s durumundaki task sıraya alınamaz (%s)" % (task_key, status))
    board_items = read_json_file(STATE_DIR / "board_items.json", [])
    board_title = next((item.get("title", "") for item in board_items if item.get("key") == task_key), "")
    patch = {"status": "selected", "queue_priority": priority,
             "selected_via": "owner web panel %s" % utc_now_text()[:10], "updated_at": utc_now_text()}
    if status is None and board_title:
        patch["title"] = board_title
    run_state_tx(["task", task_key], json.dumps(patch))
    return {"key": task_key, "previous_status": status, "status": "selected", "queue_priority": priority}


def set_task_priority(request_body):
    task_key = str(request_body.get("key", ""))
    priority = int(request_body.get("priority"))
    status = current_task_status(task_key)
    if status not in PRIORITY_EDITABLE_STATUSES:
        raise ValueError("%s durumunda öncelik değiştirilemez (%s)" % (task_key, status))
    run_state_tx(["task", task_key], json.dumps({"queue_priority": priority}))
    return {"key": task_key, "queue_priority": priority}


def unqueue_task(request_body):
    task_key = str(request_body.get("key", ""))
    status = current_task_status(task_key)
    if status != "selected":
        raise ValueError("yalnızca 'selected' task sıradan çıkarılır (%s)" % status)
    run_state_tx(["task", task_key], json.dumps({"status": "proposed", "queue_priority": None,
                                                 "selected_via": None, "updated_at": utc_now_text()}))
    return {"key": task_key, "status": "proposed"}


def question_id_of(question_text):
    return question_text.split(":", 1)[0].strip()


def answer_question(request_body):
    task_key = str(request_body.get("key", ""))
    question_id = str(request_body.get("question", "")).strip()
    answer_text = " ".join(str(request_body.get("answer", "")).split())
    if not TASK_KEY_PATTERN.match(task_key):
        raise ValueError("geçersiz task anahtarı")
    if not answer_text:
        raise ValueError("cevap boş olamaz")
    if len(answer_text) > MAX_ANSWER_LENGTH:
        raise ValueError("cevap en fazla %d karakter olabilir" % MAX_ANSWER_LENGTH)
    try:
        task = json.loads(run_state_tx(["get", "tasks.%s" % task_key]))
    except RuntimeError as error:
        raise ValueError("%s state.json'da yok" % task_key) from error
    open_questions = task.get("open_questions") or []
    question_text = next((question for question in open_questions if question_id_of(question) == question_id), None)
    if question_text is None:
        raise ValueError("%s için açık %s sorusu yok" % (task_key, question_id))
    remaining_questions = [question for question in open_questions if question is not question_text]
    answer = {"from": "owner (web panel)", "received_at": utc_now_text(),
              "summary": "%s: %s (soru: %s)" % (question_id, answer_text, question_text.split(":", 1)[-1].strip())}
    patch = {"open_questions": remaining_questions, "answers": (task.get("answers") or []) + [answer],
             "updated_at": utc_now_text()}
    if not remaining_questions and task.get("status") == "waiting_reply":
        patch["status"] = "in_progress"
    run_state_tx(["task", task_key], json.dumps(patch))
    return {"key": task_key, "question": question_id, "status": patch.get("status", task.get("status")),
            "remaining_questions": len(remaining_questions)}


def request_runner_start(request_body):
    scheduled_task = str(request_body.get("scheduled_task", ""))
    if scheduled_task not in RUNNER_TASK_NAMES:
        raise ValueError("bilinmeyen runner")
    start_request = {"requested_at": utc_now_text(), "scheduled_task": scheduled_task, "status": "pending"}
    with open(START_REQUESTS_FILE, "a") as stream:
        stream.write(json.dumps(start_request) + "\n")
    return start_request


RENAMED_AGENT_TYPES = {"pin-drill": "pin-test", "pin-rally": "pin-device", "pin-umpire": "pin-review"}


def current_agent_type(agent_type):
    return RENAMED_AGENT_TYPES.get(agent_type, agent_type)


SKILL_DIR = Path.home() / ".claude" / "skills" / "pinqloq-task-runner"
AGENT_DIR = Path.home() / ".claude" / "agents"
MAX_VIEWABLE_FILE_BYTES = 400_000
JSONL_TAIL_LINE_COUNT = 150
NEVER_VIEWABLE_FILE_NAMES = {"test-accounts.json"}
SCHEDULE_LABELS = {name: "elle başlatılır" for name in RUNNER_TASK_NAMES}
MAP_GROUPS = [
    ("trigger", "Tetikleyiciler"), ("prompt", "Runner promptları"), ("skill", "Skill ve dokümanlar"),
    ("agent", "Agentlar"), ("script", "Scriptler"), ("state", "Durum dosyaları"), ("external", "Dış sistemler"),
]
EXTERNAL_NODES = [
    ("github", "GitHub (Project #9, issue, PR)", "gh CLI ile board, issue, PR ve yorumlar",
     [r"\bgh (api|pr|issue|project|repo)\b", r"Project #9", r"project_number"]),
    ("mail", "Mail gönderimi (SMTP + Keychain)", "Takıma öneri, soru ve özet mailleri; gelen mail okunmaz; şifre Keychain'de",
     [r"smtplib", r"keychain"]),
    ("pinqloq-mcp", "pinqloq MCP (loglar)", "rindle_http / rindle_client log sorguları",
     [r"mcp__pinqloq", r"pinqloq MCP", r"rindle_http"]),
    ("devices", "Cihazlar (emülatör, simülatör, Maestro)", "Android emülatör, iOS simülatör, Maestro akışları",
     [r"\bmaestro\b", r"\badb\b", r"simctl"]),
    ("worktrees", "Git worktree'leri", "Her task için ayrı worktree; kullanıcının checkout'u değişmez",
     [r"worktree"]),
    ("pinq-doq", "pinq-doq kuralları ve skilleri", "Repo kuralları (.claude/rules), pinq_code-review ve pinq_* skilleri",
     [r"pinq-doq", r"pinq_code-review", r"pinq_add-feature"]),
]


def read_front_matter(text):
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    fields = {}
    for line in text[3:end].splitlines():
        if ":" in line:
            field_name, _, field_value = line.partition(":")
            fields[field_name.strip()] = field_value.strip()
    return fields


def read_docstring_first_line(text):
    docstring_match = re.search(r'"""(.+?)(\n|""")', text)
    return docstring_match.group(1).strip() if docstring_match else ""


def describe_file_node(node_id, group, path, label=None):
    stat = path.stat()
    is_text = path.suffix in (".md", ".py", ".json", ".jsonl", ".log", ".gradle", ".txt") or path.is_dir()
    text = path.read_text(errors="replace") if path.is_file() and is_text and stat.st_size < 2_000_000 else ""
    front_matter = read_front_matter(text)
    description = front_matter.get("description") or (read_docstring_first_line(text) if path.suffix == ".py" else "")
    return {"id": node_id, "group": group, "label": label or path.name, "path": str(path).replace(str(Path.home()), "~"),
            "description": description, "model": front_matter.get("model"), "size": stat.st_size if path.is_file() else None,
            "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "viewable": path.is_file() and is_text and path.name not in NEVER_VIEWABLE_FILE_NAMES,
            "match_tokens": [re.escape(path.name)] + ([re.escape(path.stem)] if group == "agent" else []),
            "_path": path, "_text": text if path.name not in NEVER_VIEWABLE_FILE_NAMES else ""}


def is_backup_file(path):
    return ".bak" in path.name or path.name.endswith(".lock")


def collect_map_nodes():
    nodes = []
    nodes.append({"id": "trigger:panel", "group": "trigger", "label": "Panel (Başlat, sıra)",
                  "description": "Başlat isteği yazar, sırayı state_tx.py ile değiştirir", "path": None, "viewable": False,
                  "match_tokens": [], "_text": "", "_uses": ["state:start-requests.jsonl", "script:state_tx.py"]})
    for task_dir in sorted(SCHEDULED_TASK_DIR.iterdir()) if SCHEDULED_TASK_DIR.is_dir() else []:
        prompt_file = task_dir / "SKILL.md"
        if task_dir.name not in RUNNER_TASK_NAMES or not prompt_file.exists():
            continue
        nodes.append({"id": "trigger:" + task_dir.name, "group": "trigger", "label": RUNNER_LABELS[task_dir.name],
                      "description": SCHEDULE_LABELS.get(task_dir.name, "zamanlanmış görev"), "path": None,
                      "viewable": False, "match_tokens": [], "_text": "", "_uses": ["prompt:" + task_dir.name]})
        prompt_node = describe_file_node("prompt:" + task_dir.name, "prompt", prompt_file, RUNNER_LABELS[task_dir.name] + " promptu")
        prompt_node["match_tokens"] = []
        nodes.append(prompt_node)
    skill_files = [SKILL_DIR / "SKILL.md", SKILL_DIR / "config.json"]
    skill_files += sorted(SKILL_DIR.glob("references/*.md")) + sorted(SKILL_DIR.glob("templates/*"))
    for path in skill_files:
        if path.exists() and not is_backup_file(path):
            node = describe_file_node("skill:" + path.relative_to(SKILL_DIR).as_posix(), "skill", path,
                                      "skill SKILL.md" if path == SKILL_DIR / "SKILL.md" else None)
            if path == SKILL_DIR / "SKILL.md":
                node["match_tokens"] = [r"pinqloq-task-runner` skill", r"skills/pinqloq-task-runner/SKILL\.md"]
            nodes.append(node)
    for path in sorted(AGENT_DIR.glob("pin-*.md")):
        nodes.append(describe_file_node("agent:" + path.stem, "agent", path, path.stem))
    for path in sorted(SCRIPTS_DIR.iterdir()):
        if path.is_file() and not is_backup_file(path):
            nodes.append(describe_file_node("script:" + path.name, "script", path))
    for path in sorted(STATE_DIR.iterdir()):
        if is_backup_file(path) or path.name.startswith(".") or path.suffix == ".md":
            continue
        node = describe_file_node("state:" + path.name, "state", path, path.name + ("/" if path.is_dir() else ""))
        if path.is_dir():
            node["description"] = "%d dosya" % sum(1 for _ in path.iterdir())
            node["match_tokens"] = [re.escape(path.name) + "/"]
        nodes.append(node)
    for node_id, label, description, match_tokens in EXTERNAL_NODES:
        nodes.append({"id": "external:" + node_id, "group": "external", "label": label, "description": description,
                      "path": None, "viewable": False, "match_tokens": match_tokens, "_text": ""})
    return nodes


def compute_map_edges(nodes):
    edges = set()
    compiled_tokens = [(node["id"], re.compile("|".join(node["match_tokens"]), re.IGNORECASE if node["group"] == "external" else 0))
                       for node in nodes if node["match_tokens"]]
    for node in nodes:
        for used_id in node.get("_uses", []):
            edges.add((node["id"], used_id))
        if not node["_text"]:
            continue
        for target_id, token_pattern in compiled_tokens:
            if target_id != node["id"] and token_pattern.search(node["_text"]):
                edges.add((node["id"], target_id))
    return [{"from": source_id, "to": target_id} for source_id, target_id in sorted(edges)]


def keep_reachable_from_triggers(nodes, edges):
    reachable_ids = {node["id"] for node in nodes if node["group"] == "trigger"}
    pending_ids = list(reachable_ids)
    while pending_ids:
        source_id = pending_ids.pop()
        for edge in edges:
            if edge["from"] == source_id and edge["to"] not in reachable_ids:
                reachable_ids.add(edge["to"])
                pending_ids.append(edge["to"])
    reachable_nodes = [node for node in nodes if node["id"] in reachable_ids]
    reachable_edges = [edge for edge in edges if edge["from"] in reachable_ids and edge["to"] in reachable_ids]
    return reachable_nodes, reachable_edges


def build_system_map():
    all_nodes = collect_map_nodes()
    nodes, edges = keep_reachable_from_triggers(all_nodes, compute_map_edges(all_nodes))
    public_nodes = [{key: value for key, value in node.items() if not key.startswith("_") and key != "match_tokens"}
                    for node in nodes]
    return {"groups": [{"id": group_id, "label": label} for group_id, label in MAP_GROUPS],
            "nodes": public_nodes, "edges": edges}


def read_map_file(node_id):
    node = next((candidate for candidate in collect_map_nodes() if candidate["id"] == node_id), None)
    if node is None or not node["viewable"]:
        raise ValueError("bu dosya görüntülenemez")
    path = node["_path"]
    if path.suffix == ".jsonl":
        lines = path.read_text(errors="replace").splitlines()
        return {"id": node_id, "truncated": len(lines) > JSONL_TAIL_LINE_COUNT,
                "content": "\n".join(lines[-JSONL_TAIL_LINE_COUNT:])}
    content = path.read_text(errors="replace")
    return {"id": node_id, "truncated": len(content) > MAX_VIEWABLE_FILE_BYTES, "content": content[:MAX_VIEWABLE_FILE_BYTES]}


transcript_index = TranscriptIndex()
POST_ROUTES = {"/api/queue": queue_task, "/api/priority": set_task_priority,
               "/api/unqueue": unqueue_task, "/api/start": request_runner_start,
               "/api/answer": answer_question}


class PanelHandler(BaseHTTPRequestHandler):
    allowed_hosts = set()

    def log_message(self, format_text, *arguments):
        pass

    def is_local_request(self):
        return self.headers.get("Host", "") in self.allowed_hosts

    def send_json(self, payload, status_code=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self.is_local_request():
            return self.send_json({"error": "forbidden host"}, 403)
        if self.path in ("/", "/index.html"):
            body = (PANEL_DIR / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            return self.wfile.write(body)
        if self.path == "/api/overview":
            return self.send_json({
                "now": utc_now_text(),
                "locks": read_locks(),
                "sessions": transcript_index.list_sessions(),
                "runs_log": read_runs_log(),
                "start_requests": read_start_requests(),
                "runner_names": [name for name in RUNNER_TASK_NAMES if (SCHEDULED_TASK_DIR / name).exists()],
                "runner_labels": RUNNER_LABELS,
                "plan_usage": read_plan_usage(),
                **build_tasks_view(),
            })
        if self.path.startswith("/api/metrics"):
            days_match = re.search(r"days=(\d+)", self.path)
            days = int(days_match.group(1)) if days_match else METRICS_DEFAULT_DAYS
            return self.send_json({"now": utc_now_text(), "days": days, "runs_log": read_runs_log_all(),
                                   "sessions": transcript_index.list_session_metrics(days),
                                   "timings": read_timing_totals(days)})
        if self.path == "/api/map":
            return self.send_json(build_system_map())
        if self.path.startswith("/api/file?id="):
            try:
                return self.send_json(read_map_file(unquote(self.path.split("=", 1)[1])))
            except ValueError as error:
                return self.send_json({"error": str(error)}, 400)
        self.send_json({"error": "not found"}, 404)

    def do_POST(self):
        # The custom header forces a CORS preflight, which this server never answers, so other origins cannot post.
        if not self.is_local_request() or self.headers.get("X-Pinqloq-Panel") != "1":
            return self.send_json({"error": "forbidden"}, 403)
        route = POST_ROUTES.get(self.path)
        if route is None:
            return self.send_json({"error": "not found"}, 404)
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            request_body = json.loads(self.rfile.read(content_length) or b"{}")
            return self.send_json(route(request_body))
        except (ValueError, TypeError, RuntimeError) as error:
            return self.send_json({"error": str(error)}, 400)


def main():
    port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else DEFAULT_PORT
    PanelHandler.allowed_hosts = {"127.0.0.1:%d" % port, "localhost:%d" % port}
    server = ThreadingHTTPServer(("127.0.0.1", port), PanelHandler)
    print("pinqponq-agents: http://127.0.0.1:%d" % port, flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
