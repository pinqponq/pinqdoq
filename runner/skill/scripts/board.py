#!/usr/bin/env python3
"""Cheap access to the pinqponq Project #9 board.

`gh project item-list --limit 3000` asks GraphQL for every field value of every item and costs
hundreds of rate-limit points per call; with parallel runner sessions it used up the hourly 5,000
points on 2026-10-03. This script asks only for the Status field, caches the result for a few
minutes in the state directory so parallel sessions share one fetch, and moves cards with a single
mutation using the field and option ids it resolves (and caches) itself.

  board.py items [--status <name>] [--refresh]   JSON list: item_id, key, type, state, title, status, assignees
  board.py find <task-key> [--refresh]           one item as JSON (exit 4 when the task has no card)
  board.py move <task-key> <status name>         set the card's Status (e.g. "In progress", "Waiting for human review")
"""
import json
import subprocess
import sys
import time
from pathlib import Path

STATE_DIR = Path.home() / ".claude" / "pinqloq-task-runner"
ITEMS_CACHE_FILE = STATE_DIR / "board_items.json"
PROJECT_CACHE_FILE = STATE_DIR / "board_project.json"
ITEMS_CACHE_MAX_AGE_SECONDS = 5 * 60
ORGANIZATION = "pinqponq"
PROJECT_NUMBER = 9
PAGE_SIZE = 100
EXIT_NOT_FOUND = 4

ITEMS_QUERY = """
query($organization: String!, $number: Int!, $cursor: String) {
  organization(login: $organization) {
    projectV2(number: $number) {
      items(first: %d, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          fieldValueByName(name: "Status") { ... on ProjectV2ItemFieldSingleSelectValue { name } }
          content {
            __typename
            ... on Issue { number title state repository { nameWithOwner } assignees(first: 10) { nodes { login } } }
            ... on PullRequest { number title state repository { nameWithOwner } assignees(first: 10) { nodes { login } } }
            ... on DraftIssue { title }
          }
        }
      }
    }
  }
}
""" % PAGE_SIZE

PROJECT_QUERY = """
query($organization: String!, $number: Int!) {
  organization(login: $organization) {
    projectV2(number: $number) {
      id
      field(name: "Status") { ... on ProjectV2SingleSelectField { id options { id name } } }
    }
  }
}
"""

MOVE_MUTATION = """
mutation($project: ID!, $item: ID!, $field: ID!, $option: String!) {
  updateProjectV2ItemFieldValue(input: {projectId: $project, itemId: $item, fieldId: $field,
                                        value: {singleSelectOptionId: $option}}) {
    projectV2Item { id }
  }
}
"""


def run_graphql(query, variables):
    command = ["gh", "api", "graphql", "-f", "query=" + query]
    for name, value in variables.items():
        if value is None:
            continue
        command += ["-F" if isinstance(value, int) else "-f", "%s=%s" % (name, value)]
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError("gh api graphql failed: %s" % (completed.stderr.strip() or completed.stdout.strip()))
    response = json.loads(completed.stdout)
    if response.get("errors"):
        raise RuntimeError("GraphQL errors: %s" % json.dumps(response["errors"], ensure_ascii=False))
    return response["data"]


def to_board_item(node):
    content = node.get("content") or {}
    content_type = content.get("__typename", "Unknown")
    repository = (content.get("repository") or {}).get("nameWithOwner")
    task_key = "%s#%d" % (repository, content["number"]) if repository and content.get("number") else None
    return {
        "item_id": node["id"],
        "key": task_key,
        "type": content_type,
        "state": content.get("state"),
        "title": content.get("title"),
        "status": (node.get("fieldValueByName") or {}).get("name"),
        "assignees": [assignee["login"] for assignee in (content.get("assignees") or {}).get("nodes", [])],
    }


def fetch_items():
    board_items = []
    cursor = None
    while True:
        data = run_graphql(ITEMS_QUERY, {"organization": ORGANIZATION, "number": PROJECT_NUMBER, "cursor": cursor})
        page = data["organization"]["projectV2"]["items"]
        board_items += [to_board_item(node) for node in page["nodes"]]
        if not page["pageInfo"]["hasNextPage"]:
            return board_items
        cursor = page["pageInfo"]["endCursor"]


def write_atomically(target_file, content):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    temporary_file = target_file.with_name(target_file.name + ".tmp")
    temporary_file.write_text(content)
    temporary_file.replace(target_file)


def load_items(refresh=False):
    is_cache_fresh = (ITEMS_CACHE_FILE.exists()
                      and time.time() - ITEMS_CACHE_FILE.stat().st_mtime <= ITEMS_CACHE_MAX_AGE_SECONDS)
    if is_cache_fresh and not refresh:
        return json.loads(ITEMS_CACHE_FILE.read_text())
    board_items = fetch_items()
    write_atomically(ITEMS_CACHE_FILE, json.dumps(board_items, ensure_ascii=False))
    return board_items


def find_item(task_key, refresh=False):
    for board_item in load_items(refresh):
        if board_item["key"] == task_key:
            return board_item
    return None


def load_project():
    if PROJECT_CACHE_FILE.exists():
        return json.loads(PROJECT_CACHE_FILE.read_text())
    data = run_graphql(PROJECT_QUERY, {"organization": ORGANIZATION, "number": PROJECT_NUMBER})
    project_data = data["organization"]["projectV2"]
    project = {
        "project_id": project_data["id"],
        "status_field_id": project_data["field"]["id"],
        "status_options": {option["name"]: option["id"] for option in project_data["field"]["options"]},
    }
    write_atomically(PROJECT_CACHE_FILE, json.dumps(project, ensure_ascii=False))
    return project


def move_card(task_key, status_name):
    board_item = find_item(task_key) or find_item(task_key, refresh=True)
    if not board_item:
        print("no card for %s" % task_key)
        return EXIT_NOT_FOUND
    project = load_project()
    if status_name not in project["status_options"]:
        PROJECT_CACHE_FILE.unlink(missing_ok=True)
        project = load_project()
    if status_name not in project["status_options"]:
        print("unknown status %r; options: %s" % (status_name, ", ".join(project["status_options"])))
        return 2
    run_graphql(MOVE_MUTATION, {"project": project["project_id"], "item": board_item["item_id"],
                                "field": project["status_field_id"],
                                "option": project["status_options"][status_name]})
    ITEMS_CACHE_FILE.unlink(missing_ok=True)
    print("%s: %s -> %s" % (task_key, board_item["status"], status_name))
    return 0


def read_option(arguments, option_name):
    if option_name in arguments:
        return arguments[arguments.index(option_name) + 1]
    return None


def main():
    arguments = sys.argv[1:]
    command = arguments[0] if arguments else ""
    refresh = "--refresh" in arguments

    if command == "items":
        status_filter = read_option(arguments, "--status")
        board_items = [board_item for board_item in load_items(refresh)
                       if status_filter is None or board_item["status"] == status_filter]
        print(json.dumps(board_items, ensure_ascii=False, indent=1))
        return
    if command == "find" and len(arguments) >= 2:
        board_item = find_item(arguments[1], refresh)
        if not board_item:
            print("no card for %s" % arguments[1])
            sys.exit(EXIT_NOT_FOUND)
        print(json.dumps(board_item, ensure_ascii=False))
        return
    if command == "move" and len(arguments) == 3:
        sys.exit(move_card(arguments[1], arguments[2]))
    print(__doc__, file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
