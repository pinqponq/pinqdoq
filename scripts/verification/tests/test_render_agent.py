import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SCRIPTS_DIR.parents[1]
PIN_TEST_AGENT = REPOSITORY_ROOT / "runner" / "agents" / "pin-test.md"
sys.path.insert(0, str(SCRIPTS_DIR))

import render_agent  # noqa: E402

TEMPLATE_TEXT = render_agent.TEMPLATE_FILE.read_text()


def render_generic(scripts_dir="/opt/verification", name="verification-runner"):
    return render_agent.render(TEMPLATE_TEXT, "generic", {"name": name, "scripts_dir": scripts_dir})


class PinqloqProfileTest(unittest.TestCase):
    def test_rendered_agent_matches_the_committed_pin_test(self):
        rendered = render_agent.render(TEMPLATE_TEXT, "pinqloq", render_agent.PINQLOQ_VALUES)
        self.assertEqual(
            rendered, PIN_TEST_AGENT.read_text(),
            "runner/agents/pin-test.md differs from the template; edit scripts/verification/agent-template.md and run "
            "`python3 scripts/verification/render_agent.py pinqloq --out runner/agents/pin-test.md`",
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
