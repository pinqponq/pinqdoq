#!/usr/bin/env python3
"""Diff-scoped StrykerJS mutation run for a web worktree (TypeScript/JavaScript, Vitest runner).

Usage: run_stryker_js.py <worktree> <base-ref> [--project DIR] [--threshold 85] [--lock TASK_KEY]
The web counterpart of run_pit.py: the same score, killed, total, ignored_noise, threshold and survivors fields and the
same exit codes. Mutates only the production files the branch changed
(no tests, no type declarations, nothing under e2e/), counts only the mutants on changed lines, and prints one JSON
summary; exit 1 when the score is below the threshold, 2 when git or Stryker could not run or the report misses a
changed file. --project is the folder with
package.json and stryker.config.* (default: the worktree root). Stryker's incremental file in build/stryker keeps
results, so a re-run after adding tests only re-tests mutants whose code or covering tests changed. The full Stryker
output goes to build/runner-logs/; each run is recorded in timings.jsonl.
"""
import argparse, collections, json, os, re, subprocess, sys, time

import timings

SOURCE_EXTENSIONS = (".ts", ".tsx", ".js", ".jsx", ".mts", ".cts", ".mjs", ".cjs")
NOT_PRODUCTION = re.compile(r"(\.d\.[mc]?ts$|\.(test|spec|stories)\.[^.]+$|(^|/)(e2e|__tests__|__mocks__|test|tests)/"
                            r"|(^|/)[^/]*\.config\.[^/]+$)")
TEST_FILE = re.compile(r"\.(test|spec)\.[^.]+$|(^|/)__tests__/")
CONFIG_FILES = ("stryker.config.mjs", "stryker.config.js", "stryker.config.cjs", "stryker.config.json", "stryker.conf.js")
REPORT_FILES = ("build/stryker/mutation.json", "reports/mutation/mutation.json")
INCREMENTAL_FILE = "build/stryker/incremental.json"
DETECTED = ("Killed", "Timeout")
UNDETECTED = ("Survived", "NoCoverage")
# Mutants the TypeScript checker rejects or that crash the test runner before any test runs: invalid code, nothing a
# test can kill. Stryker's own score leaves them out too. "Ignored" mutants were excluded by config or a comment.
NOISE = ("CompileError", "RuntimeError", "Ignored")


class GitError(Exception):
    pass


def sh(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def git(arguments, worktree):
    result = sh(["git"] + arguments, worktree)
    if result.returncode != 0:
        raise GitError(f"git {' '.join(arguments)}: {result.stderr.strip()}")
    return result.stdout


def diff_files(worktree, base, project):
    """Files the branch added or changed under the project folder, relative to it."""
    files = git(["diff", "--name-only", "--diff-filter=AM", f"{base}...HEAD"], worktree).split()
    prefix = "" if project in ("", ".") else project.rstrip("/") + "/"
    return [path[len(prefix):] for path in files if path.startswith(prefix)]


def production_files(files):
    return [path for path in files if path.endswith(SOURCE_EXTENSIONS) and not NOT_PRODUCTION.search(path)]


def changed_lines(worktree, base, project, files):
    result = {}
    for relative in files:
        path = os.path.join(project, relative) if project not in ("", ".") else relative
        diff = git(["diff", "-U0", f"{base}...HEAD", "--", path], worktree)
        lines = set()
        for hunk in re.finditer(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", diff, re.M):
            start, count = int(hunk.group(1)), int(hunk.group(2) or 1)
            lines |= set(range(start, start + count))
        if lines:
            result[relative] = lines
    return result


def run_stryker(project_dir, files):
    """Runs Stryker on the given files; returns (report path, log path, error text)."""
    log_dir = os.path.join(project_dir, "build", "runner-logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, time.strftime("stryker-%Y%m%d-%H%M%S.log"))
    started = time.time()
    run = sh(["npx", "--no-install", "stryker", "run", "--mutate", ",".join(files), "--reporters", "json,html",
              "--incremental", "--incrementalFile", INCREMENTAL_FILE], project_dir)
    with open(log_path, "w") as log:
        log.write(run.stdout + run.stderr)
    for name in REPORT_FILES:
        report = os.path.join(project_dir, name)
        if os.path.exists(report) and os.path.getmtime(report) >= started:
            return report, log_path, None
    return None, log_path, (run.stdout[-2000:] + run.stderr[-2000:]).strip()


def report_files(report, project_dir):
    """The report's files keyed by path relative to the project folder.

    Stryker writes relative or absolute keys; an absolute key may be the resolved path of a worktree reached through a
    symbolic link, so both sides are resolved before comparing.
    """
    files = {}
    with open(report) as report_file:
        entries = json.load(report_file).get("files", {})
    for name, entry in entries.items():
        if os.path.isabs(name):
            relative = os.path.relpath(os.path.realpath(name), os.path.realpath(project_dir))
        else:
            relative = os.path.normpath(name)
        files[relative] = entry
    return files


def describe(mutant, source_lines):
    line = mutant["location"]["start"]["line"]
    original = source_lines[line - 1].strip() if 0 < line <= len(source_lines) else ""
    replacement = mutant.get("replacement")
    text = f"{mutant['mutatorName']}: {original[:80]}"
    return text + (f" → {replacement[:80]}" if replacement is not None else "")


def count_mutants(files, changed, counts, survivors):
    """Counts the mutants on changed lines; returns the changed files the report does not contain."""
    missing = []
    for path, lines in changed.items():
        entry = files.get(path)
        if entry is None:
            missing.append(path)
            continue
        source_lines = entry.get("source", "").splitlines()
        for mutant in entry.get("mutants", []):
            line = mutant["location"]["start"]["line"]
            if line not in lines:
                continue
            status = mutant.get("status")
            if status in NOISE:
                counts["noise"] += 1
                continue
            counts[status] += 1
            if status in UNDETECTED:
                survivors.append({"file": path, "line": line, "status": status, "mutator": mutant["mutatorName"],
                                  "description": describe(mutant, source_lines)})
    return sorted(missing)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("worktree")
    parser.add_argument("base")
    parser.add_argument("--project", default=".")
    parser.add_argument("--threshold", type=float, default=85)
    parser.add_argument("--lock")
    args = parser.parse_args()
    worktree = os.path.abspath(args.worktree)
    project_dir = os.path.normpath(os.path.join(worktree, args.project))

    try:
        files = diff_files(worktree, args.base, args.project)
        changed = changed_lines(worktree, args.base, args.project, production_files(files))
    except GitError as error:
        timings.record("pit", args.lock, worktree, ["run_stryker_js.py", args.base], START_SECONDS, time.time(), 2)
        print(error, file=sys.stderr)
        return 2
    if not changed:
        print(json.dumps({"skipped": "no changed production lines in TypeScript/JavaScript files", "project": args.project}))
        return 0
    if not any(os.path.exists(os.path.join(project_dir, name)) for name in CONFIG_FILES):
        timings.record("pit", args.lock, worktree, ["run_stryker_js.py", args.base], START_SECONDS, time.time(), 2)
        print(f"No stryker.config.mjs in {args.project}: set it up as references/web/e2e-playwright.md describes.", file=sys.stderr)
        return 2
    report, log_path, error = run_stryker(project_dir, sorted(changed))
    if error is not None:
        timings.record("pit", args.lock, worktree, ["run_stryker_js.py", args.base], START_SECONDS, time.time(), 2)
        print(f"Stryker failed (full output: {log_path}):", error, file=sys.stderr)
        return 2

    counts, survivors = collections.Counter(), []
    missing = count_mutants(report_files(report, project_dir), changed, counts, survivors)
    if missing:
        timings.record("pit", args.lock, worktree, ["run_stryker_js.py", args.base], START_SECONDS, time.time(), 2)
        print(f"The Stryker report has no entry for changed files {missing} (full output: {log_path}).", file=sys.stderr)
        return 2
    killed = sum(counts[status] for status in DETECTED)
    total = killed + sum(counts[status] for status in UNDETECTED)
    score = round(100 * killed / total, 1) if total else 100.0
    timings.record("pit", args.lock, worktree, ["run_stryker_js.py", args.base], START_SECONDS, time.time(),
                   0 if score >= args.threshold else 1, pit={"score": score, "killed": killed, "total": total})
    print(json.dumps({"score": score, "killed": killed, "total": total, "ignored_noise": counts["noise"],
                      "threshold": args.threshold, "files": sorted(changed),
                      "changed_tests": any(TEST_FILE.search(path) for path in files),
                      "report": os.path.relpath(report, worktree), "log": os.path.relpath(log_path, worktree),
                      "survivors": sorted(survivors, key=lambda survivor: (survivor["file"], survivor["line"]))}, indent=1, ensure_ascii=False))
    return 0 if score >= args.threshold else 1


START_SECONDS = time.time()
if __name__ == "__main__":
    sys.exit(main())
