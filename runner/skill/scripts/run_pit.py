#!/usr/bin/env python3
"""Diff-scoped PIT mutation run for a KMP worktree (desktop/JVM tests).

Usage: run_pit.py <worktree> <base-ref> [--threshold 85] [--lock TASK_KEY]
Finds every Gradle module whose commonMain/desktopMain/jvmMain Kotlin changed (e.g. composeApp in an app,
deveng-core in deveng-core-kmp), runs PIT per module against that module's changed tests and prints one JSON
summary over all of them. Results are kept per module in build/pit-history, so a re-run after adding tests only re-tests
mutants whose class or covering tests changed (PIT's incremental analysis; scores stay identical to a full run); exit 1 when the score is below the threshold. Each run is recorded in timings.jsonl.
"""
import argparse, collections, json, os, re, subprocess, sys, urllib.request
import time
import xml.etree.ElementTree as ET

import android_sdk
import timings

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
SUSPEND_RETURN = re.compile(r"replaced return value with null for .*::invokeSuspend")
NULL_RETURN = re.compile(r"replaced return value with null for .*::([A-Za-z_][A-Za-z0-9_]*)$")
SUSPEND_SIGNATURE_SUFFIX = "Lkotlin/coroutines/Continuation;)Ljava/lang/Object;"
FLOW_COLLECTOR_EMIT = "emit"
COMPOSE_RUNTIME_CALL = "removed call to androidx/compose/runtime/"
COMPOSE_MASK_OPERATION = re.compile(r"Replaced (bitwise (AND|OR)|Shift (Left|Right))")
SERIALIZER_CLASS_SUFFIX = "$$serializer"
SERIALIZER_METHOD_PREFIX = "write$Self"
MAIN_SOURCE_SETS = ("commonMain", "desktopMain", "jvmMain")
TEST_SOURCE_SETS = ("commonTest", "desktopTest", "jvmTest")
SOURCE_SET_PATH = re.compile(r"^(?:(.+)/)?src/([A-Za-z]+)/kotlin/")


def ensure_jars():
    os.makedirs(PIT_DIR, exist_ok=True)
    for path in PIT_JARS:
        target = os.path.join(PIT_DIR, os.path.basename(path))
        if not os.path.exists(target):
            urllib.request.urlretrieve(f"{MAVEN}/{path}", target)


def sh(cmd, cwd, **kw):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, **kw)


def changed_kotlin_files(worktree, base, source_sets):
    files = sh(["git", "diff", "--name-only", "--diff-filter=AM", f"{base}...HEAD"], worktree).stdout.split()
    by_module = collections.defaultdict(list)
    for path in files:
        match = SOURCE_SET_PATH.match(path)
        if path.endswith(".kt") and match and match.group(2) in source_sets:
            by_module[match.group(1) or ""].append(path)
    return by_module


def gradle_path(module_dir):
    return ":" + module_dir.replace("/", ":") if module_dir else ":"


def changed_lines(worktree, base, files):
    result = {}
    for path in files:
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


def test_classes(worktree, files):
    names = []
    for path in files:
        if path.endswith("Test.kt"):
            package, cls = package_and_class(worktree, path)
            names.append(f"{package}.{cls}")
    return names


def run_module(worktree, module_dir, changed, tests, report_dir):
    """Runs PIT for one module; returns the mutations.xml path or an error text."""
    gradle = sh(["./gradlew", "-q", "--init-script", INIT_SCRIPT, f"-PpitModule={gradle_path(module_dir)}", "--no-configuration-cache",
                 f"{gradle_path(module_dir).rstrip(':')}:printPitClasspath"], worktree)
    classpath = next((l[len("PITCP="):] for l in gradle.stdout.splitlines() if l.startswith("PITCP=")), None)
    if not classpath:
        return None, gradle.stdout[-2000:] + gradle.stderr[-2000:]
    targets = [".".join(package_and_class(worktree, p)) + "*" for p in changed]
    source_dirs = ",".join(os.path.join(module_dir, "src", source_set, "kotlin") for source_set in MAIN_SOURCE_SETS
                           if os.path.isdir(os.path.join(worktree, module_dir, "src", source_set, "kotlin")))
    history_file = os.path.join(worktree, "build", "pit-history", (module_dir.replace("/", "-") or "root") + ".bin")
    os.makedirs(os.path.dirname(history_file), exist_ok=True)
    jars = ":".join(os.path.join(PIT_DIR, j) for j in os.listdir(PIT_DIR) if j.endswith(".jar"))
    run = sh(["java", "-cp", f"{jars}:{classpath}", "org.pitest.mutationtest.commandline.MutationCoverageReport",
              "--reportDir", report_dir, "--sourceDirs", source_dirs,
              "--targetClasses", ",".join(targets), "--excludedClasses", "*Test*",
              "--targetTests", ",".join(tests), "--classPath", classpath,
              "--outputFormats", "XML", "--threads", "4", "--timestampedReports=false",
              "--timeoutConst", "8000",
              "--historyInputLocation", history_file, "--historyOutputLocation", history_file, "--jvmArgs", "-Xmx2g"], worktree)
    mutations = os.path.join(report_dir, "mutations.xml")
    if not os.path.exists(mutations):
        return None, run.stdout[-3000:] + run.stderr[-3000:]
    return mutations, None


def composable_methods(root):
    """(class, method) pairs the Compose compiler instrumented; they carry its generated changed/default mask arithmetic."""
    return {(m.findtext("mutatedClass"), m.findtext("mutatedMethod"))
            for m in root if COMPOSE_RUNTIME_CALL in (m.findtext("description") or "")}


def declares_only_unit_suspend_functions(source, name):
    """True when every `suspend fun <name>` in the Kotlin source has no return type, or `: Unit`, before its `{` body."""
    found = False
    for match in re.finditer(r"\bsuspend\s+fun\s+(?:<[^>]*>\s*)?(?:[\w.<>?, ]+\.)?" + re.escape(name) + r"\s*\(", source):
        depth, index = 1, match.end()
        while depth and index < len(source):
            depth += {"(": 1, ")": -1}.get(source[index], 0)
            index += 1
        rest = source[index:].lstrip()
        if not (rest.startswith("{") or re.match(r":\s*Unit\s*\{", rest)):
            return False
        found = True
    return found


def is_unit_suspend_null_return(m, description, source):
    """`return null` instead of Unit from a suspend function that returns Unit: callers never read that value.

    The JVM signature of every suspend function returns Object, so only the source tells a Unit function apart.
    `emit` is FlowCollector.emit (always Unit), compiled into the collector class of a `collect { }` block.
    """
    match = NULL_RETURN.search(description)
    if not match or not (m.findtext("methodDescription") or "").endswith(SUSPEND_SIGNATURE_SUFFIX):
        return False
    name = match.group(1)
    return name == FLOW_COLLECTOR_EMIT or (source is not None and declares_only_unit_suspend_functions(source, name))


def is_compiler_generated(m, description, composables, source=None):
    """Mutations in code the Kotlin/Compose compiler writes, or that change nothing a caller can see:
    nothing a test can meaningfully kill."""
    mutated_class = m.findtext("mutatedClass") or ""
    mutated_method = m.findtext("mutatedMethod") or ""
    if any(noise in description for noise in NOISE) or UNIT_LAMBDA.search(description) or SUSPEND_RETURN.search(description):
        return True
    if is_unit_suspend_null_return(m, description, source):
        return True
    if COMPOSE_RUNTIME_CALL in description:
        return True
    if mutated_class.endswith(SERIALIZER_CLASS_SUFFIX) or mutated_method.startswith(SERIALIZER_METHOD_PREFIX):
        return True
    return (mutated_class, mutated_method) in composables and bool(COMPOSE_MASK_OPERATION.search(description))


def count_mutations(worktree, mutations, changed, counts, survivors):
    by_file = {os.path.basename(p): lines for p, lines in changed.items()}
    paths = {os.path.basename(p): os.path.join(worktree, p) for p in changed}
    sources = {}
    root = ET.parse(mutations).getroot()
    composables = composable_methods(root)
    for m in root:
        source = m.findtext("sourceFile")
        line = int(m.findtext("lineNumber"))
        if line not in by_file.get(source, ()):
            continue
        if source not in sources:
            with open(paths[source]) as file:
                sources[source] = file.read()
        description = m.findtext("description") or ""
        if is_compiler_generated(m, description, composables, sources[source]):
            counts["noise"] += 1
            continue
        status = m.get("status")
        counts[status] += 1
        if status in ("SURVIVED", "NO_COVERAGE"):
            survivors.append({"file": source, "line": line, "status": status,
                              "mutator": m.findtext("mutator").split(".")[-1], "description": description})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("worktree")
    parser.add_argument("base")
    parser.add_argument("--threshold", type=float, default=85)
    parser.add_argument("--lock")
    args = parser.parse_args()
    worktree = os.path.abspath(args.worktree)
    android_sdk.ensure_android_sdk_environment()
    ensure_jars()

    production_by_module = changed_kotlin_files(worktree, args.base, MAIN_SOURCE_SETS)
    tests_by_module = changed_kotlin_files(worktree, args.base, TEST_SOURCE_SETS)
    counts = collections.Counter()
    survivors, modules, skipped = [], [], {}
    for module_dir, production_files in sorted(production_by_module.items()):
        changed = changed_lines(worktree, args.base, production_files)
        tests = test_classes(worktree, tests_by_module.get(module_dir, []))
        if not changed or not tests:
            skipped[module_dir or "."] = "no changed lines" if not changed else "no changed tests"
            continue
        report_dir = os.path.join(worktree, "build", "pit-report", module_dir.replace("/", "-") or "root")
        mutations, error = run_module(worktree, module_dir, changed, tests, report_dir)
        if error:
            print(f"PIT failed for {module_dir or '.'}:", error, file=sys.stderr)
            return 2
        count_mutations(worktree, mutations, changed, counts, survivors)
        modules.append(module_dir or ".")
    if not modules:
        print(json.dumps({"skipped": "no module with changed production classes and changed tests", "modules": skipped}))
        return 0

    killed = counts["KILLED"] + counts["TIMED_OUT"]
    total = killed + counts["SURVIVED"] + counts["NO_COVERAGE"]
    score = round(100 * killed / total, 1) if total else 100.0
    timings.record("pit", args.lock, worktree, ["run_pit.py", args.base], START_SECONDS, time.time(), 0 if score >= args.threshold else 1,
                   pit={"score": score, "killed": killed, "total": total})
    print(json.dumps({"score": score, "killed": killed, "total": total, "ignored_noise": counts["noise"],
                      "threshold": args.threshold, "modules": modules, "skipped_modules": skipped,
                      "survivors": sorted(survivors, key=lambda s: (s["file"], s["line"]))}, indent=1))
    return 0 if score >= args.threshold else 1


START_SECONDS = time.time()
if __name__ == "__main__":
    sys.exit(main())
