#!/usr/bin/env python3
"""Runs a build/test command with its full output in a log file and prints only a short summary.

Usage: run_build.py [--cwd DIR] [--log PATH] [--lock TASK_KEY] [--tail 40] -- <command> [args...]
  run_build.py --cwd <worktree> --lock rindle-cmp#402 -- ./gradlew :composeApp:desktopTest

Summary: exit code, duration, test counts and failed tests (from JUnit XML / TRX files written
during the run), compiler errors, Gradle's "What went wrong" block; the log tail only when nothing
else explains a failure. Exit code is the command's exit code.
Every run is also recorded in timings.jsonl (timings.py); Maestro runs record each flow's result.
"""
import argparse, glob, os, re, subprocess, sys, threading, time
import xml.etree.ElementTree as ET

import timings

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOCKS_SCRIPT = os.path.join(SCRIPT_DIR, "locks.py")
LOCK_TOUCH_INTERVAL_SECONDS = 10 * 60
MAX_LISTED_ITEMS = 10
MAX_MESSAGE_LENGTH = 300
JUNIT_PATTERNS = ("**/build/test-results/**/*.xml",)
TRX_PATTERNS = ("**/TestResults/**/*.trx",)
COMPILER_ERROR = re.compile(r"^(e: .*|.*\berror (CS|MSB|NU)\d+:.*|.*: error: .*)$")
DOTNET_TOTALS = re.compile(r"(Passed|Failed)!\s+-\s+Failed:\s+(\d+), Passed:\s+(\d+), Skipped:\s+(\d+), Total:\s+(\d+)")
SECRET_LIKE = re.compile(r"(?i)(password|secret|token|apikey|api_key)\s*[=:]\s*\S+")


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cwd", default=os.getcwd())
    parser.add_argument("--log")
    parser.add_argument("--lock")
    parser.add_argument("--tail", type=int, default=40)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    arguments = parser.parse_args()
    if arguments.command[:1] == ["--"]:
        arguments.command = arguments.command[1:]
    if not arguments.command:
        parser.error("command required after --")
    return arguments


def default_log_path(working_directory, command):
    step_name = re.sub(r"[^A-Za-z0-9]+", "-", " ".join(command[:3])).strip("-")[:60] or "build"
    timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    return os.path.join(working_directory, "build", "runner-logs", f"{step_name}-{timestamp}.log")


def touch_lock(task_key):
    subprocess.run([sys.executable, LOCKS_SCRIPT, "touch", task_key], capture_output=True)


def keep_lock_fresh(task_key, finished_event):
    while not finished_event.wait(LOCK_TOUCH_INTERVAL_SECONDS):
        touch_lock(task_key)


def run_command(command, working_directory, log_path, task_key):
    finished_event = threading.Event()
    if task_key:
        touch_lock(task_key)
        threading.Thread(target=keep_lock_fresh, args=(task_key, finished_event), daemon=True).start()
    with open(log_path, "w") as log_file:
        exit_code = subprocess.run(command, cwd=working_directory, stdout=log_file, stderr=subprocess.STDOUT).returncode
    finished_event.set()
    if task_key:
        touch_lock(task_key)
    return exit_code


def files_written_since(working_directory, patterns, start_time):
    for pattern in patterns:
        for path in glob.glob(os.path.join(working_directory, pattern), recursive=True):
            if os.path.getmtime(path) >= start_time:
                yield path


def shorten(text):
    first_line = (text or "").strip().splitlines()[0] if (text or "").strip() else ""
    return SECRET_LIKE.sub(r"\1=<redacted>", first_line)[:MAX_MESSAGE_LENGTH]


def read_junit_results(paths):
    totals = {"tests": 0, "failed": 0, "skipped": 0}
    failures = []
    for path in paths:
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError:
            continue
        for test_case in root.iter("testcase"):
            totals["tests"] += 1
            problem = next((child for child in test_case if child.tag in ("failure", "error")), None)
            if problem is not None:
                totals["failed"] += 1
                message = problem.get("message") or problem.text
                failures.append(f"{test_case.get('classname')}.{test_case.get('name')}: {shorten(message)}")
            elif test_case.find("skipped") is not None:
                totals["skipped"] += 1
    return totals, failures


def read_trx_results(paths):
    totals = {"tests": 0, "failed": 0, "skipped": 0}
    failures = []
    for path in paths:
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError:
            continue
        for result in root.iter():
            if not result.tag.endswith("UnitTestResult"):
                continue
            totals["tests"] += 1
            outcome = result.get("outcome")
            if outcome == "Failed":
                totals["failed"] += 1
                message = next((element.text for element in result.iter() if element.tag.endswith("Message")), "")
                failures.append(f"{result.get('testName')}: {shorten(message)}")
            elif outcome == "NotExecuted":
                totals["skipped"] += 1
    return totals, failures


def read_log_findings(log_path):
    with open(log_path, errors="replace") as log_file:
        lines = log_file.read().splitlines()
    compiler_errors = list(dict.fromkeys(SECRET_LIKE.sub(r"\1=<redacted>", line.strip())[:MAX_MESSAGE_LENGTH] for line in lines if COMPILER_ERROR.match(line.strip())))
    went_wrong = []
    for index, line in enumerate(lines):
        if line.startswith("* What went wrong:"):
            for following in lines[index + 1:index + 12]:
                if following.startswith("* Try:"):
                    break
                if following.strip():
                    went_wrong.append(following.rstrip()[:MAX_MESSAGE_LENGTH])
    dotnet_totals = [match.groups() for match in map(DOTNET_TOTALS.search, lines) if match]
    return lines, compiler_errors, went_wrong, dotnet_totals


def record_timing(arguments, working_directory, log_path, start_time, exit_code, lines, junit_totals, trx_totals, dotnet_totals):
    kind = timings.classify_command(arguments.command + [os.path.basename(log_path)])
    tests = next((totals for totals in (junit_totals, trx_totals) if totals["tests"]), None)
    if tests is None and dotnet_totals:
        tests = {"tests": int(dotnet_totals[-1][4]), "failed": int(dotnet_totals[-1][1]), "skipped": int(dotnet_totals[-1][3])}
    flows = timings.maestro_flow_results(lines) if kind == "device" else None
    timings.record(kind, arguments.lock, working_directory, arguments.command, start_time, time.time(), exit_code,
                   tests=tests, flows=flows, log=log_path)


def print_list(title, items):
    if not items:
        return
    print(f"{title}:")
    for item in items[:MAX_LISTED_ITEMS]:
        print(f"- {item}")
    if len(items) > MAX_LISTED_ITEMS:
        print(f"- … {len(items) - MAX_LISTED_ITEMS} more (see log)")


def main():
    arguments = parse_arguments()
    working_directory = os.path.abspath(arguments.cwd)
    log_path = os.path.abspath(arguments.log or default_log_path(working_directory, arguments.command))
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    start_time = time.time()
    exit_code = run_command(arguments.command, working_directory, log_path, arguments.lock)
    duration_seconds = time.time() - start_time

    junit_totals, junit_failures = read_junit_results(files_written_since(working_directory, JUNIT_PATTERNS, start_time))
    trx_totals, trx_failures = read_trx_results(files_written_since(working_directory, TRX_PATTERNS, start_time))
    lines, compiler_errors, went_wrong, dotnet_totals = read_log_findings(log_path)
    record_timing(arguments, working_directory, log_path, start_time, exit_code, lines, junit_totals, trx_totals, dotnet_totals)

    print(f"STATUS: {'PASS' if exit_code == 0 else 'FAIL'} (exit {exit_code})")
    print(f"COMMAND: {' '.join(arguments.command)}")
    print(f"DURATION: {int(duration_seconds // 60)}m {int(duration_seconds % 60)}s")
    print(f"LOG: {log_path} ({len(lines)} lines)")
    for name, totals in (("junit", junit_totals), ("trx", trx_totals)):
        if totals["tests"]:
            print(f"TESTS ({name}): {totals['tests']} run, {totals['failed']} failed, {totals['skipped']} skipped")
    for outcome, failed, passed, skipped, total in dotnet_totals:
        print(f"TESTS (dotnet): {total} run, {failed} failed, {skipped} skipped")
    no_test_results = not (junit_totals["tests"] or trx_totals["tests"] or dotnet_totals)
    if no_test_results and re.search(r"[Tt]est", " ".join(arguments.command)):
        print("TESTS: no result files written during this run (tasks up-to-date? rerun with --rerun-tasks)")
    print_list("FAILED TESTS", junit_failures + trx_failures)
    print_list("COMPILER ERRORS", compiler_errors)
    print_list("WHAT WENT WRONG", went_wrong)
    nothing_explains_failure = exit_code != 0 and not (junit_failures or trx_failures or compiler_errors or went_wrong)
    if nothing_explains_failure:
        print(f"LOG TAIL (last {arguments.tail} lines):")
        for line in lines[-arguments.tail:]:
            print(SECRET_LIKE.sub(r"\1=<redacted>", line)[:MAX_MESSAGE_LENGTH])
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
