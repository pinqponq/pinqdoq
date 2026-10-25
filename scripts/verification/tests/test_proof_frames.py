import contextlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import proof_frames  # noqa: E402

HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


class FrameTimesTest(unittest.TestCase):
    def test_takes_a_frame_every_interval_starting_at_zero(self):
        self.assertEqual([0, 2, 4, 6], proof_frames.frame_times(7.0, 2))

    def test_adds_a_frame_near_the_end_when_the_last_interval_is_long(self):
        self.assertEqual([0, 2, 4, 6, 7.9], proof_frames.frame_times(8.0, 2))
        self.assertEqual([0, 2, 4, 5.9], proof_frames.frame_times(6.0, 2))

    def test_a_short_video_still_gets_its_first_frame(self):
        self.assertEqual([0], proof_frames.frame_times(1.0, 2))

    def test_empty_video_has_no_frames(self):
        self.assertEqual([], proof_frames.frame_times(0, 2))


class SheetsTest(unittest.TestCase):
    def test_splits_times_into_sheets_of_the_given_size(self):
        self.assertEqual([[0, 2, 4], [6, 8]], proof_frames.split_into_sheets([0, 2, 4, 6, 8], 3))

    def test_no_times_make_no_sheets(self):
        self.assertEqual([], proof_frames.split_into_sheets([], 12))

    def test_xstack_layout_places_cells_row_by_row(self):
        self.assertEqual("0_0|w0_0|0_h0|w0_h0|0_h0+h0", proof_frames.xstack_layout(5, 2))

    def test_frame_names_sort_by_time(self):
        self.assertLess(proof_frames.frame_name(2.0), proof_frames.frame_name(10.0))


class CollectInputsTest(unittest.TestCase):
    def test_collects_videos_and_images_from_a_directory_and_skips_other_files(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in ("a.mp4", "b.png", "c.txt", "d.WEBM"):
                (Path(directory) / name).write_bytes(b"")
            names = sorted(Path(path).name for path in proof_frames.collect_inputs([directory]))
        self.assertEqual(["a.mp4", "b.png", "d.WEBM"], names)


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg is not installed")
class EndToEndTest(unittest.TestCase):
    def make_video(self, directory, seconds):
        video_path = str(Path(directory) / "proof.mp4")
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=270x480:rate=10", "-t", str(seconds),
             "-pix_fmt", "yuv420p", video_path],
            check=True,
        )
        return video_path

    def test_writes_frames_and_a_contact_sheet_and_prints_a_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            video_path = self.make_video(directory, 7)
            image_path = Path(directory) / "shot.png"
            image_path.write_bytes(b"png")
            output = Path(directory) / "out"
            captured = io.StringIO()
            arguments = ["proof_frames.py", video_path, str(image_path), "--out", str(output), "--interval", "2", "--columns", "2", "--rows", "1"]
            with mock.patch.object(sys, "argv", arguments), contextlib.redirect_stdout(captured):
                proof_frames.main()
            manifest = json.loads(captured.getvalue())
            video = manifest["videos"][0]
            self.assertEqual([0, 2, 4, 6], [frame["second"] for frame in video["frames"]])
            self.assertEqual(2, len(video["sheets"]))
            self.assertEqual([[0, 2], [4, 6]], [sheet["seconds"] for sheet in video["sheets"]])
            for frame in video["frames"]:
                self.assertTrue(Path(frame["path"]).stat().st_size > 0)
            for sheet in video["sheets"]:
                self.assertTrue(Path(sheet["path"]).stat().st_size > 0)
            self.assertTrue(Path(manifest["images"][0]["path"]).exists())

    def test_exits_1_when_nothing_to_process(self):
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(sys, "argv", ["proof_frames.py", directory, "--out", directory]):
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                    proof_frames.main()
        self.assertEqual(1, raised.exception.code)


if __name__ == "__main__":
    unittest.main()
