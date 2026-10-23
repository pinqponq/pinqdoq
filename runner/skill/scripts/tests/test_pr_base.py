import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pr_base  # noqa: E402

BLOCK_LIST = """name: Deploy prod
on:
  push:
    branches:
      - main
      - 'release/**'
  pull_request:
    branches:
      - develop
jobs:
  deploy: {}
"""

INLINE_LIST = """on:
  push:
    branches: [develop, hotfix/*]
"""

PULL_REQUEST_ONLY = """on:
  pull_request:
    branches:
      - main
"""

NO_BRANCH_FILTER = """on:
  push:
    tags: ['v*']
"""


class ChooseBaseTest(unittest.TestCase):
    def test_develop_wins_when_it_exists(self):
        self.assertEqual(pr_base.choose_base("main", True), "develop")

    def test_default_branch_when_no_develop(self):
        self.assertEqual(pr_base.choose_base("master", False), "master")


class BaseProblemTest(unittest.TestCase):
    def test_refuses_default_branch_when_develop_exists(self):
        message = pr_base.base_problem("main", "main", True)
        self.assertIn("develop", message)
        self.assertIn("Refused", message)

    def test_accepts_develop_when_it_exists(self):
        self.assertIsNone(pr_base.base_problem("develop", "main", True))

    def test_accepts_default_branch_without_develop(self):
        self.assertIsNone(pr_base.base_problem("main", "main", False))

    def test_refuses_develop_when_it_does_not_exist(self):
        self.assertIn("Refused", pr_base.base_problem("develop", "main", False))

    def test_refuses_other_base_without_develop(self):
        self.assertIn("`main`", pr_base.base_problem("release/1", "main", False))

    def test_accepts_another_task_branch_for_stacked_prs(self):
        self.assertIsNone(pr_base.base_problem("task/7-base", "main", True, is_task_branch=True))

    def test_refuses_any_other_base(self):
        self.assertIn("`develop`", pr_base.base_problem("release/1", "main", True))


class PushFilterTest(unittest.TestCase):
    def test_reads_block_list_under_push_only(self):
        self.assertEqual(pr_base.push_filter(BLOCK_LIST), ["main", "release/**"])

    def test_reads_inline_list(self):
        self.assertEqual(pr_base.push_filter(INLINE_LIST), ["develop", "hotfix/*"])

    def test_pull_request_branches_do_not_count(self):
        self.assertEqual(pr_base.push_filter(PULL_REQUEST_ONLY), [])

    def test_tags_only_push_does_not_run_on_a_branch(self):
        self.assertEqual(pr_base.push_filter(NO_BRANCH_FILTER), [])

    def test_unfiltered_push_runs_on_any_branch(self):
        self.assertEqual(pr_base.push_filter("on:\n  push:\n  workflow_dispatch:\n"), "any")
        self.assertEqual(pr_base.push_filter("on: push\n"), "any")
        self.assertEqual(pr_base.push_filter("on: [push, pull_request]\n"), "any")

    def test_branches_ignore_counts_as_any(self):
        self.assertEqual(pr_base.push_filter("on:\n  push:\n    branches-ignore: [wip]\n"), "any")


class EnvironmentNoteTest(unittest.TestCase):
    workflows = {"deploy-prod.yml": BLOCK_LIST, "deploy-test.yml": INLINE_LIST, "ci.yml": PULL_REQUEST_ONLY}

    def test_names_the_workflow_that_runs_on_push(self):
        self.assertIn("deploy-prod.yml", pr_base.environment_note(self.workflows, "main"))
        self.assertNotIn("deploy-test.yml", pr_base.environment_note(self.workflows, "main"))

    def test_glob_matches_branch(self):
        self.assertEqual(pr_base.deploying_workflows(self.workflows, "release/2"), ["deploy-prod.yml"])
        self.assertEqual(pr_base.deploying_workflows(self.workflows, "release/2/x"), ["deploy-prod.yml"])
        self.assertEqual(pr_base.deploying_workflows(self.workflows, "hotfix/a"), ["deploy-test.yml"])
        self.assertEqual(pr_base.deploying_workflows(self.workflows, "hotfix/a/b"), [])

    def test_unfiltered_push_workflow_is_listed(self):
        self.assertIn("ci.yml", pr_base.environment_note({"ci.yml": "on: push\n"}, "develop"))

    def test_says_when_nothing_deploys(self):
        self.assertIn("starts no workflow", pr_base.environment_note({"ci.yml": PULL_REQUEST_ONLY}, "main"))


if __name__ == "__main__":
    unittest.main()
