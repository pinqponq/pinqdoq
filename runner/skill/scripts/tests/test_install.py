import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import install  # noqa: E402
import runner_config  # noqa: E402

ROUTINE_TEMPLATE = (install.RUNNER_DIR_IN_REPO / "templates" / "routine.md").read_text()


def routine_prompt(runner_label):
    task_id, label, session_prefix = next(routine for routine in install.ROUTINES if routine[1] == runner_label)
    return install.render_routine_prompt(ROUTINE_TEMPLATE, task_id, label, session_prefix, "/workspace")


class RoutinesTest(unittest.TestCase):
    def test_runner_4_is_a_manual_routine(self):
        self.assertIn(("pinqloq-task-runner-4", "runner-4", "manual"), install.ROUTINES)

    def test_only_runner_3_is_light_only(self):
        self.assertEqual({"runner-3"}, install.LIGHT_ONLY_RUNNERS)

    def test_runners_1_and_2_claim_device_tasks_and_prefer_different_devices(self):
        self.assertIn("--role device", routine_prompt("runner-1"))
        self.assertIn("--platform free --prefer android", routine_prompt("runner-1"))
        self.assertIn("--role device", routine_prompt("runner-2"))
        self.assertIn("--platform free --prefer ios", routine_prompt("runner-2"))

    def test_runner_4_claims_only_tasks_without_a_device(self):
        self.assertIn("--role no-device", routine_prompt("runner-4"))
        self.assertNotIn("--light-only", routine_prompt("runner-4"))
        self.assertIn("--light-only", routine_prompt("runner-3"))

    def test_scheduled_task_names_do_not_change(self):
        self.assertEqual(["pinqloq-task-runner", "pinqloq-task-runner-2", "pinqloq-task-runner-3", "pinqloq-task-runner-4"],
                         [task_id for task_id, _, _ in install.ROUTINES])

    def test_routine_description_shows_the_role(self):
        self.assertIn("(runner-4 (no-device))", routine_prompt("runner-4"))
        self.assertIn("(runner-1 (device, android))", routine_prompt("runner-1"))

    def test_github_machine_with_pinqponq_steps_gets_no_outside_note(self):
        machine = {"forge": "github", "pinqponq_steps": True}
        self.assertEqual("", install.machine_note(machine))

    def test_gitlab_or_pinqponq_steps_off_gets_the_outside_note_once(self):
        for machine in ({"forge": "gitlab", "pinqponq_steps": False}, {"forge": "github", "pinqponq_steps": False}):
            with self.subTest(machine=machine):
                task_id, label, session_prefix = install.ROUTINES[0]
                prompt = install.render_routine_prompt(ROUTINE_TEMPLATE, task_id, label, session_prefix, "/workspace",
                                                       install.machine_note(machine))
                self.assertEqual(1, prompt.count("references/outside-pinqponq.md"))
                self.assertIn("--role device", prompt)

    def test_every_installed_runner_has_a_configured_role(self):
        self.assertEqual({label for _, label, _ in install.ROUTINES}, set(runner_config.RUNNER_ROLES))


if __name__ == "__main__":
    unittest.main()
