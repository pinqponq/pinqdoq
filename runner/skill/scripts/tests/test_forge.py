import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import forge  # noqa: E402

GITHUB_REPOSITORY = {"forge": "github", "host": "github.com", "path": "pinqponq/rindle-cmp"}
GITLAB_REPOSITORY = {"forge": "gitlab", "host": "gitlab.example.com", "path": "group/sample-app"}


def git(*arguments):
    subprocess.run(["git", *arguments], check=True, capture_output=True)


class RemoteUrlTest(unittest.TestCase):
    def test_https_ssh_and_scp_urls(self):
        cases = {
            "https://gitlab.example.com/group/sample-app.git": ("gitlab.example.com", "group/sample-app"),
            "https://user@gitlab.example.com/group/subgroup/team/app": ("gitlab.example.com", "group/subgroup/team/app"),
            "ssh://git@gitlab.example.com:2222/group/app.git": ("gitlab.example.com", "group/app"),
            "git@github.com:pinqponq/rindle-cmp.git": ("github.com", "pinqponq/rindle-cmp"),
        }
        for remote_url, expected in cases.items():
            with self.subTest(remote_url=remote_url):
                self.assertEqual(expected, forge.parse_remote_url(remote_url))

    def test_unknown_host_stops(self):
        with mock.patch.object(forge, "run_command", return_value="https://bitbucket.org/a/b.git\n"):
            with self.assertRaises(forge.ForgeError):
                forge.describe_repository("/repo", "gitlab.example.com")

    def test_host_picks_the_forge(self):
        with mock.patch.object(forge, "run_command", return_value="https://gitlab.example.com/group/sample-app.git\n"):
            self.assertEqual(GITLAB_REPOSITORY, forge.describe_repository("/repo", "gitlab.example.com"))
        with mock.patch.object(forge, "run_command", return_value="https://github.com/pinqponq/rindle-cmp.git\n"):
            self.assertEqual(GITHUB_REPOSITORY, forge.describe_repository("/repo", None))


class PullRequestBaseTest(unittest.TestCase):
    """Builds an origin repository and a clone, and reads the base with git ls-remote as the runner does."""

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        self.origin = root / "origin"
        self.clone = root / "clone"
        git("init", "-q", "-b", "main", str(self.origin))
        git("-C", str(self.origin), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "first")
        git("clone", "-q", str(self.origin), str(self.clone))

    def test_default_branch_without_develop(self):
        self.assertEqual("main", forge.pull_request_base(self.clone))

    def test_develop_when_origin_has_it(self):
        git("-C", str(self.origin), "branch", "develop")
        self.assertEqual("develop", forge.pull_request_base(self.clone))


class RecordingCommands:
    def __init__(self, output=""):
        self.output = output
        self.commands = []
        self.environments = []

    def __call__(self, command, environment=None):
        self.commands.append(command)
        self.environments.append(environment)
        return self.output


class RequestCommandsTest(unittest.TestCase):
    def record(self, output, action):
        recorder = RecordingCommands(output)
        with mock.patch.object(forge, "run_command", recorder):
            result = action()
        return recorder, result

    def test_github_opens_a_ready_pull_request_with_gh(self):
        recorder, url = self.record("https://github.com/pinqponq/rindle-cmp/pull/12\n", lambda: forge.open_request(
            GITHUB_REPOSITORY, "task/5-x", "develop", "Title", "/tmp/body.md"))
        self.assertEqual("https://github.com/pinqponq/rindle-cmp/pull/12", url)
        self.assertEqual(["gh", "pr", "create", "-R", "pinqponq/rindle-cmp", "--head", "task/5-x", "--base", "develop",
                          "--title", "Title", "--body-file", "/tmp/body.md"], recorder.commands[0])

    def test_gitlab_opens_a_ready_merge_request_with_glab_on_the_machines_host(self):
        output = "Creating merge request for task/5-x into develop in group/sample-app\n\nhttps://gitlab.example.com/group/sample-app/-/merge_requests/7\n"
        recorder, url = self.record(output, lambda: forge.open_request(
            GITLAB_REPOSITORY, "task/5-x", "develop", "Title", "/tmp/body.md"))
        self.assertEqual("https://gitlab.example.com/group/sample-app/-/merge_requests/7", url)
        command = recorder.commands[0]
        self.assertEqual(["glab", "mr", "create", "-R", "group/sample-app"], command[:5])
        self.assertIn("--yes", command)
        self.assertNotIn("--draft", command)
        self.assertEqual("gitlab.example.com", recorder.environments[0]["GITLAB_HOST"])

    def test_gitlab_update_ready_and_find(self):
        recorder, _ = self.record("", lambda: forge.update_request(GITLAB_REPOSITORY, 7, body_file="/tmp/b.md", base="develop"))
        self.assertEqual(["glab", "mr", "update", "7", "-R", "group/sample-app", "--description-file", "/tmp/b.md",
                          "--target-branch", "develop"], recorder.commands[0])
        recorder, _ = self.record("", lambda: forge.mark_ready(GITLAB_REPOSITORY, 7))
        self.assertEqual("--ready", recorder.commands[0][-1])
        _, found = self.record('[{"iid": 7, "web_url": "https://gitlab.example.com/x/-/merge_requests/7"}]',
                               lambda: forge.find_open_request(GITLAB_REPOSITORY, "task/5-x"))
        self.assertEqual({"number": 7, "url": "https://gitlab.example.com/x/-/merge_requests/7"}, found)
        _, found = self.record("[]", lambda: forge.find_open_request(GITLAB_REPOSITORY, "task/5-x"))
        self.assertIsNone(found)

    def test_github_update_uses_gh_pr_edit(self):
        recorder, _ = self.record("", lambda: forge.update_request(GITHUB_REPOSITORY, 12, title="New"))
        self.assertEqual(["gh", "pr", "edit", "12", "-R", "pinqponq/rindle-cmp", "--title", "New"], recorder.commands[0])

    def test_update_without_changes_stops(self):
        with self.assertRaises(forge.ForgeError):
            forge.update_request(GITLAB_REPOSITORY, 7)

    def test_gitlab_upload_posts_the_file_to_the_project(self):
        recorder, address = self.record('{"url": "/uploads/abc/proof.png", "markdown": "![proof](/uploads/abc/proof.png)"}',
                                        lambda: forge.upload_file(GITLAB_REPOSITORY, "/tmp/proof.png"))
        self.assertEqual("/uploads/abc/proof.png", address)
        self.assertIn("projects/group%2Fsample-app/uploads", recorder.commands[0])
        self.assertIn("file=@/tmp/proof.png", recorder.commands[0])

    def test_github_upload_stops(self):
        with self.assertRaises(forge.ForgeError):
            forge.upload_file(GITHUB_REPOSITORY, "/tmp/proof.png")

    def test_there_is_no_merge_command(self):
        self.assertFalse(any("merge" in name for name in dir(forge) if callable(getattr(forge, name))
                             and name not in {"run_command"}))


if __name__ == "__main__":
    unittest.main()
