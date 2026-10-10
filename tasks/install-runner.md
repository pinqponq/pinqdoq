# Task: install-runner

Run these steps when asked to **install the pinqloq task runner** on a machine (a new Mac, or this one after the runner moved into pinq-doq). Claude runs the commands; the steps marked **(owner)** need the owner at the keyboard because they involve a login or a secret. Never type, paste or store a secret yourself.

The runner is not delivered into projects. It is linked from `~/.claude` into a dedicated pinq-doq clone that stays on `main`. See [`runner/README.md`](../runner/README.md) for the layout and the roles.

## 1. Tools

Xcode (with an iOS simulator runtime), Android Studio or the Android SDK (`adb`, `emulator`), JDK 21, Homebrew, `gh`, Maestro, and for backend tasks the .NET SDK and Node. Export `ANDROID_HOME`, `DOTNET_ROOT` and the Maestro path in `~/.zshrc`. `doctor.py` (step 4) lists whatever is still missing.

## 2. Clone pinq-doq for the runner and the projects

```bash
git clone https://github.com/pinqponq/pinqdoq ~/StudioProjects/.pinqdoq-runner
```

Clone the project repos the runner works on into `~/StudioProjects` (or the workspace you pass in step 3).

## 3. Install

```bash
python3 ~/StudioProjects/.pinqdoq-runner/runner/skill/scripts/install.py --role <primary|queue-only> --mail-cc <team addresses>
```

- `primary` on exactly one machine; every other machine is `queue-only`.
- `--worktrees <dir>` when the worktrees should live elsewhere (e.g. an external disk); the default is `~/StudioProjects/.task-runner-worktrees`.
- On a machine that already has a hand-made copy of the runner under `~/.claude`, add `--replace`: the old files are moved to `~/.claude/pinqloq-trash/<timestamp>/`, never deleted. Do this only while no runner session is running (`locks.py status` shows no task lock).

The script creates `machine.json`, links the skill, agents and panel, writes the runner folder's `settings.local.json` and the routine prompts, then runs `doctor.py`. It never overwrites an existing `machine.json` or settings file.

## 4. Secrets and accounts (owner)

Run `python3 ~/.claude/skills/pinqloq-task-runner/scripts/doctor.py` and fix each `FAIL` line with the command it shows:

- **gh as `pinq-ponq`:** `GH_CONFIG_DIR=~/.config/gh-pinq-ponq gh auth login` with the bot account, scopes `repo`, `project`, `read:org`.
- **SMTP password:** `security add-generic-password -a <username> -s pinqloq-smtp -w` (prompts for the app password).
- **pinqloq MCP:** in the runner folder, `claude mcp add pinqloq …` with a key from the pinqloq dashboard.
- **Test accounts:** copy `~/.claude/pinqloq-task-runner/test-accounts.json` from the primary machine over a private channel.
- **Devices:** create the AVDs and snapshots listed in each project's `maestro/RUNNER.md` (rindle-cmp: the signed-in `rindle-logged-in` snapshot).

Run `doctor.py` again until it prints `Ready.`

## 5. Routines

In a Claude Code chat say: **create the runner routines from `~/.claude/pinqloq-task-runner/routines`**. Claude creates one scheduled task per file (task ids `pinqloq-task-runner`, `-2`, `-3`; folder: the runner folder; no schedule, started by hand). Then set each routine's permission mode to bypass in the app **(owner)**; the routine settings are the owner's, Claude does not change them.

## 6. Panel

```bash
python3 ~/.claude/pinqloq-panel/server.py
```

Open http://127.0.0.1:8787. The panel's Start button only writes a request; a Claude chat that watches `start-requests.jsonl` starts the routine.

## Moving state (optional)

A new machine starts with an empty state. Copy `state.json` and `state-archive.json` from the old machine only when this machine replaces it (and the old one stops running); never run two machines on copies of the same state.
