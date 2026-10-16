#!/usr/bin/env python3
"""Decide cheaply whether a runner session has anything to do, before the model reads the skill.

Most runs used to end with "no new Todo cards, no comments, no PR reviews" after a full session.
This script answers that question with a handful of API calls (one cached board fetch, one batched
GraphQL query) and prints one JSON object:

  {"decision": "run" | "idle",
   "housekeeping": [...],   reasons for steps 1-4 / the card-column check (empty: skip those steps)
   "task_work": [...],      reasons for step 5 (claimable task, verification retries)
   "claimable": "<task key>" | null,
   "housekeeping_held_by_other": bool,
   "role": "primary" | "queue-only",
   "errors": [...]}

A queue-only machine (machine.json `role`) skips every housekeeping check: it only works on tasks
the owner queued on this machine, so a second machine never repeats the primary's proposals,
proposals or comment decisions.

  preflight.py [--new-session <prefix> | --log-idle <session>]
      --new-session generates the session id (<prefix>-<UTC yyyymmddHHMMSS>) and returns it as `session`;
      with either flag an idle result is also appended to runs.log

A check that fails counts as a reason to run (a session then looks properly), except a GitHub rate
limit, which a session could not get past either.
"""
import contextlib
import io
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import board  # noqa: E402
import locks  # noqa: E402
import runner_config  # noqa: E402
import state_tx  # noqa: E402

RUNS_LOG_FILE = state_tx.STATE_DIR / "runs.log"
VERIFICATION_RETRY_INTERVAL = timedelta(hours=6)
SESSION_RESERVATION_MAX_AGE_SECONDS = 24 * 60 * 60
RUNNER_COMMENT_PREFIX = "🤖"
STARTED_STATUSES = {"in_progress", "waiting_reply", "changes_requested", "verification_blocked"}
ISSUE_ACTIVITY_STATUSES = {"proposed", "waiting_reply", "pr_open"}
PULL_REQUEST_URL_PATTERN = re.compile(r"github\.com/([^/]+)/([^/]+)/pull/(\d+)")
TASK_KEY_PATTERN = re.compile(r"^([^/]+)/([^#]+)#(\d+)$")
RATE_LIMIT_MARKER = "rate limit"


def now_utc():
    return datetime.now(timezone.utc)


def parse_time(timestamp):
    return state_tx.parse_timestamp(timestamp) if timestamp else None


def check_project_scope():
    completed = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
    auth_output = completed.stdout + completed.stderr
    return [] if "'project'" in auth_output else ["gh token has no project scope (step 0.1 report)"]


def check_board(tasks, known_keys):
    reasons = []
    board_items = board.load_items()
    cards_by_key = {board_item["key"]: board_item for board_item in board_items if board_item["key"]}
    new_todo_keys = [board_item["key"] for board_item in board_items
                     if board_item["status"] == "Todo" and board_item["type"] == "Issue"
                     and board_item["key"] not in known_keys]
    if new_todo_keys:
        reasons.append("new Todo cards: " + ", ".join(new_todo_keys))
    for task_key, task in tasks.items():
        card = cards_by_key.get(task_key)
        if not card:
            continue
        allowed_columns = allowed_card_columns(task)
        if task.get("status") == "proposed" and card["status"] != "Todo":
            reasons.append("%s proposed but its card is in %s" % (task_key, card["status"]))
        elif allowed_columns and card["status"] not in allowed_columns:
            reasons.append("%s card in %s, should be %s" % (task_key, card["status"], allowed_columns[0]))
    return reasons


def allowed_card_columns(task):
    """First entry is where the runner puts the card; In Review and Done are set only by the team."""
    if task.get("status") == "pr_open":
        return ("Waiting for human review", "In Review", "Done")
    if task.get("status") in STARTED_STATUSES and task.get("branch") and not task.get("pr_url"):
        return ("In progress",)
    return ()


def pull_request_reference(pull_request_url):
    match = PULL_REQUEST_URL_PATTERN.search(pull_request_url or "")
    return (match.group(1), match.group(2), int(match.group(3))) if match else None


def issue_reference(task_key):
    match = TASK_KEY_PATTERN.match(task_key)
    return (match.group(1), match.group(2), int(match.group(3))) if match else None


COMMENT_FIELDS = "nodes { author { __typename login } createdAt body }"


def build_activity_query(tasks):
    """One GraphQL query with an alias per issue / pull request; returns (query, alias -> (task key, kind))."""
    query_parts = []
    aliases = {}
    for index, (task_key, task) in enumerate(sorted(tasks.items())):
        status = task.get("status")
        issue = issue_reference(task_key)
        if issue and status in ISSUE_ACTIVITY_STATUSES:
            alias = "issue%d" % index
            aliases[alias] = (task_key, "issue")
            query_parts.append('%s: repository(owner: "%s", name: "%s") { issue(number: %d) { comments(last: 10) { %s } } }'
                               % ((alias,) + issue + (COMMENT_FIELDS,)))
        pull_request_urls = []
        if status == "pr_open":
            pull_request_urls.append(("pr", task.get("pr_url")))
        if task.get("pending_backend_verification"):
            pull_request_urls.append(("backend_pr", task.get("backend_pr")))
        for pull_request_index, (kind, pull_request_url) in enumerate(pull_request_urls):
            pull_request = pull_request_reference(pull_request_url)
            if not pull_request:
                continue
            alias = "pr%d_%d" % (index, pull_request_index)
            aliases[alias] = (task_key, kind)
            query_parts.append(
                '%s: repository(owner: "%s", name: "%s") { pullRequest(number: %d) { state '
                'comments(last: 10) { %s } reviews(last: 10) { nodes { author { __typename login } createdAt: submittedAt body } } '
                'reviewThreads(last: 10) { nodes { comments(last: 3) { %s } } } } }'
                % ((alias,) + pull_request + (COMMENT_FIELDS, COMMENT_FIELDS)))
    return "query {\n%s\n}" % "\n".join(query_parts), aliases


def is_new_human_comment(comment, since):
    author = comment.get("author") or {}
    if author.get("__typename") == "Bot" or (author.get("login") or "").endswith("[bot]"):
        return False
    if (comment.get("body") or "").lstrip().startswith(RUNNER_COMMENT_PREFIX):
        return False
    created_at = parse_time(comment.get("createdAt"))
    return created_at is not None and (since is None or created_at > since)


def collect_comments(node):
    comments = list((node.get("comments") or {}).get("nodes", []))
    comments += [review for review in (node.get("reviews") or {}).get("nodes", []) if review.get("body")]
    for thread in (node.get("reviewThreads") or {}).get("nodes", []):
        comments += thread["comments"]["nodes"]
    return comments


def check_github_activity(tasks, last_housekeeping_at):
    """Returns (housekeeping reasons, task work, keys of tasks whose backend pull request is still open)."""
    reasons = []
    task_work = []
    waiting_on_backend = set()
    query, aliases = build_activity_query(tasks)
    if not aliases:
        return reasons, task_work, waiting_on_backend
    data = board.run_graphql(query, {})
    for alias, (task_key, kind) in aliases.items():
        repository = data.get(alias) or {}
        node = repository.get("issue") or repository.get("pullRequest") or {}
        # Comments older than the last finished housekeeping were already read by that session.
        since = max([moment for moment in (parse_time(tasks[task_key].get("updated_at")), last_housekeeping_at)
                     if moment] or [None])
        if kind == "pr" and node.get("state") in ("MERGED", "CLOSED"):
            reasons.append("%s PR is %s" % (task_key, node["state"].lower()))
        if kind == "backend_pr" and node.get("state") == "OPEN":
            waiting_on_backend.add(task_key)
        if kind == "backend_pr" and node.get("state") == "MERGED":
            task_work.append("%s backend PR merged: finish device/pinqloq verification" % task_key)
        new_comments = [comment for comment in collect_comments(node) if is_new_human_comment(comment, since)]
        if new_comments:
            authors = ", ".join(sorted({(comment.get("author") or {}).get("login", "?") for comment in new_comments}))
            reasons.append("%s: %d new comment(s)/review(s) on the %s by %s"
                           % (task_key, len(new_comments), "issue" if kind == "issue" else kind, authors))
    return reasons, task_work, waiting_on_backend


def check_verification_retries(tasks, waiting_on_backend):
    """A retry is pointless while the backend pull request the verification waits for is still open;
    the activity check reports the task as soon as that pull request is merged."""
    task_work = []
    for task_key, task in tasks.items():
        if task.get("status") != "verification_blocked" or task_key in waiting_on_backend:
            continue
        updated_at = parse_time(task.get("updated_at"))
        if updated_at is None or now_utc() - updated_at >= VERIFICATION_RETRY_INTERVAL:
            task_work.append("%s verification_blocked since %s: retry pinqloq" % (task_key, task.get("updated_at")))
    return task_work


def find_claimable_task(light_only):
    captured_output = io.StringIO()
    with contextlib.redirect_stdout(captured_output):
        exit_code = locks.print_claimable(light_only)
    lines = captured_output.getvalue().splitlines()
    return (lines[0] if exit_code == 0 else None), lines[1:]


def run_check(check, errors, *check_arguments):
    try:
        return check(*check_arguments)
    except Exception as error:  # every failure is reported in the JSON, never swallowed
        errors.append("%s: %s" % (check.__name__, error))
        return None


def collect_housekeeping(state, tasks, errors):
    """Returns (housekeeping reasons, task work found while reading GitHub activity)."""
    known_keys = set(state_tx.read_task_statuses())
    housekeeping = []
    task_work = []
    housekeeping += run_check(check_project_scope, errors) or []
    housekeeping += run_check(check_board, errors, tasks, known_keys) or []
    activity = run_check(check_github_activity, errors, tasks, parse_time(state.get("last_housekeeping_at")))
    waiting_on_backend = set()
    if activity:
        housekeeping += activity[0]
        task_work += activity[1]
        waiting_on_backend = activity[2]
    task_work += check_verification_retries(tasks, waiting_on_backend)
    return housekeeping, task_work


def evaluate(light_only=False):
    errors = []
    with state_tx.locked_state():
        state = state_tx.read_state()
    tasks = state.get("tasks", {})
    role = runner_config.read_machine_config()["role"]

    housekeeping, task_work = ([], []) if role == runner_config.QUEUE_ONLY_ROLE else collect_housekeeping(state, tasks, errors)
    if light_only:
        # Verification retries need device runs and the pinqloq backend; runner-3 leaves them to runners 1 and 2.
        task_work = []
    claimable_task, claim_skips = find_claimable_task(light_only)
    if claimable_task:
        task_work.insert(0, "claimable task: " + claimable_task)

    housekeeping_held_by_other = locks.is_held(locks.lock_file_for("housekeeping"))
    rate_limited = any(RATE_LIMIT_MARKER in error.lower() for error in errors)
    other_errors = [error for error in errors if RATE_LIMIT_MARKER not in error.lower()]
    needs_housekeeping = bool(housekeeping or other_errors) and not housekeeping_held_by_other
    should_run = (needs_housekeeping or bool(task_work)) and not (rate_limited and not task_work)
    return {
        "decision": "run" if should_run else "idle",
        "housekeeping": housekeeping,
        "task_work": task_work,
        "claimable": claimable_task,
        "claim_skips": claim_skips,
        "housekeeping_held_by_other": housekeeping_held_by_other,
        "role": role,
        "errors": errors,
    }


def append_idle_log(session, result):
    details = "; ".join(result["claim_skips"] + result["errors"]) or "nothing to do"
    if result["housekeeping_held_by_other"]:
        details = "housekeeping held by another session; " + details
    line = "%s %s: preflight idle (%s)\n" % (now_utc().strftime("%Y-%m-%dT%H:%M:%SZ"), session, details)
    with open(RUNS_LOG_FILE, "a") as runs_log:
        runs_log.write(line)


def reserve_session_id(session_prefix):
    """Two runners started in the same second used to get the same id, shared one devices lock and drove
    the emulator together (2026-10-11); a reservation file per id makes the second one take the next second."""
    reservation_dir = state_tx.STATE_DIR / "session-ids"
    reservation_dir.mkdir(parents=True, exist_ok=True)
    for old_reservation in reservation_dir.glob("*"):
        if time.time() - old_reservation.stat().st_mtime > SESSION_RESERVATION_MAX_AGE_SECONDS:
            old_reservation.unlink(missing_ok=True)
    moment = now_utc()
    while True:
        session = "%s-%s" % (session_prefix, moment.strftime("%Y%m%d%H%M%S"))
        try:
            os.close(os.open(str(reservation_dir / session), os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            return session
        except FileExistsError:
            moment += timedelta(seconds=1)


def main():
    arguments = sys.argv[1:]
    session = None
    if "--new-session" in arguments:
        # The routine prompts call this with a fixed command (no $(date) / $VAR), so the app can
        # remember the permission; the session id is generated here instead of in the shell.
        session_prefix = arguments[arguments.index("--new-session") + 1]
        session = reserve_session_id(session_prefix)
    elif "--log-idle" in arguments:
        session = arguments[arguments.index("--log-idle") + 1]
    result = evaluate(locks.LIGHT_ONLY_FLAG in arguments)
    if session:
        result = {"session": session, **result}
    print(json.dumps(result, ensure_ascii=False, indent=1))
    if session and result["decision"] == "idle":
        append_idle_log(session, result)


if __name__ == "__main__":
    main()
