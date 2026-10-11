#!/usr/bin/env python3
"""Housekeeping cleanup for the pinqloq task runner (run at the end of the housekeeping steps).

  cleanup.py [--dry-run]

1. Archives finished tasks (`state_tx.py archive`: merged/skipped/declined/done, untouched for 3 days).
2. For archived tasks: removes their local media folder (the evidence is already on the repo's
   `task-runner-media` branch).
3. Removes folders in the worktrees directory that no active task or lock refers to and that were
   not touched for two days: worktrees of finished tasks, helper worktrees (`-base`, `-develop`,
   `-media`, baselines) and non-git output folders (Stryker). A git worktree goes only when its changes are just regenerable build files (CocoaPods
   output, the local Info.plist/pbxproj edits pod install makes, the never-committed composite
   build, the pinq-doq submodule pointer) and every commit is on a remote, or the task is merged.
4. Keeps only the newest state.json backups and deletes loose build logs older than a week from
   the worktrees directory.
"""
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import locks  # noqa: E402
import runner_config  # noqa: E402
import state_tx  # noqa: E402

MEDIA_DIR = state_tx.STATE_DIR / "media"
WORKTREES_DIR = runner_config.read_machine_config()["worktrees_dir"]
KEPT_BACKUP_COUNT = 3
LOOSE_LOG_MAX_AGE_SECONDS = 7 * 24 * 60 * 60
ORPHAN_MIN_AGE_SECONDS = 2 * 24 * 60 * 60
REGENERABLE_PATH_PATTERNS = [r"(^|/)Pods/", r"(^|/)Podfile\.lock$", r"\.xcworkspace/", r"(^|/)Info\.plist$",
                             r"\.pbxproj$", r"^settings\.gradle\.kts$", r"^\.pinq-doq$", r"^maestro/"]
TASK_NUMBER_PATTERN = re.compile(r"(?:^|-)(?:org)?(\d+)(?=-|$)")


def media_folder_for(task_key):
    repository_and_number = task_key.split("/", 1)[1]
    return MEDIA_DIR / repository_and_number.replace("#", "-")


def clean_archived_tasks(dry_run):
    report = []
    with state_tx.locked_state():
        archived_tasks = state_tx.read_archive()["tasks"]
    for task_key, task in sorted(archived_tasks.items()):
        media_folder = media_folder_for(task_key)
        if media_folder.exists():
            if not dry_run:
                shutil.rmtree(media_folder)
            report.append("%s media %s" % ("would remove" if dry_run else "removed", media_folder.name))
    return report


def list_unsaved_changes(worktree_path):
    status = subprocess.run(["git", "-C", str(worktree_path), "status", "--porcelain"], capture_output=True, text=True)
    if status.returncode != 0:
        raise RuntimeError("git status failed in %s: %s" % (worktree_path, status.stderr.strip()))
    changed_paths = [line[3:].strip().strip('"') for line in status.stdout.splitlines() if line.strip()]
    return [path for path in changed_paths
            if not any(re.search(pattern, path) for pattern in REGENERABLE_PATH_PATTERNS)]


def count_commits_missing_from_remotes(worktree_path):
    commits = subprocess.run(["git", "-C", str(worktree_path), "rev-list", "--count", "HEAD", "--not", "--remotes"],
                             capture_output=True, text=True)
    if commits.returncode != 0:
        raise RuntimeError("git rev-list failed in %s: %s" % (worktree_path, commits.stderr.strip()))
    return int(commits.stdout.strip())


def last_touched_at(folder):
    git_index = folder / ".git"
    candidates = [folder, git_index] + [child for child in folder.iterdir()][:50]
    return max(candidate.stat().st_mtime for candidate in candidates if candidate.exists())


def collect_protected_references():
    """Folder paths and task numbers that a not-finished task or a held lock still refers to."""
    with state_tx.locked_state():
        tasks = state_tx.read_state().get("tasks", {})
    active_tasks = {key: task for key, task in tasks.items() if task.get("status") not in state_tx.ARCHIVABLE_STATUSES}
    lock_text = " ".join(lock_file.read_text(errors="ignore") for lock_file in locks.LOCK_DIR.glob("*.lock"))
    return {
        "text": json.dumps(active_tasks, ensure_ascii=False) + " " + lock_text,
        "numbers": {key.rsplit("#", 1)[1] for key in active_tasks},
    }


def find_merged_numbers():
    return {key.rsplit("#", 1)[1] for key, status in state_tx.read_task_statuses().items() if status == "merged"}


def remove_orphan_folder(folder, references, merged_numbers, dry_run):
    folder_numbers = set(TASK_NUMBER_PATTERN.findall(folder.name))
    if str(folder) in references["text"] or folder_numbers & references["numbers"]:
        return None
    if time.time() - last_touched_at(folder) < ORPHAN_MIN_AGE_SECONDS:
        return None
    is_worktree = (folder / ".git").exists()
    if is_worktree:
        unsaved_changes = list_unsaved_changes(folder)
        if unsaved_changes:
            return "kept %s: %d changed file(s) such as %s" % (folder.name, len(unsaved_changes), unsaved_changes[0])
        missing_commits = count_commits_missing_from_remotes(folder)
        task_was_merged = bool(folder_numbers) and folder_numbers <= merged_numbers
        if missing_commits and not task_was_merged:
            return "kept %s: %d commit(s) not on any remote" % (folder.name, missing_commits)
    if dry_run:
        return "would remove %s" % folder.name
    if is_worktree:
        # --force: the checks above proved only regenerable files would be lost, and plain removal
        # refuses worktrees with an initialized submodule (.pinq-doq) or untracked Pods.
        removal = subprocess.run(["git", "-C", str(folder), "worktree", "remove", "--force", "--force", str(folder)],
                                 capture_output=True, text=True)
        if removal.returncode != 0:
            return "kept %s: %s" % (folder.name, removal.stderr.strip())
    else:
        shutil.rmtree(folder)
    return "removed %s" % folder.name


def clean_orphan_folders(dry_run):
    if not WORKTREES_DIR.exists():
        return []
    references = collect_protected_references()
    merged_numbers = find_merged_numbers()
    report = []
    for folder in sorted(child for child in WORKTREES_DIR.iterdir() if child.is_dir()):
        try:
            outcome = remove_orphan_folder(folder, references, merged_numbers, dry_run)
        except (OSError, RuntimeError, ValueError) as error:
            outcome = "kept %s: %s" % (folder.name, error)
        if outcome:
            report.append(outcome)
    return report


def prune_backups(dry_run):
    backups = sorted(state_tx.STATE_DIR.glob("state.json.bak-*"), key=lambda backup: backup.stat().st_mtime)
    backups = [backup for backup in backups if backup.name != state_tx.LAST_BACKUP_FILE.name]
    outdated_backups = backups[:-KEPT_BACKUP_COUNT]
    if not dry_run:
        for backup in outdated_backups:
            backup.unlink()
    return ["%s %d old state backups" % ("would remove" if dry_run else "removed", len(outdated_backups))] if outdated_backups else []


def prune_loose_logs(dry_run):
    if not WORKTREES_DIR.exists():
        return []
    outdated_logs = [log_file for log_file in WORKTREES_DIR.glob("*.log")
                     if time.time() - log_file.stat().st_mtime > LOOSE_LOG_MAX_AGE_SECONDS]
    if not dry_run:
        for log_file in outdated_logs:
            log_file.unlink()
    return ["%s %d old build logs" % ("would remove" if dry_run else "removed", len(outdated_logs))] if outdated_logs else []


def main():
    dry_run = "--dry-run" in sys.argv[1:]
    report = []
    if not dry_run:
        moved_keys = state_tx.archive_finished_tasks(state_tx.DEFAULT_ARCHIVE_AFTER_DAYS)
        if moved_keys:
            report.append("archived " + ", ".join(moved_keys))
    report += clean_archived_tasks(dry_run)
    report += clean_orphan_folders(dry_run)
    report += prune_backups(dry_run)
    report += prune_loose_logs(dry_run)
    print(json.dumps(report or ["nothing to clean"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
