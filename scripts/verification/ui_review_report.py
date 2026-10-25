#!/usr/bin/env python3
"""Reads the reply of the pin-ui-review agent and decides whether a UI pull request may be opened.

Usage:
  ui_review_report.py gate <reply file> --round <1..3>     prints JSON; exit 0 = no major defect, 1 = fix, record again and review again,
                                                           2 = the reply is malformed (ask the reviewer again), 3 = major defects after the last round
  ui_review_report.py section <reply file> --round <n>     prints the pull request section "UI inceleme"

Reply format (see runner/agents/pin-ui-review.md):
  CHECKED:
  - ICONS: ok | defect | not-shown — <what was looked at>
  ... one line for every check id below ...
  DEFECTS: none
  or
  DEFECTS:
  - [major|minor] <frame> — <what is wrong> (check: <ID>)
"""
import argparse
import json
import re
import sys

CHECK_IDS = (
    "ICONS", "COLOURS", "TOUCH_TARGETS", "CONTRAST", "RAW_DATA", "PLACEHOLDER_DATA", "STATES",
    "PREVIEWS", "TEXT_FIT", "SPACING", "CONSISTENCY", "THEMES", "TEXT_SIZE",
)
RESULTS = ("ok", "defect", "not-shown")
MAX_ROUNDS = 3
MINIMUM_NOTE_WORDS = 3

CHECK_LINE = re.compile(r"^\s*[-*]\s*([A-Z_]+)\s*:\s*(ok|defect|not-shown)\s*[—–-]+\s*(.*\S)\s*$")
DEFECT_LINE = re.compile(r"^\s*[-*]\s*\[(major|minor)\]\s*(.+?)\s*[—–]\s*(.+?)\s*\(check:\s*([A-Z_]+)\)\s*$")
CODE_FENCE = re.compile(r"^\s*```")


def parse_reply(text):
    problems = []
    checks = {}
    defects = []
    section = None
    defects_none = False
    for line in text.splitlines():
        stripped = line.strip()
        if CODE_FENCE.match(line):
            continue
        if re.match(r"^CHECKED:\s*$", stripped):
            section = "checked"
            continue
        defects_header = re.match(r"^DEFECTS:\s*(.*)$", stripped)
        if defects_header:
            section = "defects"
            defects_none = defects_header.group(1).strip().lower() == "none"
            continue
        if not stripped:
            continue
        if section == "checked":
            match = CHECK_LINE.match(line)
            if not match:
                problems.append("unreadable check line: %s" % stripped)
                continue
            check_id, result, note = match.groups()
            if check_id not in CHECK_IDS:
                problems.append("unknown check id: %s" % check_id)
            elif check_id in checks:
                problems.append("check listed twice: %s" % check_id)
            elif len(note.split()) < MINIMUM_NOTE_WORDS:
                problems.append("check %s has no description of what was looked at" % check_id)
            else:
                checks[check_id] = {"result": result, "note": note}
        elif section == "defects":
            match = DEFECT_LINE.match(line)
            if not match:
                problems.append("unreadable defect line: %s" % stripped)
                continue
            severity, frame, description, check_id = match.groups()
            if check_id not in CHECK_IDS:
                problems.append("defect names an unknown check id: %s" % check_id)
                continue
            defects.append({"severity": severity, "frame": frame, "description": description, "check": check_id})
    if "CHECKED:" not in text:
        problems.append("CHECKED section is missing")
    for check_id in CHECK_IDS:
        if check_id not in checks:
            problems.append("check not listed: %s" % check_id)
    if "DEFECTS:" not in text:
        problems.append("DEFECTS section is missing")
    if defects_none and defects:
        problems.append("DEFECTS says none but defects are listed")
    if not defects_none and not defects and "DEFECTS:" in text:
        problems.append("DEFECTS is empty; write 'DEFECTS: none' when nothing is wrong")
    for check_id, check in checks.items():
        has_defect_for_check = any(defect["check"] == check_id for defect in defects)
        if check["result"] == "defect" and not has_defect_for_check:
            problems.append("check %s is marked defect but no defect names it" % check_id)
        if check["result"] == "ok" and has_defect_for_check:
            problems.append("check %s is marked ok but a defect names it" % check_id)
    return {"checks": checks, "defects": defects, "problems": problems}


def decide(parsed, round_number):
    if parsed["problems"]:
        return "malformed", 2
    has_major = any(defect["severity"] == "major" for defect in parsed["defects"])
    if not has_major:
        return "pass", 0
    if round_number >= MAX_ROUNDS:
        return "open_defects", 3
    return "fix_and_review_again", 1


def render_section(parsed, round_number, decision):
    majors = [defect for defect in parsed["defects"] if defect["severity"] == "major"]
    minors = [defect for defect in parsed["defects"] if defect["severity"] == "minor"]
    not_shown = [check_id for check_id, check in parsed["checks"].items() if check["result"] == "not-shown"]
    lines = ["## UI inceleme"]
    if decision == "open_defects":
        lines.append("⚠️ %d tur sonunda %d büyük kusur açık kaldı; karar sahibe bırakıldı (❓)." % (round_number, len(majors)))
    else:
        lines.append("Bağımsız inceleme (pin-ui-review), tur %d: büyük %d, küçük %d." % (round_number, len(majors), len(minors)))
    if parsed["defects"]:
        lines += ["", "| Önem | Kare | Sorun | Kontrol |", "|---|---|---|---|"]
        for defect in majors + minors:
            lines.append("| %s | %s | %s | %s |" % tuple(
                cell.replace("|", "\\|") for cell in (defect["severity"], defect["frame"], defect["description"], defect["check"])))
    lines.append("")
    lines.append("Bakılan kontroller: %d/%d." % (len(parsed["checks"]), len(CHECK_IDS)))
    if not_shown:
        lines.append("Kanıtta görünmeyen: %s." % ", ".join(not_shown))
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("gate", "section"))
    parser.add_argument("reply_file")
    parser.add_argument("--round", type=int, required=True, dest="round_number")
    arguments = parser.parse_args()
    with open(arguments.reply_file, encoding="utf-8") as reply_file:
        parsed = parse_reply(reply_file.read())
    decision, exit_code = decide(parsed, arguments.round_number)
    if arguments.command == "section":
        if decision == "malformed":
            print("reply is malformed: " + "; ".join(parsed["problems"]), file=sys.stderr)
            sys.exit(2)
        print(render_section(parsed, arguments.round_number, decision))
        return
    print(json.dumps({
        "decision": decision,
        "round": arguments.round_number,
        "major": sum(1 for defect in parsed["defects"] if defect["severity"] == "major"),
        "minor": sum(1 for defect in parsed["defects"] if defect["severity"] == "minor"),
        "problems": parsed["problems"],
        "defects": parsed["defects"],
    }, indent=1, ensure_ascii=False))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
