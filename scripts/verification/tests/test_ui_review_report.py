import contextlib
import io
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ui_review_report  # noqa: E402


def checked_block(overrides=None):
    overrides = overrides or {}
    lines = ["CHECKED:"]
    for check_id in ui_review_report.CHECK_IDS:
        result, note = overrides.get(check_id, ("ok", "looked at every frame of the sheet"))
        lines.append("- %s: %s — %s" % (check_id, result, note))
    return "\n".join(lines)


def reply(defects_block, overrides=None):
    return checked_block(overrides) + "\n" + defects_block + "\n"


MAJOR = "- [major] chat-02-picker — attach menu is flat pure blue, not a theme colour (check: COLOURS)"
MINOR = "- [minor] chat-05-uploaded — gap above the bubble is larger than elsewhere (check: SPACING)"
COLOURS_DEFECT = {"COLOURS": ("defect", "menu background does not match the theme")}
SPACING_DEFECT = {"SPACING": ("defect", "bubble gap differs from the other rows")}


class ParseReplyTest(unittest.TestCase):
    def test_clean_reply_has_no_problems_and_no_defects(self):
        parsed = ui_review_report.parse_reply(reply("DEFECTS: none"))
        self.assertEqual([], parsed["problems"])
        self.assertEqual([], parsed["defects"])
        self.assertEqual(len(ui_review_report.CHECK_IDS), len(parsed["checks"]))

    def test_defect_lines_are_read_with_severity_frame_text_and_check(self):
        parsed = ui_review_report.parse_reply(reply("DEFECTS:\n" + MAJOR, COLOURS_DEFECT))
        self.assertEqual([], parsed["problems"])
        self.assertEqual(
            [{"severity": "major", "frame": "chat-02-picker",
              "description": "attach menu is flat pure blue, not a theme colour", "check": "COLOURS"}],
            parsed["defects"],
        )

    def test_missing_check_is_a_problem(self):
        text = reply("DEFECTS: none").replace("- ICONS: ok — looked at every frame of the sheet\n", "")
        self.assertIn("check not listed: ICONS", ui_review_report.parse_reply(text)["problems"])

    def test_looks_fine_without_a_checked_list_is_malformed(self):
        parsed = ui_review_report.parse_reply("Looks fine to me.\nDEFECTS: none\n")
        self.assertIn("CHECKED section is missing", parsed["problems"])

    def test_ok_without_a_description_is_a_problem(self):
        parsed = ui_review_report.parse_reply(reply("DEFECTS: none", {"ICONS": ("ok", "fine")}))
        self.assertIn("check ICONS has no description of what was looked at", parsed["problems"])

    def test_unknown_and_repeated_check_ids_are_problems(self):
        unknown = ui_review_report.parse_reply(checked_block() + "\n- SOUND: ok — listened to the video track\nDEFECTS: none\n")
        self.assertIn("unknown check id: SOUND", unknown["problems"])
        repeated = ui_review_report.parse_reply(checked_block() + "\n- ICONS: ok — looked again at the icons\nDEFECTS: none\n")
        self.assertIn("check listed twice: ICONS", repeated["problems"])

    def test_defect_mark_and_defect_list_must_agree(self):
        marked_without_defect = ui_review_report.parse_reply(reply("DEFECTS: none", COLOURS_DEFECT))
        self.assertIn("check COLOURS is marked defect but no defect names it", marked_without_defect["problems"])
        defect_on_ok_check = ui_review_report.parse_reply(reply("DEFECTS:\n" + MAJOR))
        self.assertIn("check COLOURS is marked ok but a defect names it", defect_on_ok_check["problems"])

    def test_none_with_listed_defects_and_empty_defects_are_problems(self):
        both = ui_review_report.parse_reply(reply("DEFECTS: none\n" + MAJOR, COLOURS_DEFECT))
        self.assertIn("DEFECTS says none but defects are listed", both["problems"])
        empty = ui_review_report.parse_reply(reply("DEFECTS:"))
        self.assertIn("DEFECTS is empty; write 'DEFECTS: none' when nothing is wrong", empty["problems"])

    def test_missing_defects_section_is_a_problem(self):
        self.assertIn("DEFECTS section is missing", ui_review_report.parse_reply(checked_block())["problems"])

    def test_unreadable_lines_are_problems(self):
        self.assertTrue(any("unreadable defect line" in problem for problem in
                            ui_review_report.parse_reply(reply("DEFECTS:\n- the menu is ugly"))["problems"]))
        self.assertTrue(any("unreadable check line" in problem for problem in
                            ui_review_report.parse_reply(checked_block() + "\nICONS fine\nDEFECTS: none\n")["problems"]))


class CheckIdsStayInSyncTest(unittest.TestCase):
    repository = Path(__file__).resolve().parents[3]

    def test_agent_reply_format_lists_the_parsers_check_ids_in_order(self):
        agent = (self.repository / "runner" / "agents" / "pin-ui-review.md").read_text(encoding="utf-8")
        self.assertEqual(list(ui_review_report.CHECK_IDS), re.findall(r"^- ([A-Z_]+): ", agent, re.M))

    def test_rule_checklist_lists_the_parsers_check_ids_in_order(self):
        rule = (self.repository / "rules" / "ui-proof-review.md").read_text(encoding="utf-8")
        self.assertEqual(list(ui_review_report.CHECK_IDS), re.findall(r"^\| `([A-Z_]+)` ", rule, re.M))


class ReplyShapeTest(unittest.TestCase):
    def test_defect_without_a_check_id_is_a_problem(self):
        parsed = ui_review_report.parse_reply(reply("DEFECTS:\n- [major] frame 2 s — the menu is flat blue"))
        self.assertTrue(any("unreadable defect line" in problem for problem in parsed["problems"]))

    def test_defect_with_an_unknown_check_id_is_a_problem(self):
        parsed = ui_review_report.parse_reply(reply("DEFECTS:\n- [major] frame 2 s — the menu is flat blue (check: SOUND)"))
        self.assertIn("defect names an unknown check id: SOUND", parsed["problems"])

    def test_reply_wrapped_in_a_code_fence_is_read(self):
        parsed = ui_review_report.parse_reply("```\n" + reply("DEFECTS: none") + "```\n")
        self.assertEqual([], parsed["problems"])

    def test_pipes_in_a_description_do_not_break_the_table(self):
        defect = "- [major] frame 2 s — shows a | b in one cell (check: COLOURS)"
        parsed = ui_review_report.parse_reply(reply("DEFECTS:\n" + defect, COLOURS_DEFECT))
        self.assertIn("shows a \\| b in one cell", ui_review_report.render_section(parsed, 1, "fix_and_review_again"))


class DecideTest(unittest.TestCase):
    def parsed(self, defects_block, overrides=None):
        return ui_review_report.parse_reply(reply(defects_block, overrides))

    def test_no_defects_passes(self):
        self.assertEqual(("pass", 0), ui_review_report.decide(self.parsed("DEFECTS: none"), 1))

    def test_minor_defects_alone_pass(self):
        self.assertEqual(("pass", 0), ui_review_report.decide(self.parsed("DEFECTS:\n" + MINOR, SPACING_DEFECT), 1))

    def test_major_defect_means_fix_and_review_again_before_the_last_round(self):
        parsed = self.parsed("DEFECTS:\n" + MAJOR, COLOURS_DEFECT)
        self.assertEqual(("fix_and_review_again", 1), ui_review_report.decide(parsed, 1))
        self.assertEqual(("fix_and_review_again", 1), ui_review_report.decide(parsed, 2))

    def test_major_defect_in_the_third_round_opens_the_pull_request_with_defects(self):
        parsed = self.parsed("DEFECTS:\n" + MAJOR, COLOURS_DEFECT)
        self.assertEqual(("open_defects", 3), ui_review_report.decide(parsed, 3))

    def test_malformed_reply_wins_over_everything(self):
        self.assertEqual(("malformed", 2), ui_review_report.decide(ui_review_report.parse_reply("Looks fine."), 3))


class SectionTest(unittest.TestCase):
    def test_section_lists_majors_before_minors_and_what_was_not_shown(self):
        overrides = dict(COLOURS_DEFECT, **SPACING_DEFECT)
        overrides["THEMES"] = ("not-shown", "only the light theme was recorded")
        parsed = ui_review_report.parse_reply(reply("DEFECTS:\n" + MINOR + "\n" + MAJOR, overrides))
        section = ui_review_report.render_section(parsed, 2, "fix_and_review_again")
        self.assertTrue(section.startswith("## UI inceleme"))
        self.assertLess(section.index("| major |"), section.index("| minor |"))
        self.assertIn("tur 2: büyük 1, küçük 1", section)
        self.assertIn("Kanıtta görünmeyen: THEMES.", section)

    def test_section_marks_open_defects_for_the_owner(self):
        parsed = ui_review_report.parse_reply(reply("DEFECTS:\n" + MAJOR, COLOURS_DEFECT))
        section = ui_review_report.render_section(parsed, 3, "open_defects")
        self.assertIn("3 tur sonunda 1 büyük kusur açık kaldı", section)
        self.assertIn("❓", section)


class CommandLineTest(unittest.TestCase):
    def run_main(self, command, text, round_number):
        with tempfile.TemporaryDirectory() as directory:
            reply_path = Path(directory) / "reply.txt"
            reply_path.write_text(text, encoding="utf-8")
            output = io.StringIO()
            with mock.patch.object(sys, "argv", ["ui_review_report.py", command, str(reply_path), "--round", str(round_number)]):
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as raised:
                        ui_review_report.main()
        return raised.exception.code, output.getvalue()

    def test_gate_prints_json_and_exits_1_for_a_major_defect(self):
        code, output = self.run_main("gate", reply("DEFECTS:\n" + MAJOR, COLOURS_DEFECT), 1)
        self.assertEqual(1, code)
        self.assertEqual(1, json.loads(output)["major"])

    def test_gate_exits_0_when_clean(self):
        self.assertEqual(0, self.run_main("gate", reply("DEFECTS: none"), 1)[0])

    def test_gate_exits_3_after_the_last_round(self):
        self.assertEqual(3, self.run_main("gate", reply("DEFECTS:\n" + MAJOR, COLOURS_DEFECT), 3)[0])

    def test_section_of_a_malformed_reply_exits_2(self):
        self.assertEqual(2, self.run_main("section", "Looks fine.", 1)[0])


if __name__ == "__main__":
    unittest.main()
