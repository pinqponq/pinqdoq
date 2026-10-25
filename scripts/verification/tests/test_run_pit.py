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
    viewModel: ChatViewModel = koinViewModel()
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
}

class ChatService(private val module: Module) {
    suspend fun createSession(): Session =
        module.send(endpoint = "session")
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
        run_pit.count_mutations(worktree, str(report), {"src/Sample.kt": set(range(1, 40))}, counts, survivors)
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
        ])

        self.assertEqual(5, counts["noise"])
        self.assertEqual([], survivors)

    def test_conditionals_on_lines_with_a_source_condition_still_count(self):
        lines = [screen_line(text) for text in (
            "if (!state.isVisible)", "filter {", "?: \"fallback", "Count $count", "as? User", "orEmpty()",
            "${if (isActive)", "state.isEnabled", "        state.isVisible", "https://$host", "isEmpty()", "recover {", "quote = '\"'")]
        counts, survivors = count_in(SCREEN_SOURCE, [conditional("ChatScreenKt", "ChatScreen", line) for line in lines])

        self.assertEqual(0, counts["noise"])
        self.assertEqual(sorted(lines), [s["line"] for s in survivors])

    def test_conditionals_outside_composable_and_suspend_functions_still_count(self):
        counts, _ = count_in(SCREEN_SOURCE, [conditional("ChatService", "plain", screen_line("module.send("), signature="()V")])

        self.assertEqual(0, counts["noise"])
        self.assertEqual(1, counts["SURVIVED"])

    def test_conditionals_in_suspend_state_machines_without_a_source_condition_are_noise(self):
        line = screen_line("module.send(")
        counts, _ = count_in(SCREEN_SOURCE, [
            conditional("ChatService", "createSession", line, signature=SUSPEND),
            conditional("ChatViewModel$open$1", "invokeSuspend", line, signature="(Ljava/lang/Object;)Ljava/lang/Object;"),
        ])

        self.assertEqual(2, counts["noise"])

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


if __name__ == "__main__":
    unittest.main()
