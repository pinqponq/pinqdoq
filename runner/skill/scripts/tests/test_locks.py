import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import locks  # noqa: E402
import runner_config  # noqa: E402


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

    def start_claim(self, session, light_only=False, role=None):
        arguments = ([sys.executable, str(LOCKS_SCRIPT), "claim", session] + (["--light-only"] if light_only else [])
                     + (["--role", role] if role else []))
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

        self.assertNotIn(None, claimed_keys)
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

    def test_no_device_runner_skips_device_tasks_and_those_with_an_unknown_need(self):
        self.write_tasks({"org/repo#1": {"status": "selected", "needs_device": True},
                          "org/repo#2": {"status": "selected"},
                          "org/repo#3": {"status": "selected", "needs_device": False, "queue_priority": 9}})

        self.assertEqual("org/repo#3", self.claimed_key(self.start_claim("runner-4-session", role="no-device")))
        self.assertIsNone(self.claimed_key(self.start_claim("runner-4-second-session", role="no-device")))

    def test_no_device_runner_reports_why_a_waiting_task_was_skipped(self):
        self.write_tasks({"org/repo#1": {"status": "selected"}})

        process = self.start_claim("runner-4-session", role="no-device")
        output, _ = process.communicate(timeout=60)

        self.assertEqual(locks.EXIT_NOTHING_CLAIMABLE, process.returncode)
        self.assertIn("skipped org/repo#1: needs a device", output)

    def test_device_runner_takes_a_device_task_before_an_older_task_without_one(self):
        self.write_tasks({"org/repo#1": {"status": "selected", "needs_device": False, "queue_priority": 1},
                          "org/repo#2": {"status": "selected", "needs_device": True, "queue_priority": 5},
                          "org/repo#3": {"status": "selected", "queue_priority": 9}})

        claimed_keys = [self.claimed_key(self.start_claim("runner-%d-session" % number, role="device"))
                        for number in (1, 2, 1)]

        self.assertEqual(["org/repo#2", "org/repo#3", "org/repo#1"], claimed_keys)

    def test_device_runner_takes_a_task_without_a_device_when_no_device_task_waits(self):
        self.write_tasks({"org/repo#1": {"status": "selected", "needs_device": False}})

        process = self.start_claim("runner-1-session", role="device")
        output, error = process.communicate(timeout=60)

        self.assertEqual(0, process.returncode)
        self.assertEqual("org/repo#1", output.splitlines()[0])
        self.assertIn("a device runner took a task without a device", error)

    def test_a_runner_without_a_role_still_takes_any_task(self):
        self.write_tasks({"org/repo#1": {"status": "selected", "needs_device": False}})

        self.assertEqual("org/repo#1", self.claimed_key(self.start_claim("runner-9-session")))


class NeedsDeviceTest(unittest.TestCase):
    def test_a_task_without_the_field_needs_a_device(self):
        self.assertTrue(locks.needs_device({"status": "selected"}))

    def test_only_an_explicit_false_means_no_device(self):
        self.assertFalse(locks.needs_device({"needs_device": False}))
        self.assertTrue(locks.needs_device({"needs_device": True}))
        self.assertTrue(locks.needs_device({"needs_device": None}))


class RoleFromArgumentsTest(unittest.TestCase):
    def test_light_only_flag_means_the_light_role(self):
        self.assertEqual("light", locks.role_from_arguments(["claim", "s", "--light-only"]))

    def test_role_option_is_read(self):
        self.assertEqual("no-device", locks.role_from_arguments(["claim", "s", "--role", "no-device"]))

    def test_no_option_means_no_role(self):
        self.assertIsNone(locks.role_from_arguments(["claim", "s"]))

    def test_unknown_role_stops(self):
        with self.assertRaises(SystemExit):
            locks.role_from_arguments(["claim", "s", "--role", "sleepy"])


class RunnerRolesTest(unittest.TestCase):
    def test_runners_1_and_2_take_device_tasks_on_different_platforms(self):
        roles = runner_config.RUNNER_ROLES

        self.assertEqual("device", roles["runner-1"]["role"])
        self.assertEqual("device", roles["runner-2"]["role"])
        self.assertEqual({"android", "ios"}, {roles["runner-1"]["device_platform"], roles["runner-2"]["device_platform"]})

    def test_runner_3_stays_light_and_runner_4_takes_no_device_tasks(self):
        self.assertEqual("light", runner_config.RUNNER_ROLES["runner-3"]["role"])
        self.assertEqual("no-device", runner_config.RUNNER_ROLES["runner-4"]["role"])

    def test_display_label_shows_the_role_and_keeps_unknown_labels(self):
        self.assertEqual("runner-1 (device, android)", runner_config.runner_display_label("runner-1"))
        self.assertEqual("runner-4 (no-device)", runner_config.runner_display_label("runner-4"))
        self.assertEqual("runner-9", runner_config.runner_display_label("runner-9"))


class FreeDeviceChoiceTest(unittest.TestCase):
    def test_free_platform_tries_the_preferred_device_first(self):
        self.assertEqual([["devices-android"], ["devices-ios"]], locks.free_device_alternatives("android", False))
        self.assertEqual([["devices-ios", "devices-couple"], ["devices-android", "devices-couple"]],
                         locks.free_device_alternatives("ios", True))

    def test_unknown_preferred_platform_stops(self):
        with self.assertRaises(SystemExit):
            locks.free_device_alternatives("web", False)


class FreeDeviceAcquireTest(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.TemporaryDirectory()
        self.addCleanup(self.home.cleanup)
        (Path(self.home.name) / ".claude" / "pinqloq-task-runner").mkdir(parents=True)

    def run_locks(self, *arguments):
        return subprocess.run([sys.executable, str(LOCKS_SCRIPT), *arguments], env={**os.environ, "HOME": self.home.name},
                              capture_output=True, text=True, timeout=60)

    def test_takes_android_when_both_are_free(self):
        result = self.run_locks("devices", "acquire", "session-a", "--platform", "free")

        self.assertEqual("acquired devices-android", result.stdout.strip())

    def test_takes_ios_when_android_is_locked(self):
        self.run_locks("devices", "acquire", "session-a", "--platform", "android")

        result = self.run_locks("devices", "acquire", "session-b", "--platform", "free")

        self.assertEqual("acquired devices-ios", result.stdout.strip())

    def test_prefer_ios_takes_ios_first(self):
        result = self.run_locks("devices", "acquire", "session-a", "--platform", "free", "--prefer", "ios")

        self.assertEqual("acquired devices-ios", result.stdout.strip())

    def test_reports_held_when_both_are_locked(self):
        self.run_locks("devices", "acquire", "session-a", "--platform", "both")

        result = self.run_locks("devices", "acquire", "session-b", "--platform", "free", "--wait-minutes", "0")

        self.assertEqual(locks.EXIT_LOCK_HELD, result.returncode)
        self.assertIn("devices-android", result.stdout)
        self.assertIn("devices-ios", result.stdout)

    def test_option_without_a_value_stops_with_a_message(self):
        with self.assertRaises(SystemExit) as stop:
            locks.role_from_arguments(["claim", "s", "--role"])

        self.assertEqual("--role needs a value", str(stop.exception))


if __name__ == "__main__":
    unittest.main()
