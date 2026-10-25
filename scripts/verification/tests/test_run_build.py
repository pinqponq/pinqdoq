import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import run_build  # noqa: E402


class HeartbeatCommandTest(unittest.TestCase):
    def test_lock_alone_touches_the_runner_lock(self):
        self.assertEqual(
            run_build.heartbeat_command(None, "rindle-cmp#402"),
            [sys.executable, run_build.LOCKS_SCRIPT, "touch", "rindle-cmp#402"],
        )

    def test_heartbeat_is_split_like_a_shell_command(self):
        self.assertEqual(
            run_build.heartbeat_command("touch 'my lock file'", None),
            ["touch", "my lock file"],
        )

    def test_heartbeat_wins_over_lock(self):
        self.assertEqual(run_build.heartbeat_command("true", "rindle-cmp#402"), ["true"])

    def test_without_heartbeat_or_lock_nothing_runs(self):
        self.assertIsNone(run_build.heartbeat_command(None, None))


class RunCommandTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = self.temporary_directory.name
        self.log_path = os.path.join(self.directory, "build.log")
        self.heartbeat_log = os.path.join(self.directory, "heartbeats")

    def tearDown(self):
        self.temporary_directory.cleanup()

    def heartbeat_count(self):
        if not os.path.exists(self.heartbeat_log):
            return 0
        with open(self.heartbeat_log) as heartbeat_file:
            return len(heartbeat_file.readlines())

    def test_heartbeat_runs_before_and_after_the_command(self):
        heartbeat = [sys.executable, "-c", f"open({self.heartbeat_log!r}, 'a').write('beat\\n')"]
        exit_code = run_build.run_command([sys.executable, "-c", "print('built')"], self.directory, self.log_path, heartbeat)
        self.assertEqual(exit_code, 0)
        self.assertEqual(self.heartbeat_count(), 2)

    def test_without_heartbeat_only_the_command_runs(self):
        with mock.patch.object(run_build, "send_heartbeat") as send_heartbeat:
            exit_code = run_build.run_command([sys.executable, "-c", "raise SystemExit(3)"], self.directory, self.log_path, None)
        self.assertEqual(exit_code, 3)
        send_heartbeat.assert_not_called()


class SendHeartbeatTest(unittest.TestCase):
    def test_failed_heartbeat_is_reported_on_stderr(self):
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors):
            run_build.send_heartbeat([sys.executable, "-c", "print('not held: task'); raise SystemExit(1)"])
        self.assertIn("HEARTBEAT FAILED", errors.getvalue())
        self.assertIn("not held: task", errors.getvalue())

    def test_missing_heartbeat_program_is_reported_on_stderr(self):
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors):
            run_build.send_heartbeat(["/nonexistent/heartbeat-program"])
        self.assertIn("HEARTBEAT FAILED", errors.getvalue())

    def test_successful_heartbeat_prints_nothing(self):
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors):
            run_build.send_heartbeat([sys.executable, "-c", "print('touched')"])
        self.assertEqual(errors.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
