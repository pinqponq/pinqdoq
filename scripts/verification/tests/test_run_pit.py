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
"""


def mutation(xml_class, method, line, status="SURVIVED", description=None, signature=SUSPEND):
    description = description or f"replaced return value with null for {xml_class.replace('.', '/')}::{method}"
    return (f'<mutation detected="false" status="{status}"><sourceFile>Sample.kt</sourceFile>'
            f"<mutatedClass>{xml_class}</mutatedClass><mutatedMethod>{method}</mutatedMethod>"
            f"<methodDescription>{signature}</methodDescription><lineNumber>{line}</lineNumber>"
            f"<mutator>org.pitest.mutationtest.engine.gregor.mutators.returns.NullReturnValsMutator</mutator>"
            f"<description>{description}</description></mutation>")


class UnitSuspendNullReturnTest(unittest.TestCase):
    def count(self, *mutations):
        with tempfile.TemporaryDirectory() as worktree:
            Path(worktree, "src").mkdir()
            Path(worktree, "src/Sample.kt").write_text(SOURCE)
            report = Path(worktree, "mutations.xml")
            report.write_text("<mutations>" + "".join(mutations) + "</mutations>")
            counts, survivors = collections.Counter(), []
            run_pit.count_mutations(worktree, str(report), {"src/Sample.kt": set(range(1, 40))}, counts, survivors)
            return counts, survivors

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

    def test_other_mutators_on_unit_suspend_functions_still_count(self):
        counts, _ = self.count(mutation("Sample", "unregisterToken", 4, description="negated conditional"))

        self.assertEqual(0, counts["noise"])
        self.assertEqual(1, counts["SURVIVED"])


if __name__ == "__main__":
    unittest.main()
