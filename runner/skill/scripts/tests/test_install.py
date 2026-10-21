import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import install  # noqa: E402

ROUTINE_TEMPLATE = (install.RUNNER_DIR_IN_REPO / "templates" / "routine.md").read_text()


def routine_prompt(runner_label):
    task_id, label, session_prefix = next(routine for routine in install.ROUTINES if routine[1] == runner_label)
    return install.render_routine_prompt(ROUTINE_TEMPLATE, task_id, label, session_prefix, "/workspace")


class RoutinesTest(unittest.TestCase):
    def test_runner_4_is_a_manual_routine(self):
        self.assertIn(("pinqloq-task-runner-4", "runner-4", "manual"), install.ROUTINES)

    def test_only_runner_3_is_light_only(self):
        self.assertEqual({"runner-3"}, install.LIGHT_ONLY_RUNNERS)

    def test_runner_4_prompt_equals_runner_2_apart_from_the_name(self):
        runner_4_as_runner_2 = (routine_prompt("runner-4").replace("pinqloq-task-runner-4", "pinqloq-task-runner-2")
                                .replace("runner-4", "runner-2"))

        self.assertEqual(routine_prompt("runner-2"), runner_4_as_runner_2)

    def test_runner_4_claims_heavy_tasks(self):
        self.assertNotIn("--light-only", routine_prompt("runner-4"))
        self.assertIn("--light-only", routine_prompt("runner-3"))


if __name__ == "__main__":
    unittest.main()
