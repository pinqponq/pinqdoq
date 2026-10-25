import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SCRIPTS_DIR.parents[1]
RUNNER_AGENTS_DIR = REPOSITORY_ROOT / "runner" / "agents"
sys.path.insert(0, str(SCRIPTS_DIR))

import render_agent  # noqa: E402

TEMPLATE_TEXT = render_agent.AGENTS["test"]["template"].read_text()
DEVICE_TEMPLATE_TEXT = render_agent.AGENTS["device"]["template"].read_text()


def render_generic(scripts_dir="/opt/verification", name="verification-runner"):
    return render_agent.render(TEMPLATE_TEXT, "generic", {"name": name, "scripts_dir": scripts_dir})


def render_generic_device(scripts_dir="/opt/verification"):
    return render_agent.render(DEVICE_TEMPLATE_TEXT, "generic", {"name": "device-runner", "scripts_dir": scripts_dir})


class PinqloqProfileTest(unittest.TestCase):
    def test_rendered_agents_match_the_committed_runner_agents(self):
        for agent_name, agent in render_agent.AGENTS.items():
            with self.subTest(agent=agent_name):
                rendered = render_agent.render(agent["template"].read_text(), "pinqloq", render_agent.pinqloq_values(agent_name))
                committed_file = RUNNER_AGENTS_DIR / f"{agent['pinqloq_name']}.md"
                self.assertEqual(
                    rendered, committed_file.read_text(),
                    f"{committed_file.name} differs from {agent['template'].name}; edit the template and run "
                    f"`python3 scripts/verification/render_agent.py pinqloq --agent {agent_name} "
                    f"--out runner/agents/{committed_file.name}`",
                )


class GenericProfileTest(unittest.TestCase):
    def test_nothing_of_the_task_runner_is_left(self):
        agent_text = render_generic()
        for runner_only_text in ("--lock", "locks.py", "pinqloq", "state.json", "model:"):
            with self.subTest(text=runner_only_text):
                self.assertNotIn(runner_only_text, agent_text)

    def test_every_script_points_at_the_given_folder(self):
        agent_text = render_generic("/opt/verification")
        for script_name in ("run_build.py", "run_pit.py", "run_stryker_js.py", "verification_profile.py",
                            "shrink_images.py", "clean_build_output.py"):
            with self.subTest(script=script_name):
                self.assertIn(f"/opt/verification/{script_name}", agent_text)

    def test_no_template_syntax_is_left(self):
        agent_text = render_generic()
        self.assertNotIn("[[", agent_text)
        self.assertNotIn("{{", agent_text)

    def test_name_goes_into_the_frontmatter(self):
        self.assertTrue(render_generic(name="build-checker").startswith("---\nname: build-checker\n"))

    def test_heartbeat_replaces_the_lock(self):
        self.assertIn("--heartbeat '<command>'", render_generic())


class GenericDeviceProfileTest(unittest.TestCase):
    def test_nothing_of_the_task_runner_or_pinqponq_services_is_left(self):
        agent_text = render_generic_device()
        for runner_only_text in ("--lock", "locks.py", "pinqloq", "the runner's `state.json`", "devices-", "couple", "rindle",
                                 "test-accounts.json", "unattended runs", "~/.zshrc"):
            with self.subTest(text=runner_only_text):
                self.assertNotIn(runner_only_text, agent_text)

    def test_every_script_points_at_the_given_folder(self):
        agent_text = render_generic_device("/opt/verification")
        for script_name in ("run_build.py", "shrink_images.py", "clean_build_output.py"):
            with self.subTest(script=script_name):
                self.assertIn(f"/opt/verification/{script_name}", agent_text)

    def test_no_template_syntax_is_left(self):
        agent_text = render_generic_device()
        self.assertNotIn("[[", agent_text)
        self.assertNotIn("{{", agent_text)

    def test_deployed_web_address_needs_the_callers_permission(self):
        self.assertIn("run only when the caller said that address may be used", render_generic_device())

    def test_report_has_no_log_query_section(self):
        self.assertNotIn("PINQLOQ:", render_generic_device())


class TemplateSyntaxTest(unittest.TestCase):
    def test_block_of_the_other_profile_is_removed_inline(self):
        self.assertEqual(render_agent.render("a[[pinqloq: b]] c\n", "generic", {}), "a c\n")
        self.assertEqual(render_agent.render("a[[pinqloq: b]] c\n", "pinqloq", {}), "a b c\n")

    def test_line_holding_only_the_other_profile_is_dropped(self):
        self.assertEqual(render_agent.render("one\n[[pinqloq:two]]\nthree\n", "generic", {}), "one\nthree\n")

    def test_empty_line_without_blocks_is_kept(self):
        self.assertEqual(render_agent.render("one\n\nthree\n", "generic", {}), "one\n\nthree\n")

    def test_missing_placeholder_value_stops(self):
        with self.assertRaises(SystemExit):
            render_agent.render("{{unknown}}\n", "generic", {})

    def test_unknown_profile_stops(self):
        with self.assertRaises(SystemExit):
            render_agent.render("text\n", "other", {})


class CommandLineTest(unittest.TestCase):
    def run_render_script(self, *arguments):
        return subprocess.run([sys.executable, str(SCRIPTS_DIR / "render_agent.py"), *arguments],
                              capture_output=True, text=True)

    def test_generic_needs_a_scripts_folder(self):
        self.assertNotEqual(self.run_render_script("generic").returncode, 0)

    def test_pinqloq_refuses_overrides(self):
        self.assertNotEqual(self.run_render_script("pinqloq", "--name", "other").returncode, 0)

    def test_device_agent_gets_its_own_default_name(self):
        result = self.run_render_script("generic", "--agent", "device", "--scripts-dir", "/opt/verification")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith("---\nname: device-runner\n"))

    def test_generic_writes_the_agent_file(self):
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "agents" / "verification-runner.md"
            result = self.run_render_script("generic", "--scripts-dir", "/opt/verification/", "--out", str(output_path))
            self.assertEqual(result.returncode, 0, result.stderr)
            agent_text = output_path.read_text()
        self.assertIn("/opt/verification/run_build.py", agent_text)
        self.assertNotIn("/opt/verification//", agent_text)


if __name__ == "__main__":
    unittest.main()
