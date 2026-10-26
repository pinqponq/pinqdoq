import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
QUEUE_SCRIPT = SCRIPTS_DIR / "chat_queue.py"
LOCKS_SCRIPT = SCRIPTS_DIR / "locks.py"


class QueueFromChatTest(unittest.TestCase):
    """Runs chat_queue.py and locks.py as the runner does, against a state folder under a temporary home."""

    def setUp(self):
        self.home = tempfile.TemporaryDirectory()
        self.addCleanup(self.home.cleanup)
        home_dir = Path(self.home.name)
        self.state_dir = home_dir / ".claude" / "pinqloq-task-runner"
        self.state_dir.mkdir(parents=True)
        workspace_dir = home_dir / "workspace"
        subprocess.run(["git", "init", "-q", str(workspace_dir / "sample-app")], check=True)
        (workspace_dir / "not-a-repo").mkdir()
        (self.state_dir / "machine.json").write_text(json.dumps({
            "role": "queue-only", "workspace_dir": str(workspace_dir), "forge": "gitlab",
            "gitlab_host": "gitlab.example.com", "pinqponq_steps": False}))
        self.environment = {**os.environ, "HOME": self.home.name}

    def run_script(self, script, arguments, description=""):
        return subprocess.run([sys.executable, str(script), *arguments], input=description,
                              capture_output=True, text=True, env=self.environment)

    def add(self, *arguments, description="Show the guest's name on the check-in screen."):
        return self.run_script(QUEUE_SCRIPT, ["add", "--repo", "sample-app", "--title", "Guest name", *arguments],
                               description)

    def read_tasks(self):
        return json.loads((self.state_dir / "state.json").read_text())["tasks"]

    def test_task_is_stored_as_selected_with_its_description(self):
        result = self.add("--needs-device", "true")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual("local/sample-app#1", result.stdout.strip())
        task = self.read_tasks()["local/sample-app#1"]
        self.assertEqual(("selected", "chat", "Show the guest's name on the check-in screen.", True),
                         (task["status"], task["source"], task["description"], task["needs_device"]))
        self.assertTrue(task["repo_dir"].endswith("/workspace/sample-app"))

    def test_numbers_count_up_and_skip_archived_ones(self):
        (self.state_dir / "state-archive.json").write_text(json.dumps({"tasks": {"local/other#4": {"status": "done"}}}))
        self.add()
        self.assertEqual("local/sample-app#6", self.add().stdout.strip())

    def test_claim_picks_the_queued_task(self):
        self.add()
        claim = self.run_script(LOCKS_SCRIPT, ["claim", "manual-20261026120000"])
        self.assertEqual(claim.returncode, 0, claim.stderr)
        self.assertIn("local/sample-app#1", claim.stdout)

    def test_wrong_input_stores_nothing(self):
        cases = [["add", "--repo", "not-a-repo", "--title", "x"],
                 ["add", "--repo", "../sample-app", "--title", "x"],
                 ["add", "--repo", "sample-app", "--title", " "]]
        for arguments in cases:
            with self.subTest(arguments=arguments):
                self.assertNotEqual(0, self.run_script(QUEUE_SCRIPT, arguments, "description").returncode)
        self.assertNotEqual(0, self.add(description="  ").returncode)
        self.assertFalse((self.state_dir / "state.json").exists())


if __name__ == "__main__":
    unittest.main()
