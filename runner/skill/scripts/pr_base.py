#!/usr/bin/env python3
"""Pull request base check for the runner (implementation.md step 10).

  pr_base.py base <owner/repo>                 print the base branch a PR must target
  pr_base.py check <owner/repo> <base>         exit 1 with a message when <base> is wrong
  pr_base.py environment <owner/repo> <base>   print the workflows that deploy on a push to <base>

The base is `develop` when the repository has that branch, otherwise the default branch.
`main` or `master` only receives merges from `develop`.
"""
import argparse
import json
import re
import subprocess
import sys

INTEGRATION_BRANCH = "develop"


def choose_base(default_branch, has_develop):
    return INTEGRATION_BRANCH if has_develop else default_branch


def base_problem(base, default_branch, has_develop):
    """Returns the refusal message for a wrong base, or None when the base is right."""
    if base == choose_base(default_branch, has_develop):
        return None
    if has_develop and base == default_branch:
        return (f"Refused: the repository has `{INTEGRATION_BRANCH}`, so a task PR must target "
                f"`{INTEGRATION_BRANCH}`, not `{default_branch}`. `{default_branch}` only receives merges "
                f"from `{INTEGRATION_BRANCH}`.")
    return f"Refused: base `{base}` is not `{choose_base(default_branch, has_develop)}`."


def push_branches(workflow_text):
    """Branch names (or globs) listed under `on: push: branches:` in a workflow file."""
    branches = []
    lines = workflow_text.splitlines()
    in_push = False
    push_indent = 0
    in_branches = False
    branches_indent = 0
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if in_branches:
            if indent > branches_indent and stripped.startswith("-"):
                branches.append(stripped[1:].split("#")[0].strip().strip("'\""))
                continue
            in_branches = False
        if in_push and indent <= push_indent:
            in_push = False
        if re.match(r"^push\s*:", stripped):
            in_push = True
            push_indent = indent
            inline = re.match(r"^push\s*:\s*\{.*branches\s*:\s*\[([^\]]*)\]", stripped)
            if inline:
                branches += [b.strip().strip("'\"") for b in inline.group(1).split(",") if b.strip()]
            continue
        if in_push and re.match(r"^branches\s*:", stripped):
            inline = re.match(r"^branches\s*:\s*\[([^\]]*)\]", stripped)
            if inline:
                branches += [b.strip().strip("'\"") for b in inline.group(1).split(",") if b.strip()]
            else:
                in_branches = True
                branches_indent = indent
    return branches


def branch_matches(pattern, branch):
    regex = re.escape(pattern).replace(r"\*\*", ".*").replace(r"\*", "[^/]*")
    return re.fullmatch(regex, branch) is not None


def deploying_workflows(workflows, base):
    """Names of the workflows (name -> text) that run on a push to `base`."""
    return sorted(name for name, text in workflows.items()
                  if any(branch_matches(pattern, base) for pattern in push_branches(text)))


def environment_note(workflows, base):
    names = deploying_workflows(workflows, base)
    if not names:
        return f"A merge to `{base}` starts no workflow on push."
    return f"A merge to `{base}` runs on push: {', '.join(names)}. Open each file and name the environment it reaches in the PR."


def gh_json(path):
    result = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    if result.returncode != 0:
        return None
    return json.loads(result.stdout)


def repo_facts(repo):
    info = gh_json(f"repos/{repo}")
    if info is None:
        sys.exit(f"Could not read {repo} with gh.")
    has_develop = gh_json(f"repos/{repo}/branches/{INTEGRATION_BRANCH}") is not None
    return info["default_branch"], has_develop


def fetch_workflows(repo, ref):
    listing = gh_json(f"repos/{repo}/contents/.github/workflows?ref={ref}") or []
    workflows = {}
    for entry in listing:
        if not entry["name"].endswith((".yml", ".yaml")):
            continue
        raw = subprocess.run(["gh", "api", "-H", "Accept: application/vnd.github.raw", entry["url"]],
                             capture_output=True, text=True)
        if raw.returncode == 0:
            workflows[entry["name"]] = raw.stdout
    return workflows


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("base").add_argument("repo")
    check = sub.add_parser("check")
    check.add_argument("repo")
    check.add_argument("base")
    environment = sub.add_parser("environment")
    environment.add_argument("repo")
    environment.add_argument("base")
    args = parser.parse_args()

    default_branch, has_develop = repo_facts(args.repo)
    if args.command == "base":
        print(choose_base(default_branch, has_develop))
    elif args.command == "check":
        problem = base_problem(args.base, default_branch, has_develop)
        if problem:
            print(problem, file=sys.stderr)
            sys.exit(1)
        print(f"ok: {args.base}")
    else:
        print(environment_note(fetch_workflows(args.repo, args.base), args.base))


if __name__ == "__main__":
    main()
