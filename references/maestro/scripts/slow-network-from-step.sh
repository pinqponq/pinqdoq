#!/usr/bin/env bash
# Runs a Maestro command and slows the Android emulator's network once the flow reaches a given step,
# so seeding (e.g. uploads) stays fast while the step under test runs as slowly as on
# a poor mobile network. `adb emu network delay` does not affect the emulator's Wi-Fi traffic, so the
# emulator is routed through slow-proxy.py while the command runs; the proxy setting is restored when
# it ends.
# Usage: ANDROID_SERIAL=emulator-5554 maestro/scripts/slow-network-from-step.sh \
#          <step text in maestro.log> <delay seconds> -- maestro/scripts/run-flow.sh android <flow>
set -euo pipefail

if [[ -z "${ANDROID_SERIAL:-}" ]]; then
  echo "Set ANDROID_SERIAL to the emulator (e.g. emulator-5554) so the proxy is never set on another device." >&2
  exit 1
fi

step_marker="${1:?step text required, e.g. a takeScreenshot name the flow writes right before the step}"
delay_seconds="${2:?delay in seconds required}"
shift 2
[[ "${1:-}" == "--" ]] && shift
[[ $# -gt 0 ]] || { echo "Command to run is required after --" >&2; exit 2; }

readonly PROXY_PORT=8899
readonly MAESTRO_TESTS_DIR="$HOME/.maestro/tests"
script_dir="$(cd "$(dirname "$0")" && pwd)"
trigger_file="$(mktemp -u)"
previous_run="$(ls -t "$MAESTRO_TESTS_DIR" 2>/dev/null | head -1 || true)"

python3 "$script_dir/slow-proxy.py" "$PROXY_PORT" "$trigger_file" "$delay_seconds" 2>/dev/null &
proxy_pid=$!
watcher_pid=""
restore_network() {
  [[ -n "$watcher_pid" ]] && kill "$watcher_pid" 2>/dev/null || true
  adb wait-for-device && adb shell settings put global http_proxy :0 >/dev/null
  kill "$proxy_pid" 2>/dev/null || true
  rm -f "$trigger_file"
  echo "$(date -u +%FT%TZ) network restored"
}
trap restore_network EXIT
# 10.0.2.2 is the host machine as seen from the Android emulator.
adb shell settings put global http_proxy "10.0.2.2:$PROXY_PORT" >/dev/null

(
  current_run="$previous_run"
  while [[ "$current_run" == "$previous_run" ]]; do
    sleep 1
    current_run="$(ls -t "$MAESTRO_TESTS_DIR" 2>/dev/null | head -1 || true)"
  done
  until grep -q "$step_marker" "$MAESTRO_TESTS_DIR/$current_run/maestro.log" 2>/dev/null; do sleep 0.2; done
  touch "$trigger_file"
  echo "$(date -u +%FT%TZ) network slowed: ${delay_seconds}s per upstream chunk"
) &
watcher_pid=$!

"$@"
