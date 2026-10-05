#!/usr/bin/env python3
"""Diff-scoped PIT mutation run for a KMP worktree (desktop/JVM tests).

Usage: run_pit.py <worktree> <base-ref> [--threshold 85]
Prints a JSON summary; exit 1 when the score is below the threshold.
"""
import argparse, collections, json, os, re, subprocess, sys, urllib.request
import xml.etree.ElementTree as ET

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PIT_DIR = os.path.expanduser("~/.cache/pinq-pit")
INIT_SCRIPT = os.path.join(SCRIPT_DIR, "pit.init.gradle")
MAVEN = "https://repo1.maven.org/maven2"
PIT_JARS = [
    "org/pitest/pitest/1.17.4/pitest-1.17.4.jar",
    "org/pitest/pitest-entry/1.17.4/pitest-entry-1.17.4.jar",
    "org/pitest/pitest-command-line/1.17.4/pitest-command-line-1.17.4.jar",
    "org/apache/commons/commons-text/1.12.0/commons-text-1.12.0.jar",
    "org/apache/commons/commons-lang3/3.14.0/commons-lang3-3.14.0.jar",
]
NOISE = ("kotlin/ResultKt::throwOnFailure",)
UNIT_LAMBDA = re.compile(r"replaced return value with null for .*\$lambda")


def ensure_jars():
    os.makedirs(PIT_DIR, exist_ok=True)
    for path in PIT_JARS:
        target = os.path.join(PIT_DIR, os.path.basename(path))
        if not os.path.exists(target):
            urllib.request.urlretrieve(f"{MAVEN}/{path}", target)


def sh(cmd, cwd, **kw):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, **kw)


def changed_lines(worktree, base):
    files = sh(["git", "diff", "--name-only", "--diff-filter=AM", f"{base}...HEAD", "--", "composeApp/src/commonMain", "composeApp/src/desktopMain"], worktree).stdout.split()
    result = {}
    for path in files:
        if not path.endswith(".kt"):
            continue
        diff = sh(["git", "diff", "-U0", f"{base}...HEAD", "--", path], worktree).stdout
        lines = set()
        for m in re.finditer(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", diff, re.M):
            start, count = int(m.group(1)), int(m.group(2) or 1)
            lines |= set(range(start, start + count))
        if lines:
            result[path] = lines
    return result


def package_and_class(worktree, path):
    text = open(os.path.join(worktree, path)).read()
    package = re.search(r"^package\s+([\w.]+)", text, re.M).group(1)
    return package, os.path.basename(path)[:-3]


def test_classes(worktree, base):
    files = sh(["git", "diff", "--name-only", "--diff-filter=AM", f"{base}...HEAD", "--", "composeApp/src/desktopTest", "composeApp/src/commonTest"], worktree).stdout.split()
    names = []
    for path in files:
        if path.endswith("Test.kt"):
            package, cls = package_and_class(worktree, path)
            names.append(f"{package}.{cls}")
    return names


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("worktree")
    parser.add_argument("base")
    parser.add_argument("--threshold", type=float, default=85)
    args = parser.parse_args()
    worktree = os.path.abspath(args.worktree)
    ensure_jars()

    changed = changed_lines(worktree, args.base)
    targets = [".".join(package_and_class(worktree, p)) + "*" for p in changed]
    tests = test_classes(worktree, args.base)
    if not targets or not tests:
        print(json.dumps({"skipped": "no changed production classes or no changed tests", "targets": targets, "tests": tests}))
        return 0

    gradle = sh(["./gradlew", "-q", "--init-script", INIT_SCRIPT, ":composeApp:printPitClasspath"], worktree)
    classpath = next((l[len("PITCP="):] for l in gradle.stdout.splitlines() if l.startswith("PITCP=")), None)
    if not classpath:
        print(gradle.stdout[-2000:], gradle.stderr[-2000:], file=sys.stderr)
        return 2

    report_dir = os.path.join(worktree, "build", "pit-report")
    jars = ":".join(os.path.join(PIT_DIR, j) for j in os.listdir(PIT_DIR) if j.endswith(".jar"))
    run = sh(["java", "-cp", f"{jars}:{classpath}", "org.pitest.mutationtest.commandline.MutationCoverageReport",
              "--reportDir", report_dir, "--sourceDirs", "composeApp/src/commonMain/kotlin",
              "--targetClasses", ",".join(targets), "--excludedClasses", "*Test*",
              "--targetTests", ",".join(tests), "--classPath", classpath,
              "--outputFormats", "XML", "--threads", "4", "--timestampedReports=false",
              "--timeoutConst", "8000", "--jvmArgs", "-Xmx2g"], worktree)
    mutations = os.path.join(report_dir, "mutations.xml")
    if not os.path.exists(mutations):
        print(run.stdout[-3000:], run.stderr[-3000:], file=sys.stderr)
        return 2

    by_file = {os.path.basename(p): lines for p, lines in changed.items()}
    counts = collections.Counter()
    survivors = []
    for m in ET.parse(mutations).getroot():
        source = m.findtext("sourceFile")
        line = int(m.findtext("lineNumber"))
        if line not in by_file.get(source, ()):
            continue
        description = m.findtext("description") or ""
        if any(noise in description for noise in NOISE) or UNIT_LAMBDA.search(description):
            counts["noise"] += 1
            continue
        status = m.get("status")
        counts[status] += 1
        if status in ("SURVIVED", "NO_COVERAGE"):
            survivors.append({"file": source, "line": line, "status": status,
                              "mutator": m.findtext("mutator").split(".")[-1], "description": description})
    killed = counts["KILLED"] + counts["TIMED_OUT"]
    total = killed + counts["SURVIVED"] + counts["NO_COVERAGE"]
    score = round(100 * killed / total, 1) if total else 100.0
    print(json.dumps({"score": score, "killed": killed, "total": total, "ignored_noise": counts["noise"],
                      "threshold": args.threshold, "survivors": sorted(survivors, key=lambda s: (s["file"], s["line"]))}, indent=1))
    return 0 if score >= args.threshold else 1


sys.exit(main())
