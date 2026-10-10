# pinqloq task runner

The autonomous task runner for the pinqponq Project #9 board: it proposes Todo cards to the team, implements the tasks the team selects in git worktrees, proves them with tests, PIT and Maestro device runs, and opens ready-for-review PRs. It runs as Claude Code routines (runner-1/2/3) on a Mac and is watched from the local web panel [pinqponq/pinqponq-agents](https://github.com/pinqponq/pinqponq-agents) (a separate repo).

Unlike the rest of pinq-doq, nothing here is delivered into a project's `.claude/`: `deliver.py` copies only `rules/` and `skills/`. The runner is installed once per machine, as links from `~/.claude` into a pinq-doq checkout, so `git pull` updates it. Use a dedicated clone that stays on `main` (`~/StudioProjects/.pinqdoq-runner`), not the clone you edit pinq-doq in: the links follow whatever branch that checkout is on.

## Layout

```
runner/
  skill/        → linked as ~/.claude/skills/pinqloq-task-runner (SKILL.md, references/, scripts/, templates/)
    config.json     team configuration (board, mail server, To address); public, no personal data
    scripts/        state, locks, board, mail, build/PIT wrappers, preflight, install.py, doctor.py
  agents/       → linked as ~/.claude/agents/pin-test.md, pin-review.md, pin-device.md
  templates/    routine prompt and the runner folder's settings.local.json, rendered by install.py
```

## What stays on the machine

| Where | What | Committed? |
|---|---|---|
| `~/.claude/pinqloq-task-runner/` | `state.json` and archive, locks, runs.log, timings, sent mails, board cache, media, handoffs | never |
| `~/.claude/pinqloq-task-runner/machine.json` | `role`, `workspace_dir`, `worktrees_dir`, `runner_dir`, `mail_cc` | never |
| `~/.claude/pinqloq-task-runner/test-accounts.json` | test account sign-in values | never |
| macOS Keychain `pinqloq-smtp` | SMTP app password | never |
| `~/.config/gh-pinq-ponq` | the `pinq-ponq` bot's gh login | never |
| `~/.claude.json` (runner folder) | pinqloq MCP server and its key | never |
| `<runner_dir>/.claude/settings.local.json` | permission mode and pinq-ponq git identity (rendered from `templates/`) | never |

Project-specific device setup (test accounts, emulator snapshots, simulators, the state to restore after a scenario) lives in each project's `maestro/RUNNER.md`, not here.

## Roles

- **primary** — the full runner: board scan, proposals, comment decisions, reminders, verification retries.
- **queue-only** — a second machine: works only on the tasks the owner queues in that machine's panel (or chat). Preflight skips every housekeeping check, so it never repeats the primary's proposals, mails or comment decisions. The owner answers its questions in its panel.

Each machine has its own state and queue; they do not coordinate, so give each task to one machine.

## Install on a new machine

Follow [`../tasks/install-runner.md`](../tasks/install-runner.md). In short:

```bash
git clone https://github.com/pinqponq/pinqdoq ~/StudioProjects/.pinqdoq-runner
python3 ~/StudioProjects/.pinqdoq-runner/runner/skill/scripts/install.py --role queue-only --mail-cc <team addresses>
python3 ~/.claude/skills/pinqloq-task-runner/scripts/doctor.py
```

`doctor.py` lists what is still missing (gh login, Keychain entry, MCP key, devices) with the command for each.

## Update

`git -C ~/StudioProjects/.pinqdoq-runner pull` (it stays on `main`). Run `install.py` again only when this README or the templates changed.
