import collections
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import run_pit  # noqa: E402

SUSPEND = "(Lkotlin/coroutines/Continuation;)Ljava/lang/Object;"
SOURCE = """
class Sample(private val other: Other) : Port {
    override suspend fun unregisterToken() {
        other.unregisterToken()
    }

    suspend fun clear(): Unit {
        other.clear()
    }

    suspend fun load(
        id: String,
    ): String {
        return other.load(id)
    }

    suspend fun inferred() = other.inferred()

    fun plain() {
    }
}

suspend fun Receiver.enableAndLog(
    controller: Controller,
    entryPoint: (String) -> Unit
) {
    enable(controller) ?: return
}

class Initialize(private val other: Other) {
    suspend operator fun invoke() {
        other.connect()
    }
}
"""


COMPOSABLE = "(Lfeature/chat/ChatViewModel;Landroidx/compose/runtime/Composer;II)V"
COMPOSABLE_LAMBDA = "(Landroidx/compose/runtime/Composer;I)Lkotlin/Unit;"
NEGATED = "org.pitest.mutationtest.engine.gregor.mutators.NegateConditionalsMutator"
VOID_CALL = "org.pitest.mutationtest.engine.gregor.mutators.VoidMethodCallMutator"
NULL_RETURN = "org.pitest.mutationtest.engine.gregor.mutators.returns.NullReturnValsMutator"
SCREEN_SOURCE = """
@Composable
fun ChatScreen(
    viewModel: ChatViewModel = koinViewModel(),
    onFailure: (Throwable) -> Unit = {},
    onPick: (Int, String) -> Unit = { _, _ -> },
    onSave: suspend () -> Unit = {},
) {
    val state = viewModel.getState()
    if (!state.isVisible) return
    StateLayout(state = state, onClose = { viewModel.close() }) {
        ChatContent(state = state.uiState)
    }
    val names = state.items.filter { it.isActive }
    val label = state.title ?: "fallback // not a comment"
    Text(text = "a == b")
    Text(text = "Count $count", color = if (isActive) A else B, label = "x")
    val user = item as? User
    val shown = state.title.orEmpty()
    Text(text = "${if (isActive) "on" else "off"}")
    val enabled = state.isReady &&
        state.isEnabled
    val visible = if (
        state.isVisible
    ) 1 else 0
    Link(url = "https://$host", style = if (secure) A else B)
    val empty = name.isEmpty()
    val value = result.recover { 0 }
    Text(quote = '"', size = if (large) 2 else 1, label = "z")
    val hidden = !(state.isVisible)
    val photos = items.filterIsInstance<Photo>()
    val maps = items.filterIsInstance<Map<String, Int>>()
    val parsed = result.mapCatching { it.size }
    when (state.mode) {
        Mode.Loading -> Spinner()
        (Mode.Empty) -> EmptyView()
    }
}

class ChatService(private val module: Module) {
    suspend fun createSession(): Session =
        module.send(endpoint = "session")

    suspend fun getOrCreateConversation(): Conversation =
        mapper.mapToDomain(module.send(endpoint = "conversation"))

    suspend fun load(cached: Boolean): Session = if (cached) session else module.send(endpoint = "load")
}
"""


def mutation(xml_class, method, line, status="SURVIVED", description=None, signature=SUSPEND, mutator=NULL_RETURN):
    description = description or f"replaced return value with null for {xml_class.replace('.', '/')}::{method}"
    return (f'<mutation detected="false" status="{status}"><sourceFile>Sample.kt</sourceFile>'
            f"<mutatedClass>{xml_class}</mutatedClass><mutatedMethod>{method}</mutatedMethod>"
            f"<methodDescription>{signature}</methodDescription><lineNumber>{line}</lineNumber>"
            f"<mutator>{mutator}</mutator>"
            f"<description>{description}</description></mutation>")


def conditional(xml_class, method, line, signature=COMPOSABLE, status="SURVIVED"):
    return mutation(xml_class, method, line, status=status, description="negated conditional", signature=signature, mutator=NEGATED)


def count_in(source, mutations):
    with tempfile.TemporaryDirectory() as worktree:
        Path(worktree, "src").mkdir()
        Path(worktree, "src/Sample.kt").write_text(source)
        report = Path(worktree, "mutations.xml")
        report.write_text("<mutations>" + "".join(mutations) + "</mutations>")
        counts, survivors = collections.Counter(), []
        run_pit.count_mutations(worktree, str(report), {"src/Sample.kt": set(range(1, len(source.splitlines()) + 1))}, counts, survivors)
        return counts, survivors


def screen_line(text):
    return next(number for number, line in enumerate(SCREEN_SOURCE.splitlines(), 1) if text in line)


class GeneratedConditionalTest(unittest.TestCase):
    def test_conditionals_on_composable_lines_without_a_source_condition_are_noise(self):
        counts, survivors = count_in(SCREEN_SOURCE, [
            conditional("ChatScreenKt", "ChatScreen", screen_line("fun ChatScreen(")),
            conditional("ChatScreenKt", "ChatScreen", screen_line(") {"), status="KILLED"),
            conditional("ChatScreenKt", "ChatScreen", screen_line("StateLayout(")),
            conditional("ChatScreenKt", "ChatScreen$lambda$3", screen_line("ChatContent("), signature=COMPOSABLE_LAMBDA),
            conditional("ChatScreenKt", "ChatScreen", screen_line('"a == b"')),
            conditional("ChatScreenKt", "ChatScreen", screen_line("onFailure: (Throwable) -> Unit")),
            conditional("ChatScreenKt", "ChatScreen", screen_line("onSave: suspend () -> Unit")),
        ])

        self.assertEqual(7, counts["noise"])
        self.assertEqual([], survivors)

    def test_conditionals_on_lines_with_a_source_condition_still_count(self):
        lines = [screen_line(text) for text in (
            "if (!state.isVisible)", "filter {", "?: \"fallback", "Count $count", "as? User", "orEmpty()",
            "${if (isActive)", "state.isEnabled", "        state.isVisible", "https://$host", "isEmpty()", "recover {", "quote = '\"'", "!(state", "filterIsInstance<Photo", "filterIsInstance<Map", "mapCatching {",
            "onPick: (Int, String)", "Mode.Loading ->", "(Mode.Empty) ->")]
        counts, survivors = count_in(SCREEN_SOURCE, [conditional("ChatScreenKt", "ChatScreen", line) for line in lines])

        self.assertEqual(0, counts["noise"])
        self.assertEqual(sorted(lines), sorted(s["line"] for s in survivors))

    def test_conditionals_outside_composable_and_suspend_functions_still_count(self):
        counts, _ = count_in(SCREEN_SOURCE, [conditional("ChatService", "plain", screen_line("module.send("), signature="()V")])

        self.assertEqual(0, counts["noise"])
        self.assertEqual(1, counts["SURVIVED"])

    def test_conditionals_in_suspend_state_machines_without_a_source_condition_are_noise(self):
        line = screen_line("module.send(")
        counts, _ = count_in(SCREEN_SOURCE, [
            conditional("ChatService", "createSession", line, signature=SUSPEND),
            conditional("ChatViewModel$open$1", "invokeSuspend", line, signature="(Ljava/lang/Object;)Ljava/lang/Object;"),
            conditional("ChatService", "getOrCreateConversation", screen_line("fun getOrCreateConversation("), signature=SUSPEND),
            conditional("ChatService", "getOrCreateConversation", screen_line("mapToDomain("), signature=SUSPEND),
        ])

        self.assertEqual(4, counts["noise"])

    def test_removed_calls_in_composables_still_count(self):
        counts, _ = count_in(SCREEN_SOURCE, [mutation("ChatScreenKt", "ChatScreen", screen_line('"a == b"'),
                                                      description="removed call to Text", signature=COMPOSABLE, mutator=VOID_CALL)])

        self.assertEqual(0, counts["noise"])
        self.assertEqual(1, counts["SURVIVED"])


class SuspendReturnCopyTest(unittest.TestCase):
    def setUp(self):
        self.line = screen_line("suspend fun createSession")

    def test_uncovered_copies_of_a_killed_suspend_return_are_noise(self):
        counts, survivors = count_in(SCREEN_SOURCE, [
            mutation("ChatService", "createSession", self.line, status="KILLED"),
            mutation("ChatService", "createSession", self.line, status="NO_COVERAGE"),
            mutation("ChatService", "createSession", self.line, status="NO_COVERAGE"),
        ])

        self.assertEqual((1, 2), (counts["KILLED"], counts["noise"]))
        self.assertEqual([], survivors)

    def test_uncovered_suspend_return_without_a_killed_copy_still_counts(self):
        counts, survivors = count_in(SCREEN_SOURCE, [mutation("ChatService", "createSession", self.line, status="NO_COVERAGE")])

        self.assertEqual(0, counts["noise"])
        self.assertEqual(["NO_COVERAGE"], [s["status"] for s in survivors])

    def test_surviving_copy_of_a_killed_suspend_return_still_counts(self):
        counts, _ = count_in(SCREEN_SOURCE, [
            mutation("ChatService", "createSession", self.line, status="KILLED"),
            mutation("ChatService", "createSession", self.line, status="SURVIVED"),
        ])

        self.assertEqual((0, 1), (counts["noise"], counts["SURVIVED"]))

    def test_uncovered_return_on_a_line_with_a_condition_still_counts(self):
        line = screen_line("suspend fun load(")
        counts, survivors = count_in(SCREEN_SOURCE, [
            mutation("ChatService", "load", line, status="KILLED"),
            mutation("ChatService", "load", line, status="NO_COVERAGE"),
        ])

        self.assertEqual(0, counts["noise"])
        self.assertEqual(["NO_COVERAGE"], [s["status"] for s in survivors])


class UnitSuspendNullReturnTest(unittest.TestCase):
    def count(self, *mutations):
        return count_in(SOURCE, mutations)

    def test_null_return_from_unit_suspend_functions_is_noise(self):
        counts, survivors = self.count(
            mutation("Sample", "unregisterToken", 4),
            mutation("Sample", "clear", 8),
            mutation("SampleKt", "enableAndLog", 27),
        )

        self.assertEqual(3, counts["noise"])
        self.assertEqual([], survivors)

    def test_null_return_from_flow_collector_emit_is_noise(self):
        counts, survivors = self.count(mutation("Sample$observe$1$2", "emit", 4, status="NO_COVERAGE"))

        self.assertEqual(1, counts["noise"])
        self.assertEqual([], survivors)

    def test_null_return_from_suspend_function_with_a_value_still_counts(self):
        counts, survivors = self.count(mutation("Sample", "load", 14))

        self.assertEqual(0, counts["noise"])
        self.assertEqual(["load"], [s["description"].rsplit("::", 1)[1] for s in survivors])

    def test_null_return_from_expression_body_suspend_function_still_counts(self):
        counts, _ = self.count(mutation("Sample", "inferred", 17))

        self.assertEqual(0, counts["noise"])
        self.assertEqual(1, counts["SURVIVED"])

    def test_null_return_from_non_suspend_function_still_counts(self):
        counts, _ = self.count(mutation("Sample", "plain", 19, signature="()V"))

        self.assertEqual(0, counts["noise"])
        self.assertEqual(1, counts["SURVIVED"])

    def test_null_return_from_unit_suspend_operator_function_is_noise(self):
        counts, survivors = self.count(mutation("Sample", "invoke", 30), mutation("Sample", "invoke", 31, status="NO_COVERAGE"))

        self.assertEqual(2, counts["noise"])
        self.assertEqual([], survivors)

    def test_other_mutators_on_unit_suspend_functions_still_count(self):
        counts, _ = self.count(mutation("SampleKt", "enableAndLog", 27, description="negated conditional"))

        self.assertEqual(0, counts["noise"])
        self.assertEqual(1, counts["SURVIVED"])


def make_module(worktree, module_dir, build_file=None, build_text="", folders=(), files=()):
    module = Path(worktree, module_dir)
    module.mkdir(parents=True, exist_ok=True)
    if build_file:
        Path(module, build_file).write_text(build_text)
    for folder in folders:
        Path(module, folder).mkdir(parents=True, exist_ok=True)
    for path in files:
        Path(module, path).parent.mkdir(parents=True, exist_ok=True)
        Path(module, path).write_text("")


class ModuleKindTest(unittest.TestCase):
    def kind(self, **module):
        with tempfile.TemporaryDirectory() as worktree:
            make_module(worktree, "app", **module)
            return run_pit.module_kind(worktree, "app")

    def test_multiplatform_plugin_alias_is_kotlin_multiplatform(self):
        self.assertEqual("kmp", self.kind(build_file="build.gradle.kts",
                                          build_text="plugins {\n    alias(libs.plugins.kotlinMultiplatform)\n    alias(libs.plugins.androidApplication)\n}"))

    def test_applied_android_application_plugin_is_android(self):
        self.assertEqual("android", self.kind(build_file="build.gradle",
                                              build_text="apply plugin: 'com.android.application'\napply plugin: 'kotlin-android'"))

    def test_android_library_plugin_alias_is_android(self):
        self.assertEqual("android", self.kind(build_file="build.gradle.kts", build_text="plugins { alias(libs.plugins.android.library) }"))

    def test_android_module_with_a_multiplatform_library_dependency_is_android(self):
        self.assertEqual("android", self.kind(build_file="build.gradle.kts", build_text=(
            'plugins { id("com.android.application") }\n'
            'dependencies { implementation("com.russhwolf:multiplatform-settings:1.2.0") }\n'
            'compose.multiplatform')))

    def test_applied_kotlin_multiplatform_plugin_ids_are_kotlin_multiplatform(self):
        for build_text in ('plugins { kotlin("multiplatform") }', "plugins { id 'org.jetbrains.kotlin.multiplatform' }",
                           "apply plugin: 'kotlin-multiplatform'"):
            with self.subTest(build_text=build_text):
                self.assertEqual("kmp", self.kind(build_file="build.gradle.kts", build_text=build_text))

    def test_kotlin_jvm_module_is_plain_jvm(self):
        self.assertEqual("jvm", self.kind(build_file="build.gradle.kts", build_text='plugins { kotlin("jvm") }'))

    def test_convention_plugin_with_multiplatform_folders_is_kotlin_multiplatform(self):
        self.assertEqual("kmp", self.kind(build_file="build.gradle.kts", build_text='plugins { id("company.library") }',
                                          folders=("src/commonMain/kotlin",)))

    def test_module_without_build_file_and_with_android_manifest_is_android(self):
        self.assertEqual("android", self.kind(files=("src/main/AndroidManifest.xml",)))

    def test_module_without_build_file_or_android_manifest_is_plain_jvm(self):
        self.assertEqual("jvm", self.kind(folders=("src/main/java",)))


class SourceSetSelectionTest(unittest.TestCase):
    PATHS = [
        "composeApp/src/commonMain/kotlin/feature/Login.kt",
        "composeApp/src/desktopTest/kotlin/feature/LoginTest.kt",
        "app/src/main/java/com/example/Plate.java",
        "app/src/main/java/com/example/Recovery.kt",
        "app/src/main/kotlin/com/example/Format.kt",
        "app/src/test/java/com/example/PlateTest.java",
        "app/src/emulator/java/com/example/FakeTerminal.kt",
        "app/src/androidTest/java/com/example/PlateUiTest.kt",
        "app/src/main/java/com/example/notes.txt",
        "composeApp/src/androidMain/kotlin/feature/Platform.kt",
        "composeApp/src/commonMain/java/feature/Legacy.java",
    ]

    def test_kotlin_multiplatform_takes_only_kotlin_in_its_jvm_source_sets(self):
        self.assertEqual(["composeApp/src/commonMain/kotlin/feature/Login.kt"],
                         run_pit.files_in_source_sets(self.PATHS, "kmp", run_pit.MAIN_SOURCE_SETS["kmp"]))
        self.assertEqual(["composeApp/src/desktopTest/kotlin/feature/LoginTest.kt"],
                         run_pit.files_in_source_sets(self.PATHS, "kmp", run_pit.TEST_SOURCE_SETS["kmp"]))

    def test_android_takes_java_and_kotlin_from_main_and_test(self):
        self.assertEqual(["app/src/main/java/com/example/Plate.java", "app/src/main/java/com/example/Recovery.kt",
                          "app/src/main/kotlin/com/example/Format.kt"],
                         run_pit.files_in_source_sets(self.PATHS, "android", run_pit.MAIN_SOURCE_SETS["android"]))
        self.assertEqual(["app/src/test/java/com/example/PlateTest.java"],
                         run_pit.files_in_source_sets(self.PATHS, "android", run_pit.TEST_SOURCE_SETS["android"]))

    def test_plain_jvm_takes_the_same_folders_as_android(self):
        self.assertEqual(run_pit.files_in_source_sets(self.PATHS, "android", run_pit.MAIN_SOURCE_SETS["android"]),
                         run_pit.files_in_source_sets(self.PATHS, "jvm", run_pit.MAIN_SOURCE_SETS["jvm"]))
        self.assertEqual(run_pit.files_in_source_sets(self.PATHS, "android", run_pit.TEST_SOURCE_SETS["android"]),
                         run_pit.files_in_source_sets(self.PATHS, "jvm", run_pit.TEST_SOURCE_SETS["jvm"]))

    def test_source_directories_list_only_existing_folders_of_the_module_kind(self):
        with tempfile.TemporaryDirectory() as worktree:
            make_module(worktree, "app", folders=("src/main/java", "src/commonMain/kotlin"))
            make_module(worktree, "shared", folders=("src/commonMain/kotlin", "src/jvmMain/kotlin", "src/main/java"))

            self.assertEqual(["app/src/main/java"], run_pit.source_directories(worktree, "app", "android"))
            self.assertEqual(["shared/src/commonMain/kotlin", "shared/src/jvmMain/kotlin"], run_pit.source_directories(worktree, "shared", "kmp"))


class GradleCommandTest(unittest.TestCase):
    def test_executable_wrapper_runs_directly(self):
        with tempfile.TemporaryDirectory() as worktree:
            Path(worktree, "gradlew").write_text("")
            os.chmod(Path(worktree, "gradlew"), 0o755)

            self.assertEqual(["./gradlew"], run_pit.gradle_command(worktree))

    def test_wrapper_without_executable_bit_runs_through_sh(self):
        with tempfile.TemporaryDirectory() as worktree:
            Path(worktree, "gradlew").write_text("")
            os.chmod(Path(worktree, "gradlew"), 0o644)

            self.assertEqual(["sh", "gradlew"], run_pit.gradle_command(worktree))


class PrintedValueTest(unittest.TestCase):
    def test_reads_the_classpath_and_mutable_code_lines(self):
        output = "Configuration on demand\nPITCP=/app/kotlin:/app/javac:/cache/junit.jar\nPITCODE=/app/kotlin:/app/javac\n"

        self.assertEqual("/app/kotlin:/app/javac:/cache/junit.jar", run_pit.printed_value(output, run_pit.CLASSPATH_PREFIX))
        self.assertEqual("/app/kotlin:/app/javac", run_pit.printed_value(output, run_pit.MUTABLE_CODE_PREFIX))

    def test_missing_mutable_code_line_gives_none(self):
        self.assertIsNone(run_pit.printed_value("PITCP=/app/classes\n", run_pit.MUTABLE_CODE_PREFIX))


class JavaSourceTest(unittest.TestCase):
    def test_java_and_kotlin_test_files_give_their_class_names(self):
        with tempfile.TemporaryDirectory() as worktree:
            Path(worktree, "PlateTest.java").write_text("package com.example.plate;\n\npublic class PlateTest {}\n")
            Path(worktree, "RecoveryTest.kt").write_text("package com.example.recovery\n\nclass RecoveryTest\n")
            Path(worktree, "Plate.java").write_text("package com.example.plate;\n")

            self.assertEqual(["com.example.plate.PlateTest", "com.example.recovery.RecoveryTest"],
                             run_pit.test_classes(worktree, ["PlateTest.java", "RecoveryTest.kt", "Plate.java"]))

    def test_mutations_in_a_java_file_count_on_its_changed_lines(self):
        source = "package com.example;\n\npublic final class Plate {\n    static boolean same(String a, String b) {\n        return a.equals(b);\n    }\n}\n"
        with tempfile.TemporaryDirectory() as worktree:
            Path(worktree, "Plate.java").write_text(source)
            report = Path(worktree, "mutations.xml")
            report.write_text("<mutations>" + "".join(
                f'<mutation detected="false" status="{status}"><sourceFile>Plate.java</sourceFile>'
                f"<mutatedClass>com.example.Plate</mutatedClass><mutatedMethod>same</mutatedMethod>"
                f"<methodDescription>(Ljava/lang/String;Ljava/lang/String;)Z</methodDescription><lineNumber>{line}</lineNumber>"
                f"<mutator>org.pitest.mutationtest.engine.gregor.mutators.returns.BooleanTrueReturnValsMutator</mutator>"
                f"<description>replaced boolean return with true for com/example/Plate::same</description></mutation>"
                for status, line in (("KILLED", 5), ("SURVIVED", 5), ("SURVIVED", 7))) + "</mutations>")
            counts, survivors = collections.Counter(), []

            run_pit.count_mutations(worktree, str(report), {"Plate.java": {5}}, counts, survivors)

        self.assertEqual(1, counts["KILLED"])
        self.assertEqual(1, counts["SURVIVED"])
        self.assertEqual([("Plate.java", 5)], [(survivor["file"], survivor["line"]) for survivor in survivors])


if __name__ == "__main__":
    unittest.main()
