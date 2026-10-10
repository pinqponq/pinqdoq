#!/usr/bin/env python3
"""One handoff file per task, so a later session (after a question, a review or a session split)
continues from it instead of re-exploring. Lives outside the worktree, never committed.

Usage:
  handoff.py show <task-key>                      print the handoff (or "no handoff yet")
  handoff.py note <task-key> <section> <text>     add one bullet to a section (duplicates ignored)
  handoff.py set <task-key> <section> < text      replace a section with stdin (one bullet per line)
  handoff.py path <task-key>

Sections: state, decisions, files, verified, assumed, next, questions, resume
  decisions: "<decision> — why: <reason>"   files: "<path:line> — <changed|read>: <note>"
"""
import fcntl, os, re, sys, time

HANDOFF_DIR = os.path.expanduser("~/.claude/pinqloq-task-runner/handoffs")
SECTIONS = {
    "state": "Current state",
    "decisions": "Decisions made (with why)",
    "files": "Files touched / relevant",
    "verified": "Verified",
    "assumed": "Assumed / not confirmed",
    "next": "Next steps",
    "questions": "Open questions / blockers",
    "resume": "How to resume",
}
MAX_BULLET_LENGTH = 400
SECRET_LIKE = re.compile(r"(?i)(password|secret|token|apikey|api_key|otp)\s*[=:]\s*\S+")


def handoff_path(task_key):
    file_name = re.sub(r"[^A-Za-z0-9]+", "_", task_key.replace("pinqponq/", "")).strip("_") + ".md"
    return os.path.join(HANDOFF_DIR, file_name)


def read_sections(path):
    sections = {key: [] for key in SECTIONS}
    if not os.path.exists(path):
        return sections
    titles = {title: key for key, title in SECTIONS.items()}
    current = None
    with open(path) as handoff_file:
        for line in handoff_file:
            line = line.rstrip("\n")
            if line.startswith("## "):
                current = titles.get(line[3:].strip())
            elif current and line.startswith("- "):
                sections[current].append(line[2:])
    return sections


def write_sections(path, task_key, sections):
    lines = [f"# Handoff: {task_key}", f"Updated: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}", ""]
    for key, title in SECTIONS.items():
        lines.append(f"## {title}")
        lines.extend(f"- {bullet}" for bullet in sections[key])
        lines.append("")
    temporary_path = path + ".tmp"
    with open(temporary_path, "w") as handoff_file:
        handoff_file.write("\n".join(lines))
    os.replace(temporary_path, path)


def clean(text):
    return SECRET_LIKE.sub(r"\1=<redacted>", " ".join(text.split()))[:MAX_BULLET_LENGTH]


def main():
    arguments = sys.argv[1:]
    if len(arguments) < 2 or arguments[0] not in ("show", "note", "set", "path"):
        sys.exit(__doc__)
    command, task_key = arguments[0], arguments[1]
    path = handoff_path(task_key)
    if command == "path":
        print(path)
        return
    if command == "show":
        print(open(path).read() if os.path.exists(path) else f"no handoff yet for {task_key}")
        return
    section = arguments[2] if len(arguments) > 2 else ""
    if section not in SECTIONS:
        sys.exit(f"unknown section {section!r}; use one of: {', '.join(SECTIONS)}")
    os.makedirs(HANDOFF_DIR, exist_ok=True)
    with open(path + ".lock", "w") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        sections = read_sections(path)
        if command == "note":
            bullet = clean(" ".join(arguments[3:]))
            if not bullet:
                sys.exit("note text required")
            if bullet not in sections[section]:
                sections[section].append(bullet)
        else:
            sections[section] = [clean(re.sub(r"^\s*[-*] ", "", line)) for line in sys.stdin.read().splitlines() if line.strip()]
        write_sections(path, task_key, sections)
    print(f"handoff {section}: {len(sections[section])} items → {path}")


if __name__ == "__main__":
    main()
