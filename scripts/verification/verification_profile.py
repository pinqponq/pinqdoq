#!/usr/bin/env python3
"""Per-project verification settings for pin-test and the mutation scripts.

  verification_profile.py <worktree>         print the merged profile as JSON
  verification_profile.py <worktree> <key>   print one value (e.g. baseline_branch)

A project may commit `verification-profile.json` at its root to override any key. Every key has a
default equal to the pinqloq task runner's values, so a repo without the file keeps today's behavior:
- `mutation_threshold`: minimum PIT/StrykerJS score on changed lines, in percent.
- `baseline_branch`: branch whose test failures count as pre-existing when the caller names none.
- `dotnet_root`: `DOTNET_ROOT` to export when it is unset and this folder exists.
An unreadable file, an unknown key or a value of the wrong type stops the script, so a typo never
silently falls back to a default.
"""
import json
import sys
from pathlib import Path

PROFILE_FILE_NAME = "verification-profile.json"
DEFAULT_PROFILE = {
    "mutation_threshold": 85,
    "baseline_branch": "develop",
    "dotnet_root": "/opt/homebrew/opt/dotnet/libexec",
}
MINIMUM_THRESHOLD = 0
MAXIMUM_THRESHOLD = 100


def read_profile_file(profile_path):
    try:
        with open(profile_path) as profile_file:
            overrides = json.load(profile_file)
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"{profile_path}: cannot read verification profile: {error}") from error
    if not isinstance(overrides, dict):
        raise SystemExit(f"{profile_path}: verification profile must be a JSON object")
    return overrides


def validate_overrides(profile_path, overrides):
    unknown_keys = sorted(set(overrides) - set(DEFAULT_PROFILE))
    if unknown_keys:
        raise SystemExit(f"{profile_path}: unknown keys {unknown_keys}; known: {sorted(DEFAULT_PROFILE)}")
    threshold = overrides.get("mutation_threshold", DEFAULT_PROFILE["mutation_threshold"])
    is_number = isinstance(threshold, (int, float)) and not isinstance(threshold, bool)
    if not is_number or not MINIMUM_THRESHOLD <= threshold <= MAXIMUM_THRESHOLD:
        raise SystemExit(f"{profile_path}: mutation_threshold must be a number from {MINIMUM_THRESHOLD} to {MAXIMUM_THRESHOLD}")
    for key in ("baseline_branch", "dotnet_root"):
        value = overrides.get(key, DEFAULT_PROFILE[key])
        if not isinstance(value, str) or not value.strip():
            raise SystemExit(f"{profile_path}: {key} must be a non-empty string")


def load_profile(worktree):
    profile_path = Path(worktree) / PROFILE_FILE_NAME
    if not profile_path.exists():
        return dict(DEFAULT_PROFILE)
    overrides = read_profile_file(profile_path)
    validate_overrides(profile_path, overrides)
    return {**DEFAULT_PROFILE, **overrides}


def mutation_threshold(worktree, explicit_threshold):
    """The caller's `--threshold` when given, otherwise the profile's `mutation_threshold`."""
    if explicit_threshold is not None:
        return explicit_threshold
    return float(load_profile(worktree)["mutation_threshold"])


def main():
    arguments = sys.argv[1:]
    if len(arguments) not in (1, 2):
        raise SystemExit(__doc__)
    profile = load_profile(arguments[0])
    if len(arguments) == 1:
        print(json.dumps(profile, indent=2))
        return
    key = arguments[1]
    if key not in profile:
        raise SystemExit(f"unknown key {key!r}; known: {sorted(profile)}")
    print(profile[key])


if __name__ == "__main__":
    main()
