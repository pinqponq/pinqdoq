#!/usr/bin/env python3
"""Pull request base check for the runner (implementation.md step 10).

  pr_base.py base <owner/repo>                 print the base branch a PR must target
  pr_base.py check <owner/repo> <base>         exit 1 with a message when <base> is wrong
                                               (another `task/…` branch of the repo is allowed: stacked PRs)
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


def base_problem(base, default_branch, has_develop, is_task_branch=False):
    """Returns the refusal message for a wrong base, or None when the base is right.
    A stacked or moving PR may sit on another task branch of the same repository."""
    if base == choose_base(default_branch, has_develop) or is_task_branch:
        return None
    if has_develop and base == default_branch:
        return (f"Refused: the repository has `{INTEGRATION_BRANCH}`, so a task PR must target "
                f"`{INTEGRATION_BRANCH}`, not `{default_branch}`. `{default_branch}` only receives merges "
                f"from `{INTEGRATION_BRANCH}`.")
    return f"Refused: base `{base}` is not `{choose_base(default_branch, has_develop)}`."


def push_filter(workflow_text):
    """What a workflow runs on: [] (no branch push), "any" (any branch, or a branches-ignore filter),
    or the branch names/globs under `on: push: branches:`."""
    text = re.sub(r"(?m)#.*$", "", workflow_text)
    if re.search(r"(?m)^\s*on\s*:\s*\[?[^\n]*\bpush\b", text) and not re.search(r"(?m)^\s*push\s*:", text):
        return "any"
    lines = text.splitlines()
    in_push = False
    push_indent = 0
    keys = {}
    current = None
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        indent = len(line) - len(line.lstrip())
        if in_push and indent <= push_indent:
            in_push = False
        if re.match(r"^push\s*:", stripped):
            in_push = True
            push_indent = indent
            inline = re.match(r"^push\s*:\s*\{(.*)\}", stripped)
            if inline:
                for key, value in re.findall(r"([\w-]+)\s*:\s*\[([^\]]*)\]", inline.group(1)):
                    keys[key] = [v.strip().strip("'\"") for v in value.split(",") if v.strip()]
            elif stripped != "push:":
                return "any"
            continue
        if not in_push:
            continue
        key_match = re.match(r"^([\w-]+)\s*:\s*(.*)$", stripped)
        if key_match and not stripped.startswith("-"):
            current = key_match.group(1)
            value = key_match.group(2).strip()
            keys.setdefault(current, [])
            if value.startswith("["):
                keys[current] += [v.strip().strip("'\"") for v in value.strip("[]").split(",") if v.strip()]
        elif stripped.startswith("-") and current:
            keys[current].append(stripped[1:].strip().strip("'\""))
    if not in_push and not keys and not re.search(r"(?m)^\s*push\s*:", text):
        return []
    if "branches" in keys:
        return keys["branches"]
    if "tags" in keys and "branches-ignore" not in keys:
        return []
    return "any"


def branch_matches(pattern, branch):
    if re.search(r"[!?+\[]", pattern):
        return True
    regex = re.escape(pattern).replace(r"\*\*", ".*").replace(r"\*", "[^/]*")
    return re.fullmatch(regex, branch) is not None


def deploying_workflows(workflows, base):
    """Names of the workflows (name -> text) that run on a push to `base`."""
    names = []
    for name, text in workflows.items():
        pushed = push_filter(text)
        if pushed == "any" or any(branch_matches(pattern, base) for pattern in pushed):
            names.append(name)
    return sorted(names)


def environment_note(workflows, base):
    names = deploying_workflows(workflows, base)
    if not names:
        return f"A merge to `{base}` starts no workflow on push."
    return (f"A merge to `{base}` may run on push: {', '.join(names)}. "
            "Open each file and name the environment it reaches in the PR.")


def gh_json(path):
    result = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    if result.returncode != 0:
        return None
    return json.loads(result.stdout)


def branch_exists(repo, branch):
    """True or False; any failure other than 404 stops, so an outage never reads as "no develop"."""
    result = subprocess.run(["gh", "api", f"repos/{repo}/branches/{branch}"], capture_output=True, text=True)
    if result.returncode == 0:
        return True
    if "404" in result.stderr or "Not Found" in result.stderr:
        return False
    sys.exit(f"Could not read branch {branch} of {repo}: {result.stderr.strip()}")


def repo_facts(repo):
    info = gh_json(f"repos/{repo}")
    if info is None:
        sys.exit(f"Could not read {repo} with gh.")
    return info["default_branch"], branch_exists(repo, INTEGRATION_BRANCH)


def fetch_workflows(repo, ref):
    listing = subprocess.run(["gh", "api", f"repos/{repo}/contents/.github/workflows?ref={ref}"],
                             capture_output=True, text=True)
    if listing.returncode != 0:
        if "404" in listing.stderr or "Not Found" in listing.stderr:
            return {}
        sys.exit(f"Could not list the workflows of {repo}: {listing.stderr.strip()}")
    workflows = {}
    for entry in json.loads(listing.stdout):
        if not entry["name"].endswith((".yml", ".yaml")):
            continue
        raw = subprocess.run(["gh", "api", "-H", "Accept: application/vnd.github.raw", entry["url"]],
                             capture_output=True, text=True)
        if raw.returncode != 0:
            sys.exit(f"Could not read workflow {entry['name']} of {repo}: {raw.stderr.strip()}")
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
        stacked = args.base.startswith("task/") and branch_exists(args.repo, args.base)
        problem = base_problem(args.base, default_branch, has_develop, stacked)
        if problem:
            print(problem, file=sys.stderr)
            sys.exit(1)
        print(f"ok: {args.base}")
    else:
        print(environment_note(fetch_workflows(args.repo, args.base), args.base))


if __name__ == "__main__":
    main()
