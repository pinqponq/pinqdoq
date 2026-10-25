import collections
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import run_stryker_js  # noqa: E402

SOURCE = "export function discount(price: number, percent: number): number {\n" \
         "  if (percent <= 0) return price;\n" \
         "  return price - (price * percent) / 100;\n" \
         "}\n"


def mutant(line, status, mutator="EqualityOperator", replacement="percent < 0"):
    return {"id": f"{line}-{status}", "mutatorName": mutator, "replacement": replacement, "status": status,
            "location": {"start": {"line": line, "column": 7}, "end": {"line": line, "column": 19}}}


class ProductionFilesTest(unittest.TestCase):
    def test_keeps_only_production_sources(self):
        files = ["src/price.ts", "src/Cart.tsx", "src/price.test.ts", "src/Cart.spec.tsx", "src/types.d.ts",
                 "src/__tests__/cart.ts", "e2e/flows/cart.spec.ts", "e2e/subflows/menu.ts", "vite.config.ts",
                 "src/Cart.stories.tsx", "README.md", "src/styles.css", "src/util.mjs"]

        self.assertEqual(["src/price.ts", "src/Cart.tsx", "src/util.mjs"], run_stryker_js.production_files(files))


class CountMutantsTest(unittest.TestCase):
    def count(self, mutants, changed_lines):
        files = {"src/price.ts": {"language": "typescript", "source": SOURCE, "mutants": mutants}}
        counts, survivors = collections.Counter(), []
        missing = run_stryker_js.count_mutants(files, {"src/price.ts": changed_lines}, counts, survivors)
        self.assertEqual([], missing)
        return counts, survivors

    def test_counts_only_mutants_on_changed_lines(self):
        counts, survivors = self.count([mutant(2, "Survived"), mutant(3, "Survived")], {3})

        self.assertEqual(1, counts["Survived"])
        self.assertEqual([3], [s["line"] for s in survivors])

    def test_invalid_and_ignored_mutants_are_noise(self):
        counts, survivors = self.count(
            [mutant(2, "CompileError", "BlockStatement", "{}"), mutant(2, "RuntimeError"), mutant(2, "Ignored")], {2})

        self.assertEqual(3, counts["noise"])
        self.assertEqual([], survivors)

    def test_survived_and_no_coverage_are_survivors_with_the_source_line(self):
        _, survivors = self.count([mutant(2, "Survived"), mutant(2, "NoCoverage"), mutant(2, "Killed")], {2})

        self.assertEqual(["Survived", "NoCoverage"], [s["status"] for s in survivors])
        self.assertEqual("EqualityOperator: if (percent <= 0) return price; → percent < 0", survivors[0]["description"])

    def test_timeout_counts_as_detected(self):
        counts, _ = self.count([mutant(2, "Timeout")], {2})

        self.assertEqual(1, counts["Timeout"])
        self.assertEqual(0, counts["noise"])

    def test_changed_file_missing_from_the_report_is_returned(self):
        missing = run_stryker_js.count_mutants({}, {"src/price.ts": {2}}, collections.Counter(), [])

        self.assertEqual(["src/price.ts"], missing)


class GitTest(unittest.TestCase):
    def test_unknown_base_ref_raises(self):
        with tempfile.TemporaryDirectory() as worktree:
            run_stryker_js.sh(["git", "init", "-q"], worktree)

            with self.assertRaises(run_stryker_js.GitError):
                run_stryker_js.diff_files(worktree, "origin/no-such-branch", ".")


class ReportFilesTest(unittest.TestCase):
    def test_absolute_key_through_a_symbolic_link_matches(self):
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder, "project")
            project.mkdir()
            link = Path(folder, "link")
            link.symlink_to(project)
            report = Path(project, "mutation.json")
            report.write_text(json.dumps({"files": {f"{project.resolve()}/src/a.ts": {"mutants": []}}}))

            files = run_stryker_js.report_files(str(report), str(link))

        self.assertEqual(["src/a.ts"], list(files))

    def test_absolute_and_relative_keys_become_project_relative(self):
        with tempfile.TemporaryDirectory() as project:
            report = Path(project, "mutation.json")
            report.write_text(json.dumps({"files": {f"{project}/src/a.ts": {"mutants": []},
                                                    "src/b.ts": {"mutants": []}}}))

            files = run_stryker_js.report_files(str(report), project)

        self.assertEqual(["src/a.ts", "src/b.ts"], sorted(files))


if __name__ == "__main__":
    unittest.main()
