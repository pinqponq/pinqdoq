import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import doctor  # noqa: E402
import install  # noqa: E402
import runner_config  # noqa: E402

TODAYS_MACHINE_CONFIG = {
    "role": "queue-only",
    "workspace_dir": "~/StudioProjects",
    "worktrees_dir": "~/StudioProjects/.task-runner-worktrees",
    "runner_dir": "~/StudioProjects/pinqloq-runner",
    "pinq_center": None,
}


class MachineConfigFileTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.config_file = Path(self.directory.name) / "machine.json"
        patcher = mock.patch.object(runner_config, "MACHINE_CONFIG_FILE", self.config_file)
        patcher.start()
        self.addCleanup(patcher.stop)

    def write_config(self, values):
        self.config_file.write_text(json.dumps(values))


class ReadMachineConfigTest(MachineConfigFileTest):
    def test_machine_json_without_the_new_keys_stays_a_github_runner_with_every_pinqponq_step(self):
        self.write_config(TODAYS_MACHINE_CONFIG)
        machine = runner_config.read_machine_config()
        self.assertEqual("github", machine["forge"])
        self.assertIsNone(machine["gitlab_host"])
        self.assertTrue(machine["pinqponq_steps"])
        self.assertEqual("queue-only", machine["role"])

    def test_missing_machine_json_stays_a_github_runner(self):
        machine = runner_config.read_machine_config()
        self.assertEqual("github", machine["forge"])
        self.assertTrue(machine["pinqponq_steps"])

    def test_gitlab_machine_is_read(self):
        self.write_config({**TODAYS_MACHINE_CONFIG, "forge": "gitlab", "gitlab_host": "gitlab.example.com",
                           "pinqponq_steps": False})
        machine = runner_config.read_machine_config()
        self.assertEqual(("gitlab", "gitlab.example.com", False),
                         (machine["forge"], machine["gitlab_host"], machine["pinqponq_steps"]))

    def test_wrong_values_stop(self):
        wrong_values = [{"forge": "bitbucket"},
                        {"forge": "gitlab"},
                        {"forge": "gitlab", "gitlab_host": "https://gitlab.example.com"},
                        {"forge": "gitlab", "gitlab_host": "gitlab.example.com/group"},
                        {"pinqponq_steps": "no"},
                        {"forge": "gitlab", "gitlab_host": "gitlab.example.com", "role": "primary"}]
        for values in wrong_values:
            with self.subTest(values=values):
                self.write_config({**TODAYS_MACHINE_CONFIG, **values})
                with self.assertRaises(ValueError):
                    runner_config.read_machine_config()


def install_arguments(**values):
    defaults = {"role": None, "workspace": None, "worktrees": None, "runner_dir": None, "forge": None,
                "gitlab_host": None, "without_pinqponq_steps": False}
    return argparse.Namespace(**{**defaults, **values})


class WriteMachineConfigTest(MachineConfigFileTest):
    def test_install_without_the_new_flags_writes_a_github_runner_with_every_pinqponq_step(self):
        install.write_machine_config(install_arguments(role="queue-only"), dry_run=False)
        stored = json.loads(self.config_file.read_text())
        self.assertEqual(("queue-only", "github", None, True),
                         (stored["role"], stored["forge"], stored["gitlab_host"], stored["pinqponq_steps"]))

    def test_install_writes_a_gitlab_runner_without_pinqponq_steps(self):
        arguments = install_arguments(role="queue-only", forge="gitlab", gitlab_host="gitlab.example.com",
                                      without_pinqponq_steps=True)
        install.write_machine_config(arguments, dry_run=False)
        stored = json.loads(self.config_file.read_text())
        self.assertEqual(("gitlab", "gitlab.example.com", False),
                         (stored["forge"], stored["gitlab_host"], stored["pinqponq_steps"]))

    def test_gitlab_without_a_host_writes_nothing(self):
        with self.assertRaises(ValueError):
            install.write_machine_config(install_arguments(forge="gitlab"), dry_run=False)
        self.assertFalse(self.config_file.exists())

    def test_existing_machine_json_is_kept(self):
        self.write_config(TODAYS_MACHINE_CONFIG)
        message = install.write_machine_config(install_arguments(forge="gitlab", gitlab_host="gitlab.example.com"),
                                               dry_run=False)
        self.assertTrue(message.startswith("KEPT"))
        self.assertEqual(TODAYS_MACHINE_CONFIG, json.loads(self.config_file.read_text()))


def machine_for(forge, gitlab_host=None):
    return {"workspace_dir": Path("/workspace"), "worktrees_dir": Path("/workspace/.task-runner-worktrees"),
            "forge": forge, "gitlab_host": gitlab_host}


class RunnerFolderSettingsTest(unittest.TestCase):
    def test_github_settings_are_the_template_with_the_folders_filled_in(self):
        template_text = (install.RUNNER_DIR_IN_REPO / "templates" / "settings.local.json").read_text()
        expected_text = (template_text.replace("{HOME}", str(Path.home())).replace("{WORKSPACE_DIR}", "/workspace")
                         .replace("{WORKTREES_STORAGE_DIR}", "/workspace"))
        self.assertEqual(expected_text, install.render_settings(machine_for("github")))

    def test_gitlab_settings_keep_the_permissions_but_not_the_pinq_ponq_identity(self):
        github_settings = json.loads(install.render_settings(machine_for("github")))
        gitlab_settings = json.loads(install.render_settings(machine_for("gitlab", "gitlab.example.com")))
        self.assertNotIn("env", gitlab_settings)
        self.assertEqual(github_settings["permissions"], gitlab_settings["permissions"])


class RecordingReport(doctor.Report):
    def __init__(self):
        super().__init__()
        self.names = []

    def check(self, passed, name, hint, required=True):
        self.names.append(name)


class DoctorForgeTest(unittest.TestCase):
    def test_github_machine_needs_gh(self):
        report = RecordingReport()
        doctor.check_commands(report, "github")
        self.assertIn("command gh", report.names)
        self.assertNotIn("command glab", report.names)

    def test_gitlab_machine_needs_glab(self):
        report = RecordingReport()
        doctor.check_commands(report, "gitlab")
        self.assertIn("command glab", report.names)
        self.assertNotIn("command gh", report.names)


if __name__ == "__main__":
    unittest.main()
