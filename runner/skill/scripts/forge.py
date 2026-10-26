#!/usr/bin/env python3
"""Pull request / merge request commands that work the same on GitHub (gh) and GitLab (glab).

  forge.py repo <repo_dir>                        {"forge", "host", "path"} of the checkout's origin
  forge.py base <repo_dir>                        the PR base: develop when origin has it, else the default branch
  forge.py check <repo_dir> <base>                exit 1 with a message when <base> is not the PR base
  forge.py find <repo_dir> <branch>               the open PR/MR from <branch> as {"number", "url"}, or "none"
  forge.py open <repo_dir> --branch B --base X --title T --body-file F     opens it ready for review, prints the URL
  forge.py update <repo_dir> <number> [--title T] [--body-file F] [--base X]
  forge.py ready <repo_dir> <number>              marks a draft ready for review
  forge.py upload <repo_dir> <file>               GitLab only: uploads a screenshot or video to the project and
                                                  prints its address for the MR description

The forge comes from origin's host: github.com uses gh; the machine's `gitlab_host` (machine.json) uses
glab. The base is read with `git ls-remote`, so it needs only the git login. There is no merge command:
merging stays with people (and, on GitHub, with implementation.md's auto-merge rubric).
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner_config  # noqa: E402

GITHUB_HOST = "github.com"
DEVELOP_BRANCH = "develop"
# https://host/group/repo.git, ssh://git@host:2222/group/repo.git, git@host:group/repo.git
REMOTE_URL_PATTERNS = [re.compile(r"^(?:https?|ssh)://(?:[^@/]+@)?([^/:]+)(?::\d+)?/(.+?)(?:\.git)?/?$"),
                       re.compile(r"^[^@/]+@([^:/]+):(.+?)(?:\.git)?/?$")]
URL_PATTERN = re.compile(r"https?://\S+")
EXIT_WRONG_BASE = 1


class ForgeError(Exception):
    pass


def run_command(command, environment=None):
    completed = subprocess.run(command, capture_output=True, text=True, env=environment)
    if completed.returncode != 0:
        raise ForgeError("%s failed: %s" % (" ".join(command[:3]), (completed.stderr or completed.stdout).strip()))
    return completed.stdout


def parse_remote_url(remote_url):
    for pattern in REMOTE_URL_PATTERNS:
        match = pattern.match(remote_url.strip())
        if match:
            return match.group(1).lower(), match.group(2)
    raise ForgeError("cannot read host and path from origin %r" % remote_url)


def describe_repository(repo_dir, gitlab_host):
    host, path = parse_remote_url(run_command(["git", "-C", str(repo_dir), "remote", "get-url", "origin"]))
    if host == GITHUB_HOST:
        return {"forge": runner_config.GITHUB_FORGE, "host": host, "path": path}
    if gitlab_host and host == gitlab_host.split(":")[0].lower():
        return {"forge": runner_config.GITLAB_FORGE, "host": host, "path": path}
    raise ForgeError("origin host %s is neither %s nor this machine's gitlab_host (%s)" % (host, GITHUB_HOST, gitlab_host))


def default_branch(repo_dir):
    symbolic_reference = run_command(["git", "-C", str(repo_dir), "ls-remote", "--symref", "origin", "HEAD"])
    match = re.search(r"^ref: refs/heads/(\S+)\s+HEAD$", symbolic_reference, re.MULTILINE)
    if not match:
        raise ForgeError("origin of %s reports no default branch" % repo_dir)
    return match.group(1)


def pull_request_base(repo_dir):
    develop_heads = run_command(["git", "-C", str(repo_dir), "ls-remote", "--heads", "origin", DEVELOP_BRANCH])
    return DEVELOP_BRANCH if develop_heads.strip() else default_branch(repo_dir)


def glab_environment(repository):
    return {**os.environ, "GITLAB_HOST": repository["host"]}


def find_open_request(repository, branch):
    if repository["forge"] == runner_config.GITHUB_FORGE:
        listed = json.loads(run_command(["gh", "pr", "list", "-R", repository["path"], "--head", branch,
                                         "--state", "open", "--json", "number,url"]))
        return listed[0] if listed else None
    listed = json.loads(run_command(["glab", "mr", "list", "-R", repository["path"], "--source-branch", branch,
                                     "--output", "json"], glab_environment(repository)))
    return {"number": listed[0]["iid"], "url": listed[0]["web_url"]} if listed else None


def last_url(command_output):
    urls = URL_PATTERN.findall(command_output)
    if not urls:
        raise ForgeError("no address in the output: %s" % command_output.strip())
    return urls[-1]


def open_request(repository, branch, base, title, body_file):
    if repository["forge"] == runner_config.GITHUB_FORGE:
        return last_url(run_command(["gh", "pr", "create", "-R", repository["path"], "--head", branch, "--base", base,
                                     "--title", title, "--body-file", str(body_file)]))
    return last_url(run_command(["glab", "mr", "create", "-R", repository["path"], "--source-branch", branch,
                                 "--target-branch", base, "--title", title, "--description-file", str(body_file),
                                 "--yes"], glab_environment(repository)))


def update_request(repository, number, title=None, body_file=None, base=None):
    if not (title or body_file or base):
        raise ForgeError("nothing to update: pass --title, --body-file or --base")
    if repository["forge"] == runner_config.GITHUB_FORGE:
        command = ["gh", "pr", "edit", str(number), "-R", repository["path"]]
        command += (["--title", title] if title else []) + (["--body-file", str(body_file)] if body_file else [])
        command += ["--base", base] if base else []
        return run_command(command)
    command = ["glab", "mr", "update", str(number), "-R", repository["path"]]
    command += (["--title", title] if title else []) + (["--description-file", str(body_file)] if body_file else [])
    command += ["--target-branch", base] if base else []
    return run_command(command, glab_environment(repository))


def mark_ready(repository, number):
    if repository["forge"] == runner_config.GITHUB_FORGE:
        return run_command(["gh", "pr", "ready", str(number), "-R", repository["path"]])
    return run_command(["glab", "mr", "update", str(number), "-R", repository["path"], "--ready"],
                       glab_environment(repository))


def upload_file(repository, file_path):
    if repository["forge"] != runner_config.GITLAB_FORGE:
        raise ForgeError("upload is for GitLab; on GitHub publish media to the task-runner-media branch (implementation.md step 9)")
    endpoint = "projects/%s/uploads" % quote(repository["path"], safe="")
    uploaded = json.loads(run_command(["glab", "api", "--hostname", repository["host"], "--method", "POST", endpoint,
                                       "--form", "file=@%s" % file_path], glab_environment(repository)))
    return uploaded["url"]


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    subcommands = parser.add_subparsers(dest="command", required=True)
    for name in ("repo", "base"):
        subcommands.add_parser(name).add_argument("repo_dir")
    check_parser = subcommands.add_parser("check")
    check_parser.add_argument("repo_dir")
    check_parser.add_argument("base")
    find_parser = subcommands.add_parser("find")
    find_parser.add_argument("repo_dir")
    find_parser.add_argument("branch")
    open_parser = subcommands.add_parser("open")
    open_parser.add_argument("repo_dir")
    open_parser.add_argument("--branch", required=True)
    open_parser.add_argument("--base", required=True)
    open_parser.add_argument("--title", required=True)
    open_parser.add_argument("--body-file", required=True)
    update_parser = subcommands.add_parser("update")
    update_parser.add_argument("repo_dir")
    update_parser.add_argument("number", type=int)
    update_parser.add_argument("--title")
    update_parser.add_argument("--body-file")
    update_parser.add_argument("--base")
    ready_parser = subcommands.add_parser("ready")
    ready_parser.add_argument("repo_dir")
    ready_parser.add_argument("number", type=int)
    upload_parser = subcommands.add_parser("upload")
    upload_parser.add_argument("repo_dir")
    upload_parser.add_argument("file")
    return parser.parse_args()


def run(arguments):
    repo_dir = Path(arguments.repo_dir).expanduser()
    if arguments.command == "base":
        print(pull_request_base(repo_dir))
        return 0
    if arguments.command == "check":
        expected_base = pull_request_base(repo_dir)
        if arguments.base != expected_base:
            print("wrong base %s: the PR base of %s is %s" % (arguments.base, repo_dir, expected_base))
            return EXIT_WRONG_BASE
        print("ok")
        return 0
    repository = describe_repository(repo_dir, runner_config.read_machine_config()["gitlab_host"])
    if arguments.command == "repo":
        print(json.dumps(repository))
    elif arguments.command == "find":
        open_request_found = find_open_request(repository, arguments.branch)
        print(json.dumps(open_request_found) if open_request_found else "none")
    elif arguments.command == "open":
        print(open_request(repository, arguments.branch, arguments.base, arguments.title, arguments.body_file))
    elif arguments.command == "update":
        update_request(repository, arguments.number, arguments.title, arguments.body_file, arguments.base)
        print("updated")
    elif arguments.command == "ready":
        mark_ready(repository, arguments.number)
        print("ready")
    elif arguments.command == "upload":
        print(upload_file(repository, arguments.file))
    return 0


def main():
    try:
        return run(parse_arguments())
    except ForgeError as error:
        print("forge: %s" % error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
