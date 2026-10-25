#!/usr/bin/env python3
"""Tells whether an app build in a worktree can be reused for a device run instead of building again.

  build_stamp.py record --cwd <worktree> --platform android|ios --artifact <apk or .app path>
  build_stamp.py check  --cwd <worktree> --platform android|ios

`record` runs right after a successful build and stores what the build was made from. `check` exits 0
and prints the artifact path when nothing the build depends on has changed since; otherwise it exits 1
and prints why (build again then).

The source fingerprint covers the worktree and every local build pulled in with `includeBuild(...)`
(e.g. a core worktree used as a composite build): HEAD, the uncommitted diff, and the untracked files
(path, size, modification time; build/ is left out because builds and logs write there). The artifact itself must still exist with the size and modification
time it had when recorded. Stamps live in <worktree>/build/runner-logs/build-stamps.json, so tasks
never share them. Reusing a build never means skipping the install: always install the artifact on the
device after taking the device lock, because another session may have installed its own build there.
"""
import argparse, hashlib, json, os, re, subprocess, sys

STAMP_FILE = os.path.join("build", "runner-logs", "build-stamps.json")
SETTINGS_FILES = ("settings.gradle.kts", "settings.gradle")
INCLUDED_BUILD = re.compile(r"""^\s*includeBuild\(\s*["']([^"']+)["']""", re.MULTILINE)
EXIT_STALE = 1


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("record", "check"))
    parser.add_argument("--cwd", required=True)
    parser.add_argument("--platform", required=True, choices=("android", "ios"))
    parser.add_argument("--artifact")
    arguments = parser.parse_args()
    if arguments.action == "record" and not arguments.artifact:
        parser.error("record needs --artifact")
    return arguments


def run_git(repository, *git_arguments):
    completed = subprocess.run(["git", "-C", repository, *git_arguments], capture_output=True)
    if completed.returncode != 0:
        raise RuntimeError("git %s failed in %s: %s" % (" ".join(git_arguments), repository,
                                                         completed.stderr.decode(errors="replace").strip()))
    return completed.stdout


def fingerprint_repository(repository):
    digest = hashlib.sha256()
    digest.update(run_git(repository, "rev-parse", "HEAD"))
    digest.update(run_git(repository, "diff", "HEAD", "--binary"))
    untracked_paths = run_git(repository, "ls-files", "--others", "--exclude-standard", "-z").split(b"\0")
    for relative_path in sorted(path for path in untracked_paths if path and not path.startswith(b"build/")):
        file_status = os.stat(os.path.join(repository, relative_path.decode()))
        digest.update(b"%s\0%d\0%d\n" % (relative_path, file_status.st_size, file_status.st_mtime_ns))
    return digest.hexdigest()


def find_included_builds(worktree):
    included_builds = []
    for settings_name in SETTINGS_FILES:
        settings_path = os.path.join(worktree, settings_name)
        if not os.path.exists(settings_path):
            continue
        with open(settings_path) as settings_file:
            for included_path in INCLUDED_BUILD.findall(settings_file.read()):
                included_builds.append(os.path.normpath(os.path.join(worktree, os.path.expanduser(included_path))))
    return sorted(set(included_builds))


def fingerprint_sources(worktree):
    fingerprints = {worktree: fingerprint_repository(worktree)}
    for included_build in find_included_builds(worktree):
        fingerprints[included_build] = fingerprint_repository(included_build)
    return fingerprints


def describe_artifact(artifact_path):
    if os.path.isdir(artifact_path):
        newest_mtime = max(os.stat(os.path.join(directory, name)).st_mtime_ns
                           for directory, _, names in os.walk(artifact_path) for name in names + ["."])
        return {"path": artifact_path, "mtime_ns": newest_mtime}
    file_status = os.stat(artifact_path)
    return {"path": artifact_path, "mtime_ns": file_status.st_mtime_ns, "size": file_status.st_size}


def read_stamps(worktree):
    stamp_path = os.path.join(worktree, STAMP_FILE)
    if not os.path.exists(stamp_path):
        return {}
    with open(stamp_path) as stamp_file:
        return json.load(stamp_file)


def write_stamps(worktree, stamps):
    stamp_path = os.path.join(worktree, STAMP_FILE)
    os.makedirs(os.path.dirname(stamp_path), exist_ok=True)
    temporary_path = stamp_path + ".tmp"
    with open(temporary_path, "w") as stamp_file:
        json.dump(stamps, stamp_file, indent=1)
    os.replace(temporary_path, stamp_path)


def record_build(worktree, platform, artifact_path):
    if not os.path.exists(artifact_path):
        raise RuntimeError("artifact %s does not exist" % artifact_path)
    stamps = read_stamps(worktree)
    stamps[platform] = {"sources": fingerprint_sources(worktree), "artifact": describe_artifact(artifact_path)}
    write_stamps(worktree, stamps)
    print("recorded %s build: %s" % (platform, artifact_path))


def find_stale_reason(worktree, platform):
    stamp = read_stamps(worktree).get(platform)
    if not stamp:
        return "no recorded %s build" % platform, None
    artifact_path = stamp["artifact"]["path"]
    if not os.path.exists(artifact_path):
        return "artifact %s is gone" % artifact_path, None
    if describe_artifact(artifact_path) != stamp["artifact"]:
        return "artifact %s changed after it was recorded" % artifact_path, None
    current_sources = fingerprint_sources(worktree)
    if set(current_sources) != set(stamp["sources"]):
        return "the set of included builds changed", None
    for repository, recorded_fingerprint in stamp["sources"].items():
        if current_sources[repository] != recorded_fingerprint:
            return "sources changed in %s" % repository, None
    return None, artifact_path


def main():
    arguments = parse_arguments()
    worktree = os.path.abspath(arguments.cwd)
    if arguments.action == "record":
        record_build(worktree, arguments.platform, os.path.abspath(arguments.artifact))
        return
    stale_reason, artifact_path = find_stale_reason(worktree, arguments.platform)
    if stale_reason:
        print("STALE: %s, build again" % stale_reason)
        sys.exit(EXIT_STALE)
    print("REUSE: %s (install it again before running flows)" % artifact_path)


if __name__ == "__main__":
    main()
