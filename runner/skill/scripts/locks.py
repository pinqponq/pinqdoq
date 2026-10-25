#!/usr/bin/env python3
"""Locks for running several pinqloq task runner sessions at the same time.

There is no global run lock any more. Instead:
  - every task a session works on is locked, so two sessions never work on the same task;
  - a task whose dependency (`blocked_by`) is locked or not yet ready is never claimed;
  - the shared steps (comment decisions, board scan, proposals, card-column check) run in one
    session at a time under the housekeeping lock; other sessions skip them;
  - each device has its own lock (devices-android, devices-ios), because two sessions driving the same
    emulator crash each other's Maestro runs (2026-09-30); one session can test on Android while
    another tests on iOS; devices-web is the browser for a web project's Playwright flows: a local dev server
    uses one fixed port per project, and every session signs in with the same test account;
  - both devices are signed into the same test couple (Android=test1, iOS=test2), so a flow that
    changes the couple's shared server state (unmatch/re-match, seeding or deleting shared media)
    also takes the devices-couple lock: an unmatch on one device changes what the other device sees.
  - the old single `devices.lock` (written before 2026-10-07) still blocks both devices until it is
    released or stale.

Every lock is a file created with O_EXCL. A lock untouched for 75 minutes is stale (its session died)
and is replaced by the next contender.

  locks.py claim <session>                 pick the next task this session may work on, lock it and print its key
                                           (exit 4 and print the reasons when nothing is claimable)
  locks.py claimable                       print the task `claim` would pick, without locking it (exit 4 when none)
  `claim` and `claimable` take a role (runner_config.RUNNER_ROLES): `--light-only` (runner-3) picks only tasks with
                                           `weight: "light"`; `--role no-device` (runner-4) only tasks with `needs_device: false`;
                                           `--role device` (runners 1 and 2) picks tasks that need a device (or whose need is
                                           unknown) first and a task without a device only when no device task is claimable
  locks.py lock <task-key> <session>       lock one specific task (exit 3 when held)
  locks.py touch <task-key>                refresh a task lock
  locks.py release <task-key>              release a task lock
  locks.py housekeeping acquire <session>  exit 0 when acquired, 3 when another session is doing it
  locks.py housekeeping touch|release
  locks.py devices acquire <session> [--platform android|ios|web|both|free] [--prefer android|ios] [--couple] [--task <task-key>] [--wait-minutes N]
                                           wait (default 90 min) until all requested locks are free, then take them
                                           together (all or nothing); --platform defaults to both (android and ios); touches the task
                                           lock while waiting; `free` takes whichever of Android and iOS is free (the
                                           `--prefer` one, default android, when both are) and prints which one it took
  locks.py devices touch|release <session> [--platform android|ios|web|both] [--couple]
                                           touch/release only the device locks this session holds (all of them when
                                           neither --platform nor --couple is given)
  locks.py status                          list all locks with age and owner
"""
import fcntl
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner_config  # noqa: E402

STATE_DIR = Path.home() / ".claude" / "pinqloq-task-runner"
LOCK_DIR = STATE_DIR / "locks"
CLAIM_MUTEX_FILE = LOCK_DIR / "claim.mutex"
STATE_TX_SCRIPT = Path(__file__).with_name("state_tx.py")
LOCK_MAX_AGE_SECONDS = 75 * 60
DEVICE_WAIT_POLL_SECONDS = 30
DEFAULT_DEVICE_WAIT_MINUTES = 90
PLATFORM_LOCK_NAMES = {"android": "devices-android", "ios": "devices-ios", "web": "devices-web"}
COUPLE_LOCK_NAME = "devices-couple"
LEGACY_DEVICES_LOCK_NAME = "devices"
ALL_DEVICE_LOCK_NAMES = ["devices-android", "devices-ios", "devices-web", COUPLE_LOCK_NAME, LEGACY_DEVICES_LOCK_NAME]
EXIT_LOCK_HELD = 3
EXIT_NOTHING_CLAIMABLE = 4

CLAIMABLE_STATUS_ORDER = ["changes_requested", "in_progress", "selected"]
DEPENDENCY_READY_STATUSES = {"pr_open", "merged", "done"}
LIGHT_WEIGHT = "light"
LIGHT_ONLY_FLAG = "--light-only"
ROLE_OPTION = "--role"
FREE_PLATFORM = "free"
DEFAULT_PREFERRED_PLATFORM = "android"


def needs_device(task):
    """A task whose need is unknown (no `needs_device` field) counts as needing a device."""
    return task.get("needs_device") is not False


def role_from_arguments(arguments):
    """The claim role named on the command line: `--light-only` (kept for runner-3's routine) or `--role <role>`."""
    if LIGHT_ONLY_FLAG in arguments:
        return runner_config.LIGHT_ROLE
    role = read_option(arguments, ROLE_OPTION, None)
    if role not in (None, runner_config.DEVICE_ROLE, runner_config.NO_DEVICE_ROLE, runner_config.LIGHT_ROLE):
        raise SystemExit("unknown role: %s" % role)
    return role


def role_skip_reason(role, task):
    if role == runner_config.LIGHT_ROLE and task.get("weight") != LIGHT_WEIGHT:
        return "not a light task (runner-3 takes only light tasks)"
    if role == runner_config.NO_DEVICE_ROLE and needs_device(task):
        return "needs a device (runner-4 takes only tasks marked needs_device: false)"
    return None


def lock_file_for(name):
    return LOCK_DIR / ("%s.lock" % re.sub(r"[^A-Za-z0-9._-]", "_", name))


def task_lock_name(task_key):
    return "task-" + task_key


def lock_age_seconds(lock_file):
    return time.time() - lock_file.stat().st_mtime


def is_held(lock_file):
    try:
        return lock_age_seconds(lock_file) <= LOCK_MAX_AGE_SECONDS
    except FileNotFoundError:
        return False


def write_new_lock(lock_file, session):
    lock_content = "start %s session=%s pid=%d\n" % (
        time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), session, os.getppid())
    file_descriptor = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    with os.fdopen(file_descriptor, "w") as lock_stream:
        lock_stream.write(lock_content)


def remove_stale_lock(lock_file):
    # Renaming first means only one contender removes a given stale lock; the others then race on
    # O_EXCL creation, which exactly one wins.
    stale_file = lock_file.with_name(lock_file.name + ".stale.%d" % os.getpid())
    try:
        os.rename(str(lock_file), str(stale_file))
    except FileNotFoundError:
        return
    stale_file.unlink()


def try_acquire(lock_file, session):
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    try:
        write_new_lock(lock_file, session)
        return True
    except FileExistsError:
        pass
    if is_held(lock_file):
        return False
    remove_stale_lock(lock_file)
    try:
        write_new_lock(lock_file, session)
        return True
    except FileExistsError:
        return False


def describe_holder(lock_file):
    try:
        return "%d min old: %s" % (lock_age_seconds(lock_file) // 60, lock_file.read_text().strip())
    except FileNotFoundError:
        return "released"


def touch(lock_file):
    if not lock_file.exists():
        print("not held: %s" % lock_file.name)
        sys.exit(EXIT_LOCK_HELD)
    lock_file.touch()
    print("touched")


def release(lock_file):
    lock_file.unlink(missing_ok=True)
    print("released")


def run_state_tx(*state_tx_arguments):
    output = subprocess.run([sys.executable, str(STATE_TX_SCRIPT)] + list(state_tx_arguments),
                            check=True, capture_output=True, text=True).stdout
    return json.loads(output)


def read_tasks():
    return run_state_tx("get", "tasks")


def read_task_statuses():
    # Includes archived tasks: a merged dependency may already have been moved to state-archive.json.
    return run_state_tx("statuses")


def dependency_keys(task):
    blocked_by = task.get("blocked_by") or []
    return [blocked_by] if isinstance(blocked_by, str) else list(blocked_by)


def find_unready_dependency(task, task_statuses):
    for dependency_key in dependency_keys(task):
        if is_held(lock_file_for(task_lock_name(dependency_key))):
            return "%s is being worked on by another session" % dependency_key
        dependency_status = task_statuses.get(dependency_key)
        if dependency_status not in DEPENDENCY_READY_STATUSES:
            return "%s is %s (needs an open or merged PR first)" % (dependency_key, dependency_status)
    return None


def claim_order(task_item, role=None):
    """Device runners put tasks that need a device first, so a task without one never takes their turn while
    device work waits; after that the usual order: status, queue priority, age."""
    task_key, task = task_item
    device_tier = 0 if role != runner_config.DEVICE_ROLE or needs_device(task) else 1
    return (device_tier, CLAIMABLE_STATUS_ORDER.index(task["status"]), task.get("queue_priority", 1000),
            task.get("updated_at", ""), task_key)


def find_claimable_candidates(role=None):
    """Yield (task_key, None) for each claimable task in claim order, or (task_key, reason) when skipped.
    role: see runner_config.RUNNER_ROLES; an unmarked task counts as heavy and as needing a device."""
    tasks = read_tasks()
    task_statuses = read_task_statuses()
    candidates = sorted(
        ((key, task) for key, task in tasks.items() if task.get("status") in CLAIMABLE_STATUS_ORDER),
        key=lambda task_item: claim_order(task_item, role))
    for task_key, task in candidates:
        if is_held(lock_file_for(task_lock_name(task_key))):
            yield task_key, "locked by another session"
            continue
        role_reason = role_skip_reason(role, task)
        if role_reason:
            yield task_key, role_reason
            continue
        open_question_ids = [question.split(":", 1)[0].strip() for question in task.get("open_questions") or []]
        if open_question_ids:
            yield task_key, "waits for answers to " + ", ".join(open_question_ids)
            continue
        unready_dependency = find_unready_dependency(task, task_statuses)
        if unready_dependency:
            yield task_key, "waits for " + unready_dependency
            continue
        yield task_key, None


def print_claimable(role=None):
    skipped_reasons = []
    for task_key, skip_reason in find_claimable_candidates(role):
        if skip_reason is None:
            print(task_key)
            return 0
        skipped_reasons.append("%s: %s" % (task_key, skip_reason))
    print("none")
    for reason in skipped_reasons:
        print("skipped " + reason)
    return EXIT_NOTHING_CLAIMABLE


def claim(session, role=None):
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    with open(CLAIM_MUTEX_FILE, "a") as mutex_stream:
        fcntl.flock(mutex_stream, fcntl.LOCK_EX)
        skipped_reasons = []
        for task_key, skip_reason in find_claimable_candidates(role):
            if skip_reason:
                skipped_reasons.append("%s: %s" % (task_key, skip_reason))
                continue
            if try_acquire(lock_file_for(task_lock_name(task_key)), session):
                print(task_key)
                if role == runner_config.DEVICE_ROLE and not needs_device(read_tasks()[task_key]):
                    print("note: no device task is claimable; a device runner took a task without a device",
                          file=sys.stderr)
                for reason in skipped_reasons:
                    print("skipped " + reason, file=sys.stderr)
                return 0
            skipped_reasons.append("%s: locked by another session" % task_key)
    print("none")
    for reason in skipped_reasons:
        print("skipped " + reason)
    return EXIT_NOTHING_CLAIMABLE


def free_device_alternatives(preferred_platform, include_couple):
    """Lock sets to try in order for `--platform free`: the preferred device first, then the other one."""
    if preferred_platform not in ("android", "ios"):
        raise SystemExit("unknown preferred platform: %s" % preferred_platform)
    other_platform = "ios" if preferred_platform == "android" else "android"
    return [requested_device_lock_names(platform, include_couple) for platform in (preferred_platform, other_platform)]


def requested_device_lock_names(platform, include_couple):
    if platform not in ("android", "ios", "web", "both"):
        raise SystemExit("unknown platform: %s" % platform)
    platforms = ["android", "ios"] if platform == "both" else [platform]
    lock_names = [PLATFORM_LOCK_NAMES[name] for name in platforms]
    if include_couple:
        lock_names.append(COUPLE_LOCK_NAME)
    return lock_names


def holder_session(lock_file):
    try:
        match = re.search(r"session=(\S+)", lock_file.read_text())
    except FileNotFoundError:
        return None
    return match.group(1) if match else None


def try_acquire_all(lock_names, session):
    legacy_lock_file = lock_file_for(LEGACY_DEVICES_LOCK_NAME)
    if is_held(legacy_lock_file) and holder_session(legacy_lock_file) != session:
        return legacy_lock_file
    acquired_files = []
    for lock_name in lock_names:
        lock_file = lock_file_for(lock_name)
        if try_acquire(lock_file, session):
            acquired_files.append(lock_file)
            continue
        if holder_session(lock_file) == session and is_held(lock_file):
            continue
        for acquired_file in acquired_files:
            release_quietly(acquired_file)
        return lock_file
    return None


def release_quietly(lock_file):
    lock_file.unlink(missing_ok=True)


def acquire_devices(session, alternatives, task_key, wait_minutes):
    """alternatives: lock sets in order of preference; the first set that is entirely free is taken."""
    deadline = time.time() + wait_minutes * 60
    while True:
        blocking_lock_files = []
        for lock_names in alternatives:
            blocking_lock_file = try_acquire_all(lock_names, session)
            if blocking_lock_file is None:
                print("acquired %s" % " ".join(lock_names))
                return 0
            blocking_lock_files.append(blocking_lock_file)
        if time.time() >= deadline:
            print("held " + ", ".join("%s (%s)" % (lock_file.name, describe_holder(lock_file))
                                      for lock_file in blocking_lock_files))
            return EXIT_LOCK_HELD
        task_lock_file = lock_file_for(task_lock_name(task_key)) if task_key else None
        if task_lock_file and task_lock_file.exists():
            task_lock_file.touch()
        time.sleep(DEVICE_WAIT_POLL_SECONDS)


def device_locks_held_by(session, lock_names):
    return [lock_file_for(name) for name in lock_names if holder_session(lock_file_for(name)) == session]


def update_device_locks(action, session, lock_names):
    if session is None:
        # Sessions started before 2026-10-07 call `devices touch|release` without a session.
        lock_files = [lock_file_for(LEGACY_DEVICES_LOCK_NAME)]
    else:
        lock_files = device_locks_held_by(session, lock_names)
    if action == "release":
        for lock_file in lock_files:
            release_quietly(lock_file)
        print("released %s" % (" ".join(lock_file.stem for lock_file in lock_files) or "nothing"))
        return 0
    existing_files = [lock_file for lock_file in lock_files if lock_file.exists()]
    if not existing_files:
        print("not held: no device lock for %s" % session)
        return EXIT_LOCK_HELD
    for lock_file in existing_files:
        lock_file.touch()
    print("touched %s" % " ".join(lock_file.stem for lock_file in existing_files))
    return 0


def print_status():
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    lock_files = sorted(LOCK_DIR.glob("*.lock"))
    if not lock_files:
        print("no locks")
    for lock_file in lock_files:
        state = "held" if is_held(lock_file) else "stale"
        print("%s %s (%s)" % (state, lock_file.name, describe_holder(lock_file)))


def read_option(arguments, option_name, default_value):
    if option_name in arguments:
        value_index = arguments.index(option_name) + 1
        if value_index >= len(arguments):
            raise SystemExit("%s needs a value" % option_name)
        return arguments[value_index]
    return default_value


def run_devices_command(arguments):
    action = arguments[1]
    session = arguments[2] if len(arguments) >= 3 and not arguments[2].startswith("--") else None
    include_couple = "--couple" in arguments
    platform_option = read_option(arguments, "--platform", None)
    if action == "acquire":
        if session is None:
            raise SystemExit("devices acquire needs a session")
        if platform_option == FREE_PLATFORM:
            alternatives = free_device_alternatives(read_option(arguments, "--prefer", DEFAULT_PREFERRED_PLATFORM),
                                                    include_couple)
        else:
            alternatives = [requested_device_lock_names(platform_option or "both", include_couple)]
        wait_minutes = float(read_option(arguments, "--wait-minutes", DEFAULT_DEVICE_WAIT_MINUTES))
        return acquire_devices(session, alternatives, read_option(arguments, "--task", None), wait_minutes)
    if action in ("touch", "release"):
        if platform_option is not None:
            lock_names = requested_device_lock_names(platform_option, include_couple)
        elif include_couple:
            lock_names = [COUPLE_LOCK_NAME]
        else:
            lock_names = ALL_DEVICE_LOCK_NAMES
        return update_device_locks(action, session, lock_names)
    raise SystemExit("unknown devices action: %s" % action)


def main():
    arguments = sys.argv[1:]
    command = arguments[0] if arguments else ""

    role = role_from_arguments(arguments)
    if ROLE_OPTION in arguments:
        role_index = arguments.index(ROLE_OPTION)
        arguments = arguments[:role_index] + arguments[role_index + 2:]
    arguments = [argument for argument in arguments if argument != LIGHT_ONLY_FLAG]
    if command == "claim" and len(arguments) == 2:
        sys.exit(claim(arguments[1], role))
    if command == "claimable" and len(arguments) == 1:
        sys.exit(print_claimable(role))
    if command == "lock" and len(arguments) == 3:
        lock_file = lock_file_for(task_lock_name(arguments[1]))
        if try_acquire(lock_file, arguments[2]):
            print("acquired")
            return
        print("held (%s)" % describe_holder(lock_file))
        sys.exit(EXIT_LOCK_HELD)
    if command == "touch" and len(arguments) == 2:
        touch(lock_file_for(task_lock_name(arguments[1])))
        return
    if command == "release" and len(arguments) == 2:
        release(lock_file_for(task_lock_name(arguments[1])))
        return
    if command == "devices" and len(arguments) >= 2:
        sys.exit(run_devices_command(arguments))
    if command == "housekeeping" and len(arguments) >= 2:
        lock_file = lock_file_for(command)
        action = arguments[1]
        if action == "acquire" and len(arguments) >= 3:
            if try_acquire(lock_file, arguments[2]):
                print("acquired")
                return
            print("held (%s)" % describe_holder(lock_file))
            sys.exit(EXIT_LOCK_HELD)
        if action == "touch":
            touch(lock_file)
            return
        if action == "release":
            release(lock_file)
            return
    if command == "status":
        print_status()
        return
    print(__doc__, file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
