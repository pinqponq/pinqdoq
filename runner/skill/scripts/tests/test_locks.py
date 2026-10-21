import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import locks  # noqa: E402


class RequestedDeviceLockNamesTest(unittest.TestCase):
    def test_web_platform_requests_only_the_web_lock(self):
        self.assertEqual(locks.requested_device_lock_names("web", False), ["devices-web"])

    def test_both_platforms_keep_meaning_android_and_ios(self):
        self.assertEqual(
            locks.requested_device_lock_names("both", True),
            ["devices-android", "devices-ios", "devices-couple"],
        )

    def test_unknown_platform_stops(self):
        with self.assertRaises(SystemExit):
            locks.requested_device_lock_names("desktop", False)

    def test_release_without_platform_covers_the_web_lock(self):
        self.assertIn("devices-web", locks.ALL_DEVICE_LOCK_NAMES)


LOCKS_SCRIPT = Path(locks.__file__).resolve()


class ClaimWithFourRunnersTest(unittest.TestCase):
    """Runs locks.py as the runners do, against a state folder under a temporary home."""

    def setUp(self):
        self.home = tempfile.TemporaryDirectory()
        self.addCleanup(self.home.cleanup)
        self.state_dir = Path(self.home.name) / ".claude" / "pinqloq-task-runner"
        self.state_dir.mkdir(parents=True)

    def write_tasks(self, tasks):
        (self.state_dir / "state.json").write_text(json.dumps({"tasks": tasks}))

    def start_claim(self, session, light_only=False):
        arguments = [sys.executable, str(LOCKS_SCRIPT), "claim", session] + (["--light-only"] if light_only else [])
        return subprocess.Popen(arguments, env={**os.environ, "HOME": self.home.name},
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def claimed_key(self, process):
        output, _ = process.communicate(timeout=60)
        return output.splitlines()[0] if process.returncode == 0 else None

    def test_four_sessions_started_together_claim_each_task_once(self):
        self.write_tasks({"org/repo#%d" % number: {"status": "selected", "queue_priority": number,
                                                    "weight": "light"} for number in range(1, 5)})

        processes = [self.start_claim("runner-%d-session" % number, light_only=number == 3) for number in range(1, 5)]
        claimed_keys = [self.claimed_key(process) for process in processes]

        self.assertEqual(["org/repo#1", "org/repo#2", "org/repo#3", "org/repo#4"], sorted(claimed_keys))

    def test_a_fifth_session_finds_nothing_once_four_tasks_are_claimed(self):
        self.write_tasks({"org/repo#%d" % number: {"status": "selected"} for number in range(1, 5)})
        for number in (1, 2, 4):
            self.claimed_key(self.start_claim("runner-%d-session" % number))
        self.claimed_key(self.start_claim("runner-2-second-session"))

        self.assertIsNone(self.claimed_key(self.start_claim("runner-4-second-session")))

    def test_runner_4_claims_a_heavy_task_that_runner_3_skips(self):
        self.write_tasks({"org/repo#1": {"status": "selected"}})

        self.assertIsNone(self.claimed_key(self.start_claim("runner-3-session", light_only=True)))
        self.assertEqual("org/repo#1", self.claimed_key(self.start_claim("runner-4-session")))


if __name__ == "__main__":
    unittest.main()
