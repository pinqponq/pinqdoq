#!/usr/bin/env python3
"""
Add a string resource to the project's Compose Multiplatform resources.

Usage:
  python scripts/add_string_resource.py <feature_or_shared> <string_key> "<value>" [--lang tr|en] [--project-root <abs_path>]

Behavior:
  - For feature == "shared": key becomes: shared_<string_key>
  - Otherwise: key becomes: <feature>_feat_<string_key>
  - Updates the appropriate strings.xml based on --lang (default: tr)
  - If key exists, updates its value; otherwise appends a new <string> before </resources>
"""

import argparse
from pathlib import Path
import re
import sys


def build_key(feature: str, raw_key: str) -> str:
    feature = feature.strip().lower()
    if feature == "shared":
        return f"shared_{raw_key.strip().lower()}"
    return f"{feature}_feat_{raw_key.strip().lower()}"


def get_strings_file(project_root: Path, lang: str) -> Path:
    base = project_root / "composeApp" / "src" / "commonMain" / "composeResources"
    if lang == "en":
        return base / "values-en" / "strings.xml"
    return base / "values" / "strings.xml"


def ensure_file_exists(path: Path):
    if not path.exists():
        sys.stderr.write(f"[!] strings file not found: {path}\n")
        sys.exit(1)


def escape_xml(text: str) -> str:
    # minimal XML escape for content
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
    )


def upsert_string(strings_path: Path, key: str, value: str) -> bool:
    """Returns True if file modified, False otherwise."""
    original = strings_path.read_text(encoding="utf-8")

    # Regex to find an existing <string name="key">...</string>
    pattern = re.compile(rf"(<string\\s+name=\"{re.escape(key)}\">)(.*?)(</string>)", re.DOTALL)
    if pattern.search(original):
        new_content = pattern.sub(rf"\\1{escape_xml(value)}\\3", original)
        if new_content != original:
            strings_path.write_text(new_content, encoding="utf-8")
            return True
        return False

    # Append before </resources>, preserve indentation similar to file (4 spaces)
    insertion = f"    <string name=\"{key}\">{escape_xml(value)}</string>\n"
    if "</resources>" not in original:
        raise RuntimeError("Invalid strings.xml: missing </resources>")
    new_content = original.replace("</resources>", insertion + "</resources>")
    strings_path.write_text(new_content, encoding="utf-8")
    return True


def main():
    parser = argparse.ArgumentParser(description="Add/update a string resource")
    parser.add_argument("feature", help="feature name or 'shared'")
    parser.add_argument("key", help="string key without prefixes")
    parser.add_argument("value", help="string value to set")
    parser.add_argument("--lang", choices=["tr", "en"], default="tr")
    parser.add_argument("--project-root", default=str(Path.cwd()))

    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    key = build_key(args.feature, args.key)
    strings_file = get_strings_file(project_root, args.lang)

    ensure_file_exists(strings_file)
    modified = upsert_string(strings_file, key, args.value)
    if modified:
        print(f"[+] Updated {strings_file}: {key}")
    else:
        print(f"[*] No changes needed for {key} in {strings_file}")


if __name__ == "__main__":
    main()




