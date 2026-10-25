#!/usr/bin/env python3
"""Tell Pinq Center that a task is done, when the task came from a Pinq Center case.

  case_update.py <issue-body-file|-> <task-url> <pull-request-url> <message-file|->

Reads the issue body (a file or stdin), looks for the case marker `<!-- pinq-center-case:<id> -->` and, when
it is there, posts the update to `<api_url>/api/user/runner/cases/<id>/updates` with the service token in
`X-Runner-Token`. Prints one line (never the token). Exit 0 for "sent" and for "skipped" (no marker, or
Pinq Center is not configured on this machine); exit 1 when the server refuses or cannot be reached, so the
runner reports it under İnsan gerekiyor and goes on.

The address and token come from `machine.json` → `pinq_center` (`api_url`, `runner_token`).
"""
import json
import re
import sys
import urllib.error
import urllib.request

import runner_config

CASE_MARKER = re.compile(r"<!-- pinq-center-case:(\d+) -->")
UPDATE_PATH = "/api/user/runner/cases/%s/updates"
TOKEN_HEADER = "X-Runner-Token"
TIMEOUT_SECONDS = 20


def find_case_id(issue_body):
    match = CASE_MARKER.search(issue_body)
    return int(match.group(1)) if match else None


def build_request(settings, case_id, task_url, pull_request_url, message):
    body = {"taskUrl": task_url, "message": message, "pullRequestUrl": pull_request_url}
    return urllib.request.Request(
        settings["api_url"].rstrip("/") + UPDATE_PATH % case_id,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", TOKEN_HEADER: settings["runner_token"]},
        method="POST",
    )


def send_update(settings, case_id, task_url, pull_request_url, message):
    request = build_request(settings, case_id, task_url, pull_request_url, message)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return "sent case %s (HTTP %s)" % (case_id, response.status)
    except urllib.error.HTTPError as error:
        raise RuntimeError("case %s refused (HTTP %s)" % (case_id, error.code))
    except urllib.error.URLError as error:
        raise RuntimeError("case %s not reachable (%s)" % (case_id, error.reason))


def read_source(name):
    return sys.stdin.read() if name == "-" else open(name).read()


def main(arguments):
    if len(arguments) != 4:
        sys.exit(__doc__)
    issue_body, task_url, pull_request_url, message = read_source(arguments[0]), arguments[1], arguments[2], read_source(arguments[3])
    case_id = find_case_id(issue_body)
    if case_id is None:
        print("skipped: no Pinq Center case marker")
        return 0
    settings = runner_config.read_machine_config()["pinq_center"]
    if not settings or not settings.get("api_url") or not settings.get("runner_token"):
        print("skipped: pinq_center is not configured in machine.json")
        return 0
    try:
        print(send_update(settings, case_id, task_url, pull_request_url, message.strip()))
    except RuntimeError as error:
        print("case_update.py: %s" % error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
