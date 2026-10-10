#!/usr/bin/env python3
"""Check whether this machine can run the pinqloq task runner; print what is missing and how to fix it.

  doctor.py            exit 0 when every required check passes, 1 otherwise

It only reads: it never prints or stores secret values (it checks that the Keychain entry, the gh
login, the MCP server entry and test-accounts.json exist, not what they contain).
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner_config  # noqa: E402

RUNNER_DIR_IN_REPO = runner_config.SKILL_DIR.parent
CLAUDE_DIR = Path.home() / ".claude"
RUNNER_GITHUB_LOGIN = "pinq-ponq"
RUNNER_GH_CONFIG_DIR = Path.home() / ".config" / "gh-pinq-ponq"
REQUIRED_COMMANDS = {
    "git": "xcode-select --install",
    "gh": "brew install gh",
    "python3": "xcode-select --install",
    "java": "install JDK 21 (e.g. brew install --cask temurin@21)",
}
DEVICE_COMMANDS = {
    "adb": "Android SDK platform-tools; export ANDROID_HOME=~/Library/Android/sdk in ~/.zshrc",
    "emulator": "Android SDK emulator; add $ANDROID_HOME/emulator to PATH",
    "xcrun": "install Xcode",
    "maestro": "curl -fsSL https://get.maestro.mobile.dev | bash",
}
OPTIONAL_COMMANDS = {
    "dotnet": "brew install dotnet (backend tasks: rindle-backend, pinqops)",
    "node": "brew install node",
}
EXTRA_PATHS = [Path.home() / ".maestro" / "bin", Path.home() / "Library" / "Android" / "sdk" / "platform-tools",
               Path.home() / "Library" / "Android" / "sdk" / "emulator", Path("/opt/homebrew/bin")]


class Report:
    def __init__(self):
        self.failed = False

    def check(self, passed, name, hint, required=True):
        mark = "ok  " if passed else ("FAIL" if required else "warn")
        print("%s  %s%s" % (mark, name, "" if passed else "  ->  " + hint))
        if not passed and required:
            self.failed = True


def find_command(command):
    search_path = os.pathsep.join([os.environ.get("PATH", "")] + [str(path) for path in EXTRA_PATHS])
    return shutil.which(command, path=search_path)


def run_quietly(command, environment=None):
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=30, env=environment)
    except (OSError, subprocess.TimeoutExpired) as error:
        return subprocess.CompletedProcess(command, 1, "", str(error))


def check_commands(report):
    for commands, required in ((REQUIRED_COMMANDS, True), (DEVICE_COMMANDS, True), (OPTIONAL_COMMANDS, False)):
        for command, hint in commands.items():
            report.check(find_command(command) is not None, "command %s" % command, hint, required)


def check_links(report):
    expected_links = [(CLAUDE_DIR / "skills" / "pinqloq-task-runner", RUNNER_DIR_IN_REPO / "skill")]
    expected_links += [(CLAUDE_DIR / "agents" / agent.name, agent) for agent in sorted((RUNNER_DIR_IN_REPO / "agents").glob("pin-*.md"))]
    for link_path, target in expected_links:
        linked = link_path.is_symlink() and link_path.resolve() == target.resolve()
        report.check(linked, "link %s" % link_path.name, "run install.py (add --replace to move an old copy aside)")


def check_machine(report):
    try:
        machine = runner_config.read_machine_config()
    except ValueError as error:
        report.check(False, "machine.json", str(error))
        return None
    report.check(runner_config.MACHINE_CONFIG_FILE.exists(), "machine.json (role %s)" % machine["role"],
                 "run install.py --role primary|queue-only", required=False)
    report.check(machine["workspace_dir"].is_dir(), "workspace %s" % machine["workspace_dir"], "clone the project repos there")
    worktrees_ready = machine["worktrees_dir"].is_dir() and os.access(machine["worktrees_dir"], os.W_OK)
    report.check(worktrees_ready, "worktrees %s" % machine["worktrees_dir"], "create it (an external disk is fine; link it)")
    settings_file = machine["runner_dir"] / ".claude" / "settings.local.json"
    report.check(settings_file.exists(), "runner folder settings %s" % settings_file, "run install.py")
    report.check(bool(machine["mail_cc"]), "mail_cc in machine.json", "add the team addresses to machine.json `mail_cc`", required=False)
    return machine


def check_github(report):
    environment = {**os.environ, "GH_CONFIG_DIR": str(RUNNER_GH_CONFIG_DIR)}
    login = run_quietly(["gh", "api", "user", "-q", ".login"], environment).stdout.strip()
    report.check(login == RUNNER_GITHUB_LOGIN, "gh login %s (%s)" % (RUNNER_GITHUB_LOGIN, login or "none"),
                 "GH_CONFIG_DIR=%s gh auth login (as %s, scopes repo, project, read:org)" % (RUNNER_GH_CONFIG_DIR, RUNNER_GITHUB_LOGIN))
    status = run_quietly(["gh", "auth", "status"], environment)
    report.check("'project'" in status.stdout + status.stderr, "gh project scope",
                 "GH_CONFIG_DIR=%s gh auth refresh -s project" % RUNNER_GH_CONFIG_DIR)


def check_secrets(report, machine):
    team_config = runner_config.read_team_config()
    keychain = run_quietly(["security", "find-generic-password", "-a", team_config["username"], "-s", team_config["keychain_service"]])
    report.check(keychain.returncode == 0, "Keychain entry %s" % team_config["keychain_service"],
                 "security add-generic-password -a %s -s %s -w   (the SMTP app password; type it yourself)"
                 % (team_config["username"], team_config["keychain_service"]))
    test_accounts_file = runner_config.STATE_DIR / "test-accounts.json"
    report.check(test_accounts_file.exists(), "test-accounts.json", "copy it by hand from the primary machine (never commit it)",
                 required=machine is None or machine["role"] == runner_config.PRIMARY_ROLE)
    claude_settings_file = Path.home() / ".claude.json"
    projects = json.loads(claude_settings_file.read_text()).get("projects", {}) if claude_settings_file.exists() else {}
    runner_dir = str(machine["runner_dir"]) if machine else ""
    has_pinqloq_mcp = "pinqloq" in (projects.get(runner_dir, {}).get("mcpServers") or {})
    report.check(has_pinqloq_mcp, "pinqloq MCP server for %s" % runner_dir,
                 "in %s: claude mcp add pinqloq … (the key comes from the pinqloq dashboard)" % runner_dir)


def check_devices(report):
    emulator = find_command("emulator")
    avds = run_quietly([emulator, "-list-avds"]).stdout.split() if emulator else []
    report.check(bool(avds), "Android AVDs (%s)" % (", ".join(avds) or "none"),
                 "create the AVDs and snapshots the project's maestro/RUNNER.md lists")
    simulators = run_quietly(["xcrun", "simctl", "list", "devices", "available"]).stdout
    report.check("iPhone" in simulators, "iOS simulators", "install an iOS runtime in Xcode > Settings > Components")


def main():
    report = Report()
    print("pinqloq runner doctor (%s)\n" % RUNNER_DIR_IN_REPO)
    check_commands(report)
    check_links(report)
    machine = check_machine(report)
    check_github(report)
    check_secrets(report, machine)
    check_devices(report)
    print("\n%s" % ("Missing pieces above; fix the FAIL lines." if report.failed else "Ready."))
    return 1 if report.failed else 0


if __name__ == "__main__":
    sys.exit(main())
