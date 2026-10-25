#!/usr/bin/env python3
"""Turns proof recordings into still frames and contact sheets for the independent UI review.

Usage: proof_frames.py <video or image or directory>... --out DIR [--interval 2] [--columns 4] [--rows 3] [--sheet-width 360]
For each video it writes full-size frames (`frames/<video>/frame-<second>s.jpg`, one every <interval> seconds)
and contact sheets (`sheets/<video>-sheet-<n>.jpg`, <columns> x <rows> frames each). Images are copied as they are.
Prints a JSON manifest: the files the reviewer should open, sheets first, then the frames of each sheet.
The originals stay untouched and remain the PR evidence.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

VIDEO_EXTENSIONS = (".mp4", ".webm", ".mov")
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg")
DEFAULT_INTERVAL_SECONDS = 2.0
MINIMUM_INTERVAL_SECONDS = 0.1
JPEG_QUALITY = "3"


def frame_times(duration_seconds, interval_seconds):
    """Seconds at which frames are taken: 0, interval, 2*interval, ... and always one near the end."""
    if interval_seconds < MINIMUM_INTERVAL_SECONDS:
        raise ValueError("interval must be at least %s seconds" % MINIMUM_INTERVAL_SECONDS)
    if duration_seconds <= 0:
        return []
    times = []
    step_index = 0
    while step_index * interval_seconds < duration_seconds:
        times.append(round(step_index * interval_seconds, 3))
        step_index += 1
    last_time = round(max(duration_seconds - 0.1, 0), 3)
    if last_time - times[-1] >= interval_seconds / 2:
        times.append(last_time)
    return times


def split_into_sheets(times, frames_per_sheet):
    return [times[start:start + frames_per_sheet] for start in range(0, len(times), frames_per_sheet)]


def frame_name(second):
    return "frame-%06.1fs.jpg" % second


def collect_inputs(paths):
    for path in paths:
        if os.path.isdir(path):
            for directory, _, file_names in os.walk(path):
                for file_name in sorted(file_names):
                    if file_name.lower().endswith(VIDEO_EXTENSIONS + IMAGE_EXTENSIONS):
                        yield os.path.join(directory, file_name)
        elif path.lower().endswith(VIDEO_EXTENSIONS + IMAGE_EXTENSIONS):
            yield path


def video_duration(video_path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video_path],
        check=True, capture_output=True, text=True,
    )
    return float(result.stdout.strip())


def extract_frame(video_path, second, target_path):
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-ss", str(second), "-i", video_path, "-frames:v", "1", "-q:v", JPEG_QUALITY, target_path],
        check=True, capture_output=True,
    )


def build_sheet(frame_paths, columns, rows, sheet_width, target_path):
    if len(frame_paths) == 1:
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", frame_paths[0], "-vf", "scale=%d:-1" % sheet_width, "-frames:v", "1", "-q:v", JPEG_QUALITY, target_path],
            check=True, capture_output=True,
        )
        return
    command = ["ffmpeg", "-y", "-v", "error"]
    for frame_path in frame_paths:
        command += ["-i", frame_path]
    inputs = "".join("[%d:v]scale=%d:-1[s%d];" % (index, sheet_width, index) for index in range(len(frame_paths)))
    stacked = "".join("[s%d]" % index for index in range(len(frame_paths)))
    filter_graph = inputs + stacked + "xstack=inputs=%d:layout=%s:fill=black" % (len(frame_paths), xstack_layout(len(frame_paths), columns))
    command += ["-filter_complex", filter_graph, "-frames:v", "1", "-q:v", JPEG_QUALITY, target_path]
    subprocess.run(command, check=True, capture_output=True)


def xstack_layout(frame_count, columns):
    """Pixel positions for ffmpeg's xstack, assuming every cell is as wide as the first one."""
    positions = []
    for index in range(frame_count):
        column = index % columns
        row = index // columns
        x_part = "0" if column == 0 else "+".join("w0" for _ in range(column))
        y_part = "0" if row == 0 else "+".join("h0" for _ in range(row))
        positions.append("%s_%s" % (x_part, y_part))
    return "|".join(positions)


def process_video(video_path, output_directory, interval, columns, rows, sheet_width, number):
    name = "%d-%s" % (number, os.path.splitext(os.path.basename(video_path))[0])
    frames_directory = os.path.join(output_directory, "frames", name)
    sheets_directory = os.path.join(output_directory, "sheets")
    os.makedirs(frames_directory, exist_ok=True)
    os.makedirs(sheets_directory, exist_ok=True)
    duration = video_duration(video_path)
    times = frame_times(duration, interval)
    frame_paths = {}
    for second in times:
        target_path = os.path.join(frames_directory, frame_name(second))
        extract_frame(video_path, second, target_path)
        frame_paths[second] = target_path
    sheets = []
    for sheet_index, sheet_times in enumerate(split_into_sheets(times, columns * rows), start=1):
        sheet_path = os.path.join(sheets_directory, "%s-sheet-%d.jpg" % (name, sheet_index))
        build_sheet([frame_paths[second] for second in sheet_times], columns, rows, sheet_width, sheet_path)
        sheets.append({"path": sheet_path, "seconds": sheet_times})
    return {
        "video": video_path,
        "duration_seconds": round(duration, 1),
        "interval_seconds": interval,
        "sheets": sheets,
        "frames": [{"second": second, "path": frame_paths[second]} for second in times],
    }


def copy_image(image_path, output_directory, number):
    images_directory = os.path.join(output_directory, "images")
    os.makedirs(images_directory, exist_ok=True)
    target_path = os.path.join(images_directory, "%d-%s" % (number, os.path.basename(image_path)))
    shutil.copyfile(image_path, target_path)
    return {"image": image_path, "path": target_path}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--out", required=True)
    parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL_SECONDS)
    parser.add_argument("--columns", type=int, default=4)
    parser.add_argument("--rows", type=int, default=3)
    parser.add_argument("--sheet-width", type=int, default=360)
    arguments = parser.parse_args()
    if arguments.interval < MINIMUM_INTERVAL_SECONDS:
        parser.error("--interval must be at least %s seconds" % MINIMUM_INTERVAL_SECONDS)
    inputs = list(collect_inputs(arguments.paths))
    if not inputs:
        print("no videos or images found", file=sys.stderr)
        sys.exit(1)
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        print("ffmpeg and ffprobe are required", file=sys.stderr)
        sys.exit(2)
    manifest = {"videos": [], "images": []}
    for number, input_path in enumerate(inputs, start=1):
        if input_path.lower().endswith(VIDEO_EXTENSIONS):
            manifest["videos"].append(process_video(
                input_path, arguments.out, arguments.interval, arguments.columns, arguments.rows, arguments.sheet_width, number))
        else:
            manifest["images"].append(copy_image(input_path, arguments.out, number))
    print(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    main()
