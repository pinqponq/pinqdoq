import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))

import verification_profile  # noqa: E402


class LoadProfileTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.worktree = Path(self.temporary_directory.name)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def write_profile(self, content):
        (self.worktree / verification_profile.PROFILE_FILE_NAME).write_text(content)

    def test_repo_without_profile_keeps_the_runner_values(self):
        self.assertEqual(
            verification_profile.load_profile(self.worktree),
            {"mutation_threshold": 85, "baseline_branch": "develop", "dotnet_root": "/opt/homebrew/opt/dotnet/libexec"},
        )

    def test_profile_overrides_only_the_keys_it_names(self):
        self.write_profile(json.dumps({"baseline_branch": "main", "mutation_threshold": 70}))
        profile = verification_profile.load_profile(self.worktree)
        self.assertEqual(profile["baseline_branch"], "main")
        self.assertEqual(profile["mutation_threshold"], 70)
        self.assertEqual(profile["dotnet_root"], verification_profile.DEFAULT_PROFILE["dotnet_root"])

    def test_unknown_key_stops(self):
        self.write_profile(json.dumps({"mutation_treshold": 70}))
        with self.assertRaises(SystemExit) as raised:
            verification_profile.load_profile(self.worktree)
        self.assertIn("mutation_treshold", str(raised.exception))

    def test_invalid_json_stops(self):
        self.write_profile("{not json")
        with self.assertRaises(SystemExit):
            verification_profile.load_profile(self.worktree)

    def test_non_object_profile_stops(self):
        self.write_profile("[]")
        with self.assertRaises(SystemExit):
            verification_profile.load_profile(self.worktree)

    def test_threshold_outside_percent_range_stops(self):
        for threshold in (-1, 101, "85", True):
            with self.subTest(threshold=threshold):
                self.write_profile(json.dumps({"mutation_threshold": threshold}))
                with self.assertRaises(SystemExit):
                    verification_profile.load_profile(self.worktree)

    def test_threshold_boundaries_are_accepted(self):
        for threshold in (0, 100, 92.5):
            with self.subTest(threshold=threshold):
                self.write_profile(json.dumps({"mutation_threshold": threshold}))
                self.assertEqual(verification_profile.load_profile(self.worktree)["mutation_threshold"], threshold)

    def test_empty_baseline_branch_stops(self):
        for value in ("", "  ", 3):
            with self.subTest(value=value):
                self.write_profile(json.dumps({"baseline_branch": value}))
                with self.assertRaises(SystemExit):
                    verification_profile.load_profile(self.worktree)

    def test_empty_dotnet_root_stops(self):
        self.write_profile(json.dumps({"dotnet_root": ""}))
        with self.assertRaises(SystemExit):
            verification_profile.load_profile(self.worktree)


    def test_explicit_threshold_wins_over_the_profile(self):
        self.write_profile(json.dumps({"mutation_threshold": 70}))
        self.assertEqual(verification_profile.mutation_threshold(self.worktree, 90.0), 90.0)

    def test_threshold_comes_from_the_profile_when_not_given(self):
        self.write_profile(json.dumps({"mutation_threshold": 70}))
        self.assertEqual(verification_profile.mutation_threshold(self.worktree, None), 70.0)

    def test_threshold_defaults_to_the_runner_value_as_a_float(self):
        threshold = verification_profile.mutation_threshold(self.worktree, None)
        self.assertEqual(threshold, 85.0)
        self.assertIsInstance(threshold, float)


class CommandLineTest(unittest.TestCase):
    def run_profile_script(self, *arguments):
        return subprocess.run([sys.executable, str(SCRIPTS_DIR / "verification_profile.py"), *arguments],
                              capture_output=True, text=True)

    def test_prints_one_value(self):
        with tempfile.TemporaryDirectory() as worktree:
            result = self.run_profile_script(worktree, "baseline_branch")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "develop")

    def test_prints_the_whole_profile(self):
        with tempfile.TemporaryDirectory() as worktree:
            result = self.run_profile_script(worktree)
        self.assertEqual(json.loads(result.stdout), verification_profile.DEFAULT_PROFILE)

    def test_unknown_key_fails(self):
        with tempfile.TemporaryDirectory() as worktree:
            result = self.run_profile_script(worktree, "nope")
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
