#!/usr/bin/env bash
# Runs a Maestro flow with a test account's sign-in values from a local account file that is never
# committed. The values reach Maestro only as TEST_EMAIL / TEST_OTP and are masked in the output.
# Usage: maestro/scripts/with-test-account.sh <account> <android|ios> <flow> [extra maestro args]
# Account file (TEST_ACCOUNTS_FILE): {"otp": "…", "accounts": {"<account>": {"email": "…"}}}
set -euo pipefail

readonly ACCOUNTS_FILE="${TEST_ACCOUNTS_FILE:-$HOME/.claude/pinqloq-task-runner/test-accounts.json}"

account="${1:?account (e.g. test1) required}"
shift

test_email="$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["accounts"][sys.argv[2]]["email"])' "$ACCOUNTS_FILE" "$account")"
test_otp="$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["otp"])' "$ACCOUNTS_FILE")"

script_dir="$(cd "$(dirname "$0")" && pwd)"
"$script_dir/run-flow.sh" "$1" "$2" -e TEST_EMAIL="$test_email" -e TEST_OTP="$test_otp" "${@:3}" \
  | sed -e "s/$test_email/<test-email>/g" -e "s/$test_otp/<test-otp>/g"
