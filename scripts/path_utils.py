"""
Path and package helpers driven by config.json (Plan B).
Single source of truth: path segment and package prefix come from config only.

Also hosts small shared helpers used by the registration scripts to edit Kotlin
DI files in place (insert an import, register a `singleOf(::X)` line).
"""

import re
import sys

DEFAULT_CONFIG_PATH = "config.json"

# Kotlin generic container types that are invalid as a bare field type — they
# require `<...>` type arguments. A bare one almost always means the shell ate
# the `<...>` of an unquoted argument (e.g. `coverUrls:List<String>` → `List`).
GENERIC_CONTAINER_TYPES = {
    "List", "MutableList", "Set", "MutableSet", "Map", "MutableMap",
    "Collection", "MutableCollection", "Iterable", "Sequence",
    "Array", "ArrayList", "HashMap", "HashSet", "LinkedHashMap", "LinkedHashSet",
    "Pair", "Triple",
}


def check_field_type(field_name: str, field_type: str) -> None:
    """Fail fast when a field type is a bare generic container with no type argument.

    This usually means an unquoted `List<String>` had its `<...>` eaten by the
    shell (`<` / `>` are redirection operators). Exits non-zero with guidance.
    """
    bare = field_type.rstrip("?").strip()
    if bare in GENERIC_CONTAINER_TYPES:
        print(
            f"[!] Error: field '{field_name}' has type '{field_type}', a generic container "
            f"with no type argument.\n"
            f"    The shell most likely stripped the '<...>' from an unquoted argument.\n"
            f"    Quote the whole field, e.g. '{field_name}:{bare}<String>', "
            f"or HTML-escape it: {field_name}:{bare}&lt;String&gt;",
            file=sys.stderr,
        )
        sys.exit(1)


def insert_import(content: str, import_statement: str) -> str:
    """Return `content` with `import <import_statement>` added after the last import.

    No-op if the import is already present. Falls back to inserting right after the
    `package` line when the file has no imports yet.
    """
    import_line = f"import {import_statement}"
    if import_line in content:
        return content
    lines = content.splitlines(keepends=True)
    insert_at = None
    for i, line in enumerate(lines):
        if line.strip().startswith("import "):
            insert_at = i + 1
    if insert_at is None:
        for i, line in enumerate(lines):
            if line.strip().startswith("package "):
                insert_at = i + 1
                break
    if insert_at is None:
        insert_at = 0
    lines.insert(insert_at, import_line + "\n")
    return "".join(lines)


def register_in_koin_module(content: str, registration_line: str) -> str:
    """Return `content` with `registration_line` inserted inside the top-level
    `module { ... }` block, just before its closing brace.

    No-op if the registration is already present. Returns `content` unchanged when
    no `module { ... }` block is found — callers should detect that and fall back.
    """
    reg = registration_line.strip()
    if reg in content:
        return content
    lines = content.splitlines(keepends=True)
    module_idx = None
    for i, line in enumerate(lines):
        if re.search(r"\bmodule\s*\{", line):
            module_idx = i
            break
    if module_idx is None:
        return content
    brace = 0
    seen_open = False
    close_idx = None
    for i in range(module_idx, len(lines)):
        brace += lines[i].count("{") - lines[i].count("}")
        if "{" in lines[i]:
            seen_open = True
        if seen_open and brace == 0:
            close_idx = i
            break
    if close_idx is None:
        return content
    lines.insert(close_idx, f"    {reg}\n")
    return "".join(lines)


def is_shared(feature_name: str) -> bool:
    """True when feature_name is the shared layer."""
    return feature_name.lower() == "shared"


def get_path_segment(config: dict, feature_name: str) -> str:
    """
    First path segment under base_path.
    Shared: config["shared_root"] (default "shared").
    Feature: config["feature_root"]/feature_name (e.g. feature/login).
    """
    if is_shared(feature_name):
        return config.get("shared_root", "shared")
    return f"{config.get('feature_root', 'feature')}/{feature_name}"


def get_package_prefix(config: dict, feature_name: str) -> str:
    """
    Full package prefix (no trailing dot), prepended with config["base_package"] when set.
    This is the single source of truth for package prefixes — every generator and the
    layer scaffolds build on it, so they stay consistent for any base_package.
    Shared:  [base_package.]config["shared_root"]                 (default "shared")
    Feature: [base_package.]config["feature_root"].feature_name   (e.g. feature.login)
    """
    base_package = config.get("base_package", "")
    if is_shared(feature_name):
        layer = config.get("shared_root", "shared")
    else:
        layer = f"{config.get('feature_root', 'feature')}.{feature_name}"
    return f"{base_package}.{layer}" if base_package else layer
