#!/usr/bin/env python3
"""Makes reduced copies of screenshots for reading, so full-resolution images never enter the context.

Usage: shrink_images.py <image or directory>... [--max-side 800] [--out DIR]
Copies go to <out> (default: a `_small/` folder next to each image) as JPEG; prints one path per line.
The originals stay untouched and remain the PR evidence.
"""
import argparse, os, subprocess, sys

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg")
DEFAULT_MAX_SIDE = 800
JPEG_QUALITY = "60"


def collect_images(paths):
    for path in paths:
        if os.path.isdir(path):
            for directory, _, file_names in os.walk(path):
                if os.path.basename(directory) == "_small":
                    continue
                for file_name in sorted(file_names):
                    if file_name.lower().endswith(IMAGE_EXTENSIONS):
                        yield os.path.join(directory, file_name)
        elif path.lower().endswith(IMAGE_EXTENSIONS):
            yield path


def shrink(image_path, max_side, output_directory):
    target_directory = output_directory or os.path.join(os.path.dirname(image_path), "_small")
    os.makedirs(target_directory, exist_ok=True)
    target_path = os.path.join(target_directory, os.path.splitext(os.path.basename(image_path))[0] + ".jpg")
    is_up_to_date = os.path.exists(target_path) and os.path.getmtime(target_path) >= os.path.getmtime(image_path)
    if not is_up_to_date:
        subprocess.run(
            ["sips", "-Z", str(max_side), "-s", "format", "jpeg", "-s", "formatOptions", JPEG_QUALITY, image_path, "--out", target_path],
            check=True, capture_output=True,
        )
    return target_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--max-side", type=int, default=DEFAULT_MAX_SIDE)
    parser.add_argument("--out")
    arguments = parser.parse_args()
    images = list(collect_images(arguments.paths))
    if not images:
        print("no images found", file=sys.stderr)
        sys.exit(1)
    for image_path in images:
        print(shrink(image_path, arguments.max_side, arguments.out))


if __name__ == "__main__":
    main()
