#!/usr/bin/env python3
"""Diff-scoped PIT mutation run for the JVM tests of Kotlin Multiplatform, Android and plain JVM Gradle modules.

Usage: run_pit.py <worktree> <base-ref> [--threshold PERCENT] [--lock TASK_KEY] [--android-variant VARIANT]
Finds every Gradle module whose production code changed, runs PIT per module against that module's changed tests and
prints one JSON summary over all of them. The module's build file decides its type:
- Kotlin Multiplatform (e.g. composeApp in an app, deveng-core in deveng-core-kmp): Kotlin files in
  src/<commonMain|desktopMain|jvmMain>/kotlin, tests in src/<commonTest|desktopTest|jvmTest>/kotlin, run on the desktop
  or first JVM target.
- Android (an application or library module): Kotlin and Java files in src/main/<java|kotlin>, tests in
  src/test/<java|kotlin>, run on the unit test classpath of the debug variant (`--android-variant` picks another one).
- Plain JVM: the same folders as Android, run on the classpath of the `test` task. Results are kept per module in build/pit-history, so a re-run after adding tests only re-tests
mutants whose class or covering tests changed (PIT's incremental analysis; scores stay identical to a full run); exit 1 when the score is below the threshold. Each run is recorded in timings.jsonl.
"""
import argparse, collections, json, os, re, subprocess, sys, urllib.request
import time
import xml.etree.ElementTree as ET

import android_sdk
import timings
import verification_profile

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
COMPOSER_PARAMETER = "Landroidx/compose/runtime/Composer;"
NEGATED_CONDITIONAL = "negated conditional"
NULL_RETURN_MUTATOR = "NullReturnValsMutator"
SUSPEND_STATE_MACHINE_METHOD = "invokeSuspend"
KILLED_STATUSES = ("KILLED", "TIMED_OUT")
SOURCE_CONDITION = re.compile(
    r"\b(if|else|when|while|for|do|is|in|takeIf|takeUnless|check|checkNotNull|require|requireNotNull)\b|\bas\?"
    r"|->|\?:|\?\.|&&|\|\||!!|==|!=|<=|>=|\s<\s|\s>\s|!\s*[\w(]"
    r"|\b(filter|filterNot|filterNotNull|filterIsInstance|filterIndexed|filterKeys|filterValues|filterTo|map|mapNotNull"
    r"|mapIndexed|mapIndexedNotNull|mapKeys|mapValues|mapTo|mapNotNullTo|flatMap|forEach|forEachIndexed|onEach|onEachIndexed"
    r"|any|all|none|first|firstOrNull|firstNotNullOf|firstNotNullOfOrNull|last|lastOrNull|find|findLast|single|singleOrNull"
    r"|count|sumOf|maxBy|maxByOrNull|minBy|minByOrNull|maxOf|maxOfOrNull|minOf|minOfOrNull|sortedBy|sortedByDescending"
    r"|sortedWith|groupBy|associate|associateBy|associateWith|partition|takeWhile|dropWhile|indexOfFirst|indexOfLast"
    r"|distinctBy|repeat|reduce|reduceOrNull|reduceIndexed|fold|foldIndexed|zip|use|orEmpty|isEmpty|isBlank|isNotEmpty"
    r"|isNotBlank|isNullOrEmpty|isNullOrBlank|ifEmpty|ifBlank|getOrElse|getOrPut|getOrDefault|getOrNull|getOrThrow"
    r"|recover|recoverCatching|mapCatching|onSuccess|onFailure|exceptionOrNull)\s*(?:<(?:[^<>]|<[^<>]*>)*>)?\s*[({]")
CONTINUED_CONDITION = re.compile(r"(&&|\|\||\?:)\s*$|\b(if|when|while)\b.*\(\s*$")
STRING_TEMPLATE_EXPRESSION = "${"
CHAR_LITERAL = re.compile(r"'(?:[^'\\]|\\.)'")
STRING_LITERAL = re.compile(r'"(?:[^"\\]|\\.)*"')
LINE_COMMENT = re.compile(r"//.*$")
SERIALIZER_CLASS_SUFFIX = "$$serializer"
SERIALIZER_METHOD_PREFIX = "write$Self"
KOTLIN_MULTIPLATFORM_MODULE = "kmp"
ANDROID_MODULE = "android"
JVM_MODULE = "jvm"
MAIN_SOURCE_SETS = {KOTLIN_MULTIPLATFORM_MODULE: ("commonMain", "desktopMain", "jvmMain"), ANDROID_MODULE: ("main",), JVM_MODULE: ("main",)}
TEST_SOURCE_SETS = {KOTLIN_MULTIPLATFORM_MODULE: ("commonTest", "desktopTest", "jvmTest"), ANDROID_MODULE: ("test",), JVM_MODULE: ("test",)}
LANGUAGE_FOLDERS = {KOTLIN_MULTIPLATFORM_MODULE: ("kotlin",), ANDROID_MODULE: ("java", "kotlin"), JVM_MODULE: ("java", "kotlin")}
SOURCE_EXTENSIONS = {KOTLIN_MULTIPLATFORM_MODULE: (".kt",), ANDROID_MODULE: (".kt", ".java"), JVM_MODULE: (".kt", ".java")}
TEST_FILE_SUFFIXES = ("Test.kt", "Test.java")
SOURCE_SET_PATH = re.compile(r"^(?:(.+)/)?src/([A-Za-z]+)/(java|kotlin)/")
BUILD_FILE_NAMES = ("build.gradle.kts", "build.gradle")
MULTIPLATFORM_PLUGIN = re.compile(r"multiplatform", re.I)
ANDROID_PLUGIN = re.compile(r"com\.android\.(application|library)|\bandroid[._-]?(application|library)\b|^\s*android\s*\{", re.I | re.M)
ANDROID_MANIFEST = os.path.join("src", "main", "AndroidManifest.xml")
DEFAULT_ANDROID_VARIANT = "debug"
GRADLE_WRAPPER = "gradlew"
CLASSPATH_PREFIX = "PITCP="
MUTABLE_CODE_PREFIX = "PITCODE="


def ensure_jars():
    os.makedirs(PIT_DIR, exist_ok=True)
    for path in PIT_JARS:
        target = os.path.join(PIT_DIR, os.path.basename(path))
        if not os.path.exists(target):
            urllib.request.urlretrieve(f"{MAVEN}/{path}", target)


def sh(cmd, cwd, **kw):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, **kw)


def changed_source_files(worktree, base):
    """Added or modified files under some module's src/<source set>/<java|kotlin>/, grouped by module folder."""
    files = sh(["git", "diff", "--name-only", "--diff-filter=AM", f"{base}...HEAD"], worktree).stdout.split()
    by_module = collections.defaultdict(list)
    for path in files:
        match = SOURCE_SET_PATH.match(path)
        if match:
            by_module[match.group(1) or ""].append(path)
    return by_module


def module_kind(worktree, module_dir):
    """The module type from its build file's plugins and its source folders.

    Both are read because a convention plugin can hide the real plugin id from the build file.
    """
    module_path = os.path.join(worktree, module_dir)
    build_text = ""
    for name in BUILD_FILE_NAMES:
        if os.path.isfile(os.path.join(module_path, name)):
            with open(os.path.join(module_path, name)) as file:
                build_text = file.read()
            break
    has_multiplatform_folder = any(os.path.isdir(os.path.join(module_path, "src", source_set))
                                   for source_set in MAIN_SOURCE_SETS[KOTLIN_MULTIPLATFORM_MODULE])
    if MULTIPLATFORM_PLUGIN.search(build_text) or has_multiplatform_folder:
        return KOTLIN_MULTIPLATFORM_MODULE
    if ANDROID_PLUGIN.search(build_text) or os.path.isfile(os.path.join(module_path, ANDROID_MANIFEST)):
        return ANDROID_MODULE
    return JVM_MODULE


def files_in_source_sets(paths, kind, source_sets):
    """The paths in one of the source sets whose language folder and file extension the module type compiles."""
    selected = []
    for path in paths:
        match = SOURCE_SET_PATH.match(path)
        if (match and match.group(2) in source_sets and match.group(3) in LANGUAGE_FOLDERS[kind]
                and path.endswith(SOURCE_EXTENSIONS[kind])):
            selected.append(path)
    return selected


def source_dirs(worktree, module_dir, kind):
    return [os.path.join(module_dir, "src", source_set, folder) for source_set in MAIN_SOURCE_SETS[kind]
            for folder in LANGUAGE_FOLDERS[kind] if os.path.isdir(os.path.join(worktree, module_dir, "src", source_set, folder))]


def printed_value(gradle_output, prefix):
    """The value of the first `<prefix>…` line pit.init.gradle printed, or None when it printed none."""
    return next((line[len(prefix):] for line in gradle_output.splitlines() if line.startswith(prefix)), None)


def gradle_command(worktree):
    """The Gradle wrapper call; a wrapper committed without the executable bit runs through `sh`."""
    wrapper = os.path.join(worktree, GRADLE_WRAPPER)
    return ["./" + GRADLE_WRAPPER] if os.access(wrapper, os.X_OK) else ["sh", GRADLE_WRAPPER]


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
    with open(os.path.join(worktree, path)) as file:
        text = file.read()
    package = re.search(r"^package\s+([\w.]+)", text, re.M).group(1)
    return package, os.path.splitext(os.path.basename(path))[0]


def test_classes(worktree, files):
    names = []
    for path in files:
        if path.endswith(TEST_FILE_SUFFIXES):
            package, cls = package_and_class(worktree, path)
            names.append(f"{package}.{cls}")
    return names


def run_module(worktree, module_dir, kind, android_variant, changed, tests, report_dir):
    """Runs PIT for one module; returns the mutations.xml path or an error text."""
    gradle = sh(gradle_command(worktree) + ["-q", "--init-script", INIT_SCRIPT, f"-PpitModule={gradle_path(module_dir)}", f"-PpitModuleKind={kind}",
                 f"-PpitAndroidVariant={android_variant}", "--no-configuration-cache",
                 f"{gradle_path(module_dir).rstrip(':')}:printPitClasspath"], worktree)
    classpath = printed_value(gradle.stdout, CLASSPATH_PREFIX)
    mutable_code = printed_value(gradle.stdout, MUTABLE_CODE_PREFIX)
    if not classpath:
        return None, gradle.stdout[-2000:] + gradle.stderr[-2000:]
    targets = [".".join(package_and_class(worktree, p)) + "*" for p in changed]
    history_file = os.path.join(worktree, "build", "pit-history", (module_dir.replace("/", "-") or "root") + ".bin")
    os.makedirs(os.path.dirname(history_file), exist_ok=True)
    jars = ":".join(os.path.join(PIT_DIR, j) for j in os.listdir(PIT_DIR) if j.endswith(".jar"))
    run = sh(["java", "-cp", f"{jars}:{classpath}", "org.pitest.mutationtest.commandline.MutationCoverageReport",
              "--reportDir", report_dir, "--sourceDirs", ",".join(source_dirs(worktree, module_dir, kind)),
              "--targetClasses", ",".join(targets), "--excludedClasses", "*Test*",
              "--targetTests", ",".join(tests), "--classPath", classpath,
              *(["--mutableCodePaths", mutable_code.replace(":", ",")] if mutable_code else []),
              "--outputFormats", "XML", "--threads", "4", "--timestampedReports=false",
              "--timeoutConst", "8000",
              "--historyInputLocation", history_file, "--historyOutputLocation", history_file, "--jvmArgs", "-Xmx2g"], worktree)
    mutations = os.path.join(report_dir, "mutations.xml")
    if not os.path.exists(mutations):
        return None, run.stdout[-3000:] + run.stderr[-3000:]
    return mutations, None


def composable_methods(root):
    """(class, method) pairs the Compose compiler instrumented; they carry its generated changed/default mask arithmetic."""
    return {(m.findtext("mutatedClass"), m.findtext("mutatedMethod")) for m in root
            if COMPOSE_RUNTIME_CALL in (m.findtext("description") or "")
            or COMPOSER_PARAMETER in (m.findtext("methodDescription") or "")}


def is_suspend_method(mutation):
    return (mutation.findtext("mutatedMethod") == SUSPEND_STATE_MACHINE_METHOD
            or (mutation.findtext("methodDescription") or "").endswith(SUSPEND_SIGNATURE_SUFFIX))


def mutation_key(mutation):
    return tuple(mutation.findtext(field) for field in ("mutatedClass", "mutatedMethod", "lineNumber", "description"))


def killed_suspend_returns(root):
    """Null-return mutations of suspend functions that a test killed, keyed by class, method, line and description."""
    return {mutation_key(mutation) for mutation in root
            if mutation.get("status") in KILLED_STATUSES and NULL_RETURN_MUTATOR in (mutation.findtext("mutator") or "")
            and is_suspend_method(mutation)}


def code_without_strings_and_comments(text):
    return LINE_COMMENT.sub("", STRING_LITERAL.sub('""', CHAR_LITERAL.sub("''", text)))


def source_line_has_condition(source, line):
    """True when the person-written code on the line can branch: a condition, a safe call, a comparison, an inline call
    that branches, a string template expression, or the rest of a condition the previous line started."""
    lines = source.splitlines()
    if not 0 < line <= len(lines):
        return True
    text = lines[line - 1]
    if STRING_TEMPLATE_EXPRESSION in text:
        return True
    previous_code = code_without_strings_and_comments(lines[line - 2]) if line > 1 else ""
    return bool(SOURCE_CONDITION.search(code_without_strings_and_comments(text)) or CONTINUED_CONDITION.search(previous_code))


def is_generated_conditional(mutation, description, composables, source):
    """A negated conditional on a line of a composable or suspend function whose source has no condition.

    The Compose compiler adds $changed/$default/skipping checks and the coroutine compiler adds COROUTINE_SUSPENDED and
    label checks to such lines. A condition a person wrote shows up on the line PIT reports, or on the line before it
    when that line ends with `&&`, `||`, `?:` or an open `if (`/`when (`/`while (`; a condition split in another way is
    not recognised.
    """
    if NEGATED_CONDITIONAL not in description or source is None:
        return False
    in_generated_frame = (mutation.findtext("mutatedClass"), mutation.findtext("mutatedMethod")) in composables or is_suspend_method(mutation)
    return in_generated_frame and not source_line_has_condition(source, int(mutation.findtext("lineNumber")))


def is_uncovered_suspend_return_copy(mutation, killed_returns, source):
    """An uncovered copy of a suspend function's null-return mutation whose covered copy a test killed.

    The coroutine compiler writes one return per suspension path; the returned value is already proven by the killed copy.
    A line with a condition can hold returns a person wrote, so its copies still count.
    """
    if mutation.get("status") != "NO_COVERAGE" or mutation_key(mutation) not in killed_returns or source is None:
        return False
    return not source_line_has_condition(source, int(mutation.findtext("lineNumber")))


def declares_only_unit_suspend_functions(source, name):
    """True when every `suspend fun <name>` in the Kotlin source has no return type, or `: Unit`, before its `{` body."""
    found = False
    for match in re.finditer(r"\bsuspend\s+(?:[a-z]+\s+)*fun\s+(?:<[^>]*>\s*)?(?:[\w.<>?, ]+\.)?" + re.escape(name) + r"\s*\(", source):
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


def is_compiler_generated(m, description, composables, source=None, killed_returns=frozenset()):
    """Mutations in code the Kotlin/Compose compiler writes, or that change nothing a caller can see:
    nothing a test can meaningfully kill."""
    if is_generated_conditional(m, description, composables, source) or is_uncovered_suspend_return_copy(m, killed_returns, source):
        return True
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
    killed_returns = killed_suspend_returns(root)
    for m in root:
        source = m.findtext("sourceFile")
        line = int(m.findtext("lineNumber"))
        if line not in by_file.get(source, ()):
            continue
        if source not in sources:
            with open(paths[source]) as file:
                sources[source] = file.read()
        description = m.findtext("description") or ""
        if is_compiler_generated(m, description, composables, sources[source], killed_returns):
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
    parser.add_argument("--threshold", type=float, help="defaults to the verification profile's mutation_threshold")
    parser.add_argument("--lock")
    parser.add_argument("--android-variant", default=DEFAULT_ANDROID_VARIANT, help="Android build variant whose unit tests PIT runs")
    args = parser.parse_args()
    worktree = os.path.abspath(args.worktree)
    args.threshold = verification_profile.mutation_threshold(worktree, args.threshold)
    android_sdk.ensure_android_sdk_environment()
    ensure_jars()

    counts = collections.Counter()
    survivors, modules, skipped = [], [], {}
    for module_dir, paths in sorted(changed_source_files(worktree, args.base).items()):
        kind = module_kind(worktree, module_dir)
        production_files = files_in_source_sets(paths, kind, MAIN_SOURCE_SETS[kind])
        if not production_files:
            continue
        changed = changed_lines(worktree, args.base, production_files)
        tests = test_classes(worktree, files_in_source_sets(paths, kind, TEST_SOURCE_SETS[kind]))
        if not changed or not tests:
            skipped[module_dir or "."] = "no changed lines" if not changed else "no changed tests"
            continue
        report_dir = os.path.join(worktree, "build", "pit-report", module_dir.replace("/", "-") or "root")
        mutations, error = run_module(worktree, module_dir, kind, args.android_variant, changed, tests, report_dir)
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
