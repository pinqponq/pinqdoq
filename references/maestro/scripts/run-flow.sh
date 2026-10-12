#!/usr/bin/env bash
# Runs Maestro flows against the booted Android emulator or iOS simulator with the right app id.
# Usage: maestro/scripts/run-flow.sh <android|ios> <flow file or directory> [extra maestro test args]
# Run it from the app's root folder; results go to build/maestro/<platform>/ there.
# App ids come from maestro/app-ids.env; ANDROID_APP_ID / IOS_APP_ID set in the environment win.
set -euo pipefail

script_dir="$(cd "$(dirname "$0")" && pwd)"
app_ids_file="$(dirname "$script_dir")/app-ids.env"
environment_android_app_id="${ANDROID_APP_ID:-}"
environment_ios_app_id="${IOS_APP_ID:-}"
if [[ -f "$app_ids_file" ]]; then
  # shellcheck source=/dev/null
  source "$app_ids_file"
fi
ANDROID_APP_ID="${environment_android_app_id:-${ANDROID_APP_ID:-}}"
IOS_APP_ID="${environment_ios_app_id:-${IOS_APP_ID:-}}"

platform="${1:?platform (android|ios) required}"
flow_path="${2:?flow file or directory required}"
shift 2

case "$platform" in
  android)
    app_id="${ANDROID_APP_ID:?set ANDROID_APP_ID (e.g. in maestro/app-ids.env)}"
    # With several devices attached (e.g. a personal phone on USB) never guess: require ANDROID_SERIAL.
    connected_devices="$(adb devices | awk 'NR > 1 && $2 == "device" { print $1 }')"
    if [[ -n "${ANDROID_SERIAL:-}" ]]; then
      device_id="$ANDROID_SERIAL"
    elif [[ "$(printf '%s\n' "$connected_devices" | grep -c .)" -gt 1 ]]; then
      echo "Several Android devices are connected; set ANDROID_SERIAL (e.g. emulator-5554)." >&2
      exit 1
    else
      device_id="$connected_devices"
    fi
    # A loaded emulator snapshot keeps the clock of the moment it was saved; anything the app sorts
    # by time (e.g. freshly seeded media) would land between older items instead of on top.
    if [[ -n "$device_id" ]]; then
      adb -s "$device_id" shell cmd alarm set-time "$(($(date +%s) * 1000))" >/dev/null
    fi
    ;;
  ios)
    app_id="${IOS_APP_ID:?set IOS_APP_ID (e.g. in maestro/app-ids.env)}"
    # Device names can contain parentheses ("iPhone SE (3rd generation)"), so match the UDID itself.
    device_id="$(xcrun simctl list devices booted | grep -Eo '[0-9A-F]{8}(-[0-9A-F]{4}){3}-[0-9A-F]{12}' | head -1 || true)"
    ;;
  *)
    echo "Unknown platform: $platform (expected android or ios)" >&2
    exit 2
    ;;
esac

if [[ -z "$device_id" ]]; then
  echo "No booted $platform device found." >&2
  exit 1
fi

output_dir="build/maestro/$platform"
mkdir -p "$output_dir"

MAESTRO_CLI_NO_ANALYTICS=1 maestro --device "$device_id" test \
  --env APP_ID="$app_id" \
  --test-output-dir "$output_dir" \
  --format junit --output "$output_dir/report.xml" \
  "$@" "$flow_path"
