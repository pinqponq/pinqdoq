#!/usr/bin/env python3
"""Housekeeping cleanup for the pinqloq task runner (run at the end of the housekeeping steps).

  cleanup.py [--dry-run]

1. Archives finished tasks (`state_tx.py archive`: merged/skipped/declined/done, untouched for 3 days).
2. For archived tasks: removes their local media folder (the evidence is already on the repo's
   `task-runner-media` branch) and their worktrees, but only when the worktree has no uncommitted or
   untracked changes and no unpushed commits; otherwise it is kept and reported.
3. Keeps only the newest state.json backups and deletes loose build logs older than a week from
   the worktrees directory.
"""
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner_config  # noqa: E402
import state_tx  # noqa: E402

MEDIA_DIR = state_tx.STATE_DIR / "media"
WORKTREES_DIR = runner_config.read_machine_config()["worktrees_dir"]
WORKTREE_FIELDS = ["worktree", "backend_worktree", "core_worktree"]
KEPT_BACKUP_COUNT = 3
LOOSE_LOG_MAX_AGE_SECONDS = 7 * 24 * 60 * 60


def media_folder_for(task_key):
    repository_and_number = task_key.split("/", 1)[1]
    return MEDIA_DIR / repository_and_number.replace("#", "-")


def remove_worktree(worktree_path, dry_run):
    if not worktree_path.exists():
        return None
    if dry_run:
        return "would remove worktree %s" % worktree_path
    unsaved_work = find_unsaved_work(worktree_path)
    if unsaved_work:
        return "kept worktree %s: %s" % (worktree_path, unsaved_work)
    # Plain `worktree remove` refuses any worktree with an initialized submodule (.pinq-doq), so
    # --force is used, but only after the checks above proved nothing would be lost.
    completed = subprocess.run(["git", "-C", str(worktree_path), "worktree", "remove", "--force", str(worktree_path)],
                               capture_output=True, text=True)
    if completed.returncode != 0:
        return "kept worktree %s: %s" % (worktree_path, completed.stderr.strip())
    return "removed worktree %s" % worktree_path


def find_unsaved_work(worktree_path):
    status = subprocess.run(["git", "-C", str(worktree_path), "status", "--porcelain"],
                            capture_output=True, text=True)
    if status.returncode != 0:
        return "git status failed: " + status.stderr.strip()
    if status.stdout.strip():
        return "uncommitted or untracked changes"
    unpushed = subprocess.run(["git", "-C", str(worktree_path), "rev-list", "--count", "@{u}..HEAD"],
                              capture_output=True, text=True)
    if unpushed.returncode != 0:
        return "no upstream branch"
    if unpushed.stdout.strip() != "0":
        return "%s unpushed commit(s)" % unpushed.stdout.strip()
    return None


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
        for field in WORKTREE_FIELDS:
            if task.get(field):
                outcome = remove_worktree(Path(task[field]).expanduser(), dry_run)
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
    report += prune_backups(dry_run)
    report += prune_loose_logs(dry_run)
    print(json.dumps(report or ["nothing to clean"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
