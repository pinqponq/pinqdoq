import json
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import case_update  # noqa: E402

TASK_URL = "https://github.com/pinqponq/pinqdoq/issues/79"
PULL_REQUEST_URL = "https://github.com/pinqponq/pinqdoq/pull/80"
FAKE_TOKEN = "fake-token-for-tests-0123456789abcdef"
ISSUE_BODY = "Body\n<!-- pinq-center-case:42 -->\n"


class FakeEndpoint(BaseHTTPRequestHandler):
    received = []
    status = 204

    def do_POST(self):
        length = int(self.headers["Content-Length"])
        FakeEndpoint.received.append((self.path, self.headers.get(case_update.TOKEN_HEADER), json.loads(self.rfile.read(length))))
        self.send_response(FakeEndpoint.status)
        self.end_headers()

    def log_message(self, *arguments):
        pass


class CaseUpdateTest(unittest.TestCase):
    def setUp(self):
        FakeEndpoint.received = []
        FakeEndpoint.status = 204
        self.server = HTTPServer(("127.0.0.1", 0), FakeEndpoint)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.settings = {"api_url": "http://127.0.0.1:%s/" % self.server.server_port, "runner_token": FAKE_TOKEN}
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def run_main(self, issue_body, settings):
        machine = {"pinq_center": settings}
        with mock.patch.object(case_update.runner_config, "read_machine_config", return_value=machine), \
                mock.patch.object(case_update, "read_source", side_effect=lambda name: {"body": issue_body, "message": " Done \n"}[name]):
            return case_update.main(["body", TASK_URL, PULL_REQUEST_URL, "message"])

    def test_finds_the_case_id_in_the_marker(self):
        self.assertEqual(42, case_update.find_case_id(ISSUE_BODY))

    def test_has_no_case_id_without_the_marker(self):
        self.assertIsNone(case_update.find_case_id("Closes #1 <!-- other:42 -->"))

    def test_posts_the_update_with_the_token_header(self):
        self.assertEqual(0, self.run_main(ISSUE_BODY, self.settings))

        self.assertEqual([("/api/user/runner/cases/42/updates", FAKE_TOKEN,
                           {"taskUrl": TASK_URL, "message": "Done", "pullRequestUrl": PULL_REQUEST_URL})], FakeEndpoint.received)

    def test_skips_quietly_without_the_marker(self):
        self.assertEqual(0, self.run_main("No marker", self.settings))
        self.assertEqual([], FakeEndpoint.received)

    def test_skips_quietly_when_pinq_center_is_not_configured(self):
        self.assertEqual(0, self.run_main(ISSUE_BODY, None))
        self.assertEqual(0, self.run_main(ISSUE_BODY, {"api_url": "http://127.0.0.1:1"}))
        self.assertEqual([], FakeEndpoint.received)

    def test_fails_when_the_server_refuses(self):
        FakeEndpoint.status = 401

        with mock.patch("sys.stderr") as stderr:
            self.assertEqual(1, self.run_main(ISSUE_BODY, self.settings))

        self.assertNotIn(FAKE_TOKEN, "".join(call.args[0] for call in stderr.write.call_args_list))

    def test_fails_when_the_server_is_not_reachable(self):
        self.server.shutdown()
        self.server.server_close()

        self.assertEqual(1, self.run_main(ISSUE_BODY, self.settings))


if __name__ == "__main__":
    unittest.main()
