#!/usr/bin/env python3
"""
Turn a product template (kmp-app-template or a backend template) into a new product.

The template carries a `template.json` manifest at its root; the product is described
by a JSON file. The script copies the template, replaces the placeholder identity
(app name, package, bundle id, API base URL) in file contents and paths, writes keys,
removes modules the product does not use, sets theme colors in Color.kt and fails if
any placeholder is left. Stdlib only, no network except `git clone` of the template.

Usage:
    python scripts/new_product.py --template <dir|git url> --product <product.json> --destination <dir> [--dry-run]

Examples:
    python scripts/new_product.py --template ../kmp-app-template --product lumo.json --destination ../lumo-cmp
    python scripts/new_product.py --template https://github.com/pinqponq/kmp-app-template.git --product lumo.json --destination /tmp/lumo --dry-run

Manifest format and product file format: references/templates/new-product-starter.md
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Set

MANIFEST_NAME = "template.json"
GITIGNORE_NAME = ".gitignore"
EXIT_CODE_ERROR = 2
IDENTITY_FIELDS = ("app_name", "package", "bundle_id", "api_base_url")
APP_NAME_PATTERN = re.compile(r"^[A-Z][A-Za-z0-9]{1,29}$")
PACKAGE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")
BUNDLE_ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9-]*(\.[A-Za-z][A-Za-z0-9-]*)+$")
URL_PATTERN = re.compile(r"^https://[^\s\"']+/$")
KEY_NAME_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")
HEX_COLOR_PATTERN = re.compile(r"^#([0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$")
MARKER_PATTERN = re.compile(r"template:([a-z0-9_-]+):(start|end)")
SKIPPED_DIRECTORIES = {".git", ".gradle", "build", ".idea", "bin", "obj", "node_modules"}

INVALID_PRODUCT = "INVALID_PRODUCT"
INVALID_MANIFEST = "INVALID_MANIFEST"
MISSING_FIELDS = "MISSING_FIELDS"
INVALID_FIELD = "INVALID_FIELD"
MISSING_KEYS = "MISSING_KEYS"
UNKNOWN_KEYS = "UNKNOWN_KEYS"
UNKNOWN_MODULES = "UNKNOWN_MODULES"
INVALID_COLOR = "INVALID_COLOR"
UNCLOSED_MARKER = "UNCLOSED_MARKER"
TEMPLATE_UNAVAILABLE = "TEMPLATE_UNAVAILABLE"
INVALID_DESTINATION = "INVALID_DESTINATION"
PATH_CONFLICT = "PATH_CONFLICT"
SECRET_NOT_IGNORED = "SECRET_NOT_IGNORED"
THEME_FILE_MISSING = "THEME_FILE_MISSING"
UNKNOWN_THEME_TOKEN = "UNKNOWN_THEME_TOKEN"
PLACEHOLDERS_LEFT = "PLACEHOLDERS_LEFT"
FILE_SYSTEM_ERROR = "FILE_SYSTEM_ERROR"


class StarterError(Exception):
    def __init__(self, error_code: str, message: str, how_to_fix: str, missing_fields: Optional[List[str]] = None):
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.how_to_fix = how_to_fix
        self.missing_fields = missing_fields or []

    def to_dict(self) -> dict:
        return {
            "error_code": self.error_code,
            "message": self.message,
            "missing_fields": self.missing_fields,
            "how_to_fix": self.how_to_fix,
        }


def load_json(path: Path, error_code: str) -> dict:
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise StarterError(error_code, f"{path} not found", "Pass an existing file")
    except json.JSONDecodeError as exception:
        raise StarterError(error_code, f"{path} is not valid JSON: {exception}", "Fix the JSON syntax")
    if not isinstance(content, dict):
        raise StarterError(error_code, f"{path} is not a JSON object", "Use the object format from the reference")
    return content


def validate_product(product: dict, manifest: dict) -> None:
    missing = [field for field in IDENTITY_FIELDS if not product.get(field)]
    if missing:
        raise StarterError(MISSING_FIELDS, f"Product is missing {', '.join(missing)}", "Add the fields to the product file", missing)
    checks = (
        ("app_name", APP_NAME_PATTERN, "PascalCase letters and digits, 2-30 characters"),
        ("package", PACKAGE_PATTERN, "lowercase dotted package such as com.deveng.lumo"),
        ("bundle_id", BUNDLE_ID_PATTERN, "dotted bundle id such as com.deveng.lumo.Lumo"),
        ("api_base_url", URL_PATTERN, "https URL ending with /"),
    )
    for field, pattern, expected in checks:
        value = product[field]
        if not isinstance(value, str) or not pattern.match(value):
            raise StarterError(INVALID_FIELD, f"{field} '{value}' is invalid", f"Use a {expected}")

    keys = product.get("keys", {})
    key_specs = manifest.get("keys", {})
    missing_keys = [name for name, key_spec in key_specs.items() if key_spec.get("required", True) and not keys.get(name)]
    if missing_keys:
        raise StarterError(MISSING_KEYS, f"Product is missing keys {', '.join(missing_keys)}", "Add them under \"keys\"", missing_keys)
    unknown_keys = sorted(set(keys) - set(key_specs))
    if unknown_keys:
        raise StarterError(UNKNOWN_KEYS, f"Template has no keys {', '.join(unknown_keys)}", "Remove them or add them to template.json")
    non_text_keys = sorted(name for name, value in keys.items() if not isinstance(value, str))
    if non_text_keys:
        raise StarterError(INVALID_FIELD, f"Keys {', '.join(non_text_keys)} are not strings", "Give every key as a string")

    unknown_modules = sorted(set(product.get("modules", {})) - set(manifest.get("modules", {})))
    if unknown_modules:
        raise StarterError(UNKNOWN_MODULES, f"Template has no modules {', '.join(unknown_modules)}", "Use module names from template.json")

    for token, value in product.get("theme", {}).items():
        if not HEX_COLOR_PATTERN.match(str(value)):
            raise StarterError(INVALID_COLOR, f"Theme color {token} '{value}' is invalid", "Use #RRGGBB or #AARRGGBB")


def validate_manifest(manifest: dict) -> None:
    placeholders = manifest.get("placeholders", {})
    missing = [field for field in IDENTITY_FIELDS if not placeholders.get(field)]
    if missing:
        raise StarterError(INVALID_MANIFEST, f"template.json placeholders miss {', '.join(missing)}", "Add every identity placeholder", missing)
    for name, key_spec in manifest.get("keys", {}).items():
        if not KEY_NAME_PATTERN.match(name):
            raise StarterError(INVALID_MANIFEST, f"Key name '{name}' is invalid", "Use UPPER_SNAKE_CASE key names")
        if key_spec.get("secret") and not key_spec.get("file"):
            raise StarterError(INVALID_MANIFEST, f"Secret key {name} has no file", "Give secret keys a gitignored properties file")


def validate_package_move(manifest: dict, product: dict) -> None:
    template_package = manifest["placeholders"]["package"]
    if product["package"].startswith(template_package + "."):
        raise StarterError(PATH_CONFLICT, f"{product['package']} is inside the template package", "Use a package outside the template package")


def identity_replacements(placeholders: dict, product: dict) -> List[tuple]:
    pairs = [(placeholders[field], product[field]) for field in IDENTITY_FIELDS]
    pairs.append((placeholders["app_name"].lower(), product["app_name"].lower()))
    pairs.append((placeholders["package"].replace(".", "/"), product["package"].replace(".", "/")))
    return sorted(pairs, key=lambda pair: len(pair[0]), reverse=True)


def apply_replacements(text: str, pairs: List[tuple]) -> str:
    pattern = re.compile("|".join(re.escape(old) for old, _ in pairs))
    lookup = dict(pairs)
    return pattern.sub(lambda match: lookup[match.group(0)], text)


def strip_module_blocks(text: str, kept: Dict[str, bool]) -> str:
    lines = text.splitlines(keepends=True)
    result = []
    removing: List[str] = []
    for line in lines:
        marker = MARKER_PATTERN.search(line)
        if marker:
            module, edge = marker.group(1), marker.group(2)
            if edge == "start" and not kept.get(module, True):
                removing.append(module)
            elif edge == "end" and removing and removing[-1] == module:
                removing.pop()
            continue
        if not removing:
            result.append(line)
    if removing:
        raise StarterError(UNCLOSED_MARKER, f"template:{removing[-1]}:start has no end marker", "Close the block in the template")
    return "".join(result)


def read_text(path: Path) -> Optional[str]:
    data = path.read_bytes()
    if b"\0" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def iter_files(root: Path):
    for path in sorted(root.rglob("*")):
        if path.is_file():
            yield path


def fetch_template(template: str, work_directory: Path) -> Path:
    if template.startswith(("https://", "git@")):
        target = work_directory / "template"
        completed = subprocess.run(
            ["git", "clone", "--depth", "1", "--quiet", template, str(target)],
            capture_output=True, text=True,
        )
        if completed.returncode != 0:
            raise StarterError(TEMPLATE_UNAVAILABLE, f"git clone failed: {completed.stderr.strip()}", "Check the URL and access")
        return target
    path = Path(template).expanduser()
    if not (path / MANIFEST_NAME).is_file():
        raise StarterError(TEMPLATE_UNAVAILABLE, f"{path} has no {MANIFEST_NAME}", "Point --template at a template repo root")
    return path


def check_destination(destination: Path) -> None:
    if destination.exists() and not destination.is_dir():
        raise StarterError(INVALID_DESTINATION, f"{destination} is a file", "Choose a new or empty directory")
    if destination.exists() and any(destination.iterdir()):
        raise StarterError(INVALID_DESTINATION, f"{destination} is not empty", "Choose a new or empty directory")


def secret_files(manifest: dict) -> Set[str]:
    return {key_spec["file"] for key_spec in manifest.get("keys", {}).values() if key_spec.get("secret")}


def copy_template(source: Path, staging: Path, manifest: dict) -> None:
    excluded = {source / relative for relative in secret_files(manifest)}

    def ignore(directory: str, names: List[str]) -> Set[str]:
        return {name for name in names if name in SKIPPED_DIRECTORIES or Path(directory) / name in excluded}

    shutil.copytree(source, staging, ignore=ignore)


def remove_modules(root: Path, manifest: dict, kept: Dict[str, bool]) -> List[str]:
    removed = []
    for module, module_spec in manifest.get("modules", {}).items():
        if kept[module]:
            continue
        for relative in module_spec.get("paths", []):
            target = root / relative
            if target.is_dir():
                shutil.rmtree(target)
            elif target.exists():
                target.unlink()
        removed.append(module)
    return removed


def rename_paths(root: Path, pairs: List[tuple]) -> int:
    renamed = 0
    for old, new in [(old, new) for old, new in pairs if "/" in old]:
        for source in sorted(root.rglob(old.split("/")[-1])):
            if not source.is_dir() or not source.as_posix().endswith("/" + old):
                continue
            target = Path(source.as_posix()[: -len(old)] + new)
            if target.exists():
                raise StarterError(PATH_CONFLICT, f"{target.relative_to(root)} already exists", "Use a package that is not in the template")
            shutil.move(str(source), str(target))
            prune_empty_parents(source.parent, root)
            renamed += 1
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        new_name = apply_replacements(path.name, pairs)
        if new_name != path.name:
            path.rename(path.with_name(new_name))
            renamed += 1
    return renamed


def prune_empty_parents(path: Path, root: Path) -> None:
    while path != root and path.is_dir() and not any(path.iterdir()):
        path.rmdir()
        path = path.parent


def write_keys(root: Path, manifest: dict, keys: dict) -> List[str]:
    written = []
    secret_lines: Dict[str, List[str]] = {}
    for name, key_spec in manifest.get("keys", {}).items():
        if name not in keys:
            continue
        if key_spec.get("secret"):
            secret_lines.setdefault(key_spec["file"], []).append(f"{name}={keys[name]}\n")
        written.append(name)
    for relative, lines in secret_lines.items():
        if not is_gitignored(root, relative):
            raise StarterError(SECRET_NOT_IGNORED, f"{relative} is not in .gitignore", "Add it to the template's .gitignore")
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("".join(lines), encoding="utf-8")
    return written


def is_gitignored(root: Path, relative: str) -> bool:
    gitignore = root / GITIGNORE_NAME
    if not gitignore.is_file():
        return False
    with tempfile.TemporaryDirectory() as repository:
        shutil.copy(gitignore, Path(repository) / GITIGNORE_NAME)
        subprocess.run(["git", "init", "--quiet", repository], check=True, capture_output=True)
        completed = subprocess.run(
            ["git", "-C", repository, "check-ignore", "--quiet", "--no-index", relative],
            capture_output=True,
        )
    return completed.returncode == 0


def public_key_pairs(manifest: dict, keys: dict) -> List[tuple]:
    return [
        (f"__{name}__", keys.get(name, ""))
        for name, key_spec in manifest.get("keys", {}).items()
        if not key_spec.get("secret")
    ]


def set_theme(root: Path, manifest: dict, theme: dict, pairs: List[tuple]) -> List[str]:
    if not theme:
        return []
    theme_file_name = manifest.get("theme_file")
    if theme_file_name is None:
        raise StarterError(THEME_FILE_MISSING, "template.json has no theme_file", "Set theme_file to Color.kt")
    theme_file = root / apply_replacements(theme_file_name, pairs)
    if not theme_file.is_file():
        raise StarterError(THEME_FILE_MISSING, f"{theme_file_name} does not exist", "Point theme_file at Color.kt")
    text = theme_file.read_text(encoding="utf-8")
    for token, value in theme.items():
        pattern = re.compile(rf"(val {re.escape(token)} = Color\(0x)[0-9A-Fa-f]{{8}}(\))")
        if not pattern.search(text):
            raise StarterError(UNKNOWN_THEME_TOKEN, f"{token} is not defined in {theme_file_name}", "Use a token from Color.kt")
        hex_value = value.lstrip("#").upper()
        argb = hex_value if len(hex_value) == 8 else "FF" + hex_value
        text = pattern.sub(rf"\g<1>{argb}\g<2>", text)
    theme_file.write_text(text, encoding="utf-8")
    return sorted(theme)


def find_leftovers(root: Path, manifest: dict) -> List[str]:
    tokens = [manifest["placeholders"][field] for field in IDENTITY_FIELDS]
    tokens += [f"__{name}__" for name in manifest.get("keys", {})]
    leftovers = []
    for path in iter_files(root):
        relative = path.relative_to(root).as_posix()
        text = read_text(path) or ""
        for token in tokens:
            if token in relative or token in text:
                leftovers.append(f"{relative}: {token}")
    return leftovers


def generate(template: str, product_path: Path, destination: Path, dry_run: bool = False) -> dict:
    product = load_json(product_path, INVALID_PRODUCT)
    check_destination(destination)
    with tempfile.TemporaryDirectory() as work_directory:
        source = fetch_template(template, Path(work_directory))
        manifest = load_json(source / MANIFEST_NAME, INVALID_MANIFEST)
        validate_manifest(manifest)
        validate_product(product, manifest)
        validate_package_move(manifest, product)

        staging = Path(work_directory) / "product"
        copy_template(source, staging, manifest)
        kept = {module: bool(product.get("modules", {}).get(module, module_spec.get("default", True)))
                for module, module_spec in manifest.get("modules", {}).items()}
        removed = remove_modules(staging, manifest, kept)

        keys = product.get("keys", {})
        pairs = identity_replacements(manifest["placeholders"], product) + public_key_pairs(manifest, keys)
        changed = 0
        for path in iter_files(staging):
            text = read_text(path)
            if text is None:
                continue
            updated = apply_replacements(strip_module_blocks(text, kept), pairs)
            if updated != text:
                path.write_text(updated, encoding="utf-8")
                changed += 1
        renamed = rename_paths(staging, pairs)
        written = write_keys(staging, manifest, keys)
        theme_tokens = set_theme(staging, manifest, product.get("theme", {}), pairs)
        (staging / MANIFEST_NAME).unlink()

        leftovers = find_leftovers(staging, manifest)
        if leftovers:
            raise StarterError(PLACEHOLDERS_LEFT, "; ".join(leftovers[:20]), "Add the missing values or fix the template")
        if not dry_run:
            shutil.copytree(staging, destination, dirs_exist_ok=True)

    return {
        "destination": str(destination),
        "dry_run": dry_run,
        "files_changed": changed,
        "paths_renamed": renamed,
        "modules_removed": removed,
        "keys_written": written,
        "theme_tokens": theme_tokens,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Create a new product from a pinqponq template.")
    parser.add_argument("--template", required=True, help="template directory or git URL")
    parser.add_argument("--product", required=True, help="product JSON file")
    parser.add_argument("--destination", required=True, help="new, empty output directory")
    parser.add_argument("--dry-run", action="store_true", help="validate and report without writing --destination")
    args = parser.parse_args(argv)
    try:
        result = generate(args.template, Path(args.product).expanduser(), Path(args.destination).expanduser(), args.dry_run)
    except StarterError as error:
        print(json.dumps(error.to_dict(), indent=1))
        return EXIT_CODE_ERROR
    except OSError as error:
        failure = StarterError(FILE_SYSTEM_ERROR, str(error), "Check the paths and permissions, then run again")
        print(json.dumps(failure.to_dict(), indent=1))
        return EXIT_CODE_ERROR
    print(json.dumps(result, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
