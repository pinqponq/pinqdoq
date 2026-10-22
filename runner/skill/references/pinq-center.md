# Pinq Center cases

Pinq Center opens a task for a support case and puts the marker `<!-- pinq-center-case:<id> -->` in the issue body. When the runner finishes such a task, Pinq Center is told what was done, so the case moves to "task done" and its history shows the work.

## When
After the PR is open and the card is in Waiting for human review (implementation.md step 11), and after a finished change request. Read the issue body once (`gh issue view -R <repo> <n> --json body -q .body`). No marker → nothing to do; the script skips quietly.

## How
```
gh issue view -R <repo> <n> --json body -q .body | python3 scripts/case_update.py - <issue url> <pr url> <message file>
```
- The message is one or two Turkish sentences for the case history: what was done and where (for example "Görev tamamlandı, PR hazır: <pr url>"). No tokens, no personal data, at most 2,000 characters.
- Pinq Center accepts the update only for a case in "task opened" state, and only when the task URL is the one stored on the case. A refusal (exit 1) is not retried; list it under İnsan gerekiyor in the run report and go on.
- The service token is the `runner_token` in `machine.json` → `pinq_center` (with `api_url`). The owner puts it there. Never print it, never write it into a repo, PR, comment, report or log; `runner_config.py` prints it as `<hidden>`. Without that key, the script skips quietly.

## Dry run against a fake endpoint
`scripts/tests/test_case_update.py` starts a local HTTP server that plays the endpoint and runs the script against it. It checks the request path, the `X-Runner-Token` header and the body, the quiet skips (no marker, not configured), and that a refusal or an unreachable server gives exit 1 without the token in the output:
```
python3 -m unittest scripts/tests/test_case_update.py
```
By hand: point `api_url` at any local server that answers POST `/api/user/runner/cases/<id>/updates` with 204.
