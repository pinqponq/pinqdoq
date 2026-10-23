# pinqloq Task Runner — the runner routines and the device limit

Read this when you need to know which runner takes which task, or why a device lock is busy. It is part of SKILL.md; "Parallel sessions" there says how each lock is taken.

## The four runners
`install.py` writes one routine prompt per runner from `runner/templates/routine.md`:

| Routine | Label (role) | Started by | Takes |
|---|---|---|---|
| `pinqloq-task-runner` | runner-1 (device, android) | schedule | tasks that need a device, Android first; verification retries |
| `pinqloq-task-runner-2` | runner-2 (device, ios) | panel auto-start or by hand | tasks that need a device, iOS first; verification retries |
| `pinqloq-task-runner-3` | runner-3 (light) | panel auto-start or by hand | only tasks with `weight: "light"` (`--light-only`); no verification retries |
| `pinqloq-task-runner-4` | runner-4 (no-device) | panel auto-start or by hand | only tasks with `needs_device: false` (`--role no-device`); no verification retries |

The roles live in one place, `RUNNER_ROLES` in `scripts/runner_config.py`; `install.py` writes the flags and notes into the routine prompts from it and the labels show the role. The scheduled task names (first column) never change: the panel, the start script and the watchers use them.

**`needs_device`.** Set in step 3 with `weight`. `false` means no device step; `true` or unset (unknown) means the task needs one.

**Claim order.** A device runner (1, 2) puts tasks that need a device first, then the usual order (status, `queue_priority`, age). When no device task is claimable it takes a task without a device instead of idling, and `locks.py claim` prints `note: no device task is claimable; a device runner took a task without a device` on stderr; write it into `runs.log`. Runner-4 never takes a device task; when only device tasks wait it stays idle and the preflight idle line in `runs.log` lists each skipped task with `needs a device`, so the idle is visible and not silent. Runner-3 is unchanged.

**Free device.** Runners 1 and 2 are not bound to their device: shared-code proof takes whichever device is free (`implementation.md` → "Choose the device").

## At most 2 device jobs at once
The emulator and the simulator are the slow, shared part of a run. The limit is the per-device locks, not a new mechanism:
- One session at a time on the Android emulator (`devices-android`) and one on the iOS simulator (`devices-ios`). So at most 2 device jobs run at the same time, whichever runners hold them.
- Web tests (Playwright, Vitest, Stryker) are not counted. Vitest and Stryker take no device lock. Playwright flows take only `devices-web`, which guards the project's fixed dev server port and shared test account, not an emulator or simulator.
- Builds, unit tests, PIT and code review take no device lock and run in parallel with every other session.
- A session that needs a specific platform which another session holds does its other steps first (build, tests, PIT), then waits on `devices acquire`. If the lock is still held when the wait ends (exit 3), it pushes the WIP branch, keeps the task `in_progress`, releases the task lock and finishes its pass. It never starts a second task while it waits; the next pass of any runner picks the task up again.
