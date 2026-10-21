# pinqloq Task Runner — the runner routines and the device limit

Read this when you need to know which runner takes which task, or why a device lock is busy. It is part of SKILL.md; "Parallel sessions" there says how each lock is taken.

## The four runners
`install.py` writes one routine prompt per runner from `runner/templates/routine.md`:

| Routine | Label | Started by | Takes |
|---|---|---|---|
| `pinqloq-task-runner` | runner-1 | schedule | any task |
| `pinqloq-task-runner-2` | runner-2 | panel auto-start or by hand | any task |
| `pinqloq-task-runner-3` | runner-3 | panel auto-start or by hand | only tasks with `weight: "light"` (`--light-only`); no verification retries |
| `pinqloq-task-runner-4` | runner-4 | panel auto-start or by hand | any task (same prompt as runner-2) |

Runners 1, 2 and 4 take every task, including verification retries. Runner-3 stays light-only so the owner can keep it free for quick work.

## At most 2 device jobs at once
The emulator and the simulator are the slow, shared part of a run. The limit is the per-device locks, not a new mechanism:
- One session at a time on the Android emulator (`devices-android`) and one on the iOS simulator (`devices-ios`). So at most 2 device jobs run at the same time, whichever runners hold them.
- Web tests (Playwright, Vitest, Stryker) are not counted. Vitest and Stryker take no device lock. Playwright flows take only `devices-web`, which guards the project's fixed dev server port and shared test account, not an emulator or simulator.
- Builds, unit tests, PIT and code review take no device lock and run in parallel with every other session.
- A session that needs a device which another session holds does its other steps first (build, tests, PIT), then waits on `devices acquire`. If the lock is still held when the wait ends (exit 3), it pushes the WIP branch, keeps the task `in_progress`, releases the task lock and finishes its pass. It never starts a second task while it waits; the next pass of any runner picks the task up again.
