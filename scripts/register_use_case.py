#!/usr/bin/env python3
"""
Register use case in domain DI module.

Options:
    --shared               Target shared layer instead of feature layer
    --feature-root <root>  Root folder (feature or shared)

Usage:
    python scripts/register_use_case.py <feature> <UseCaseName> [--shared]

Examples:
    python scripts/register_use_case.py notifications GetNotificationsUseCase
    python scripts/register_use_case.py products FetchProductsUseCase
    
    # Register multiple at once
    python scripts/register_use_case.py notifications GetNotificationsUseCase MarkAsReadUseCase DeleteNotificationUseCase
    
    # Target shared layer
    python scripts/register_use_case.py shared GetSomethingUseCase --shared
"""

import os
import sys
import json
from pathlib import Path
from typing import Set, Optional

from path_utils import (
    DEFAULT_CONFIG_PATH,
    get_package_prefix,
    get_path_segment,
    insert_import,
    is_shared,
    register_in_koin_module,
)


def load_config(config_path: str = None) -> dict:
    """Load configuration from JSON file."""
    path = config_path or DEFAULT_CONFIG_PATH
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            "base_path": "composeApp/src/commonMain/kotlin",
            "base_package": "",
            "feature_root": "feature",
            "shared_root": "shared",
        }


def to_pascal_case(text: str) -> str:
    """Convert text to PascalCase."""
    return ''.join(word.capitalize() for word in text.split('_'))


def print_instructions(target_path: str, import_statement: str, registration_line: str) -> None:
    """Fallback: print Target Path + Code when the file can't be edited in place."""
    print(f"\n[+] Use Case Registration Instructions")
    print()
    print("Target Path:")
    print(f"  {target_path}")
    print()
    print("Code:")
    print(f"  import {import_statement}")
    print()
    print(f"  {registration_line}")


def register_use_case(feature_name: str, use_case_name: str, config: dict, project_root: Optional[Path] = None) -> bool:
    """Register a use case in the domain DI module by editing the module file in place.

    Inserts `import …` and `singleOf(::UseCase)` idempotently, then writes the file.
    Falls back to printing instructions when the module file (or its `module { }`
    block) cannot be found.
    """
    feature_name_pascal = to_pascal_case(feature_name)
    path_segment = get_path_segment(config, feature_name)
    package_prefix = get_package_prefix(config, feature_name)
    base_path_str = config.get("base_path", "composeApp/src/commonMain/kotlin")
    use_case_package = f"{package_prefix}.domain.usecase"

    if is_shared(feature_name):
        rel_path = f"{path_segment}/domain/di/SharedDomainModule.kt"
    else:
        rel_path = f"{path_segment}/domain/di/{feature_name_pascal}DomainModule.kt"

    base_dir = (project_root if project_root is not None else Path.cwd()) / base_path_str
    target_file = base_dir / rel_path

    import_statement = f"{use_case_package}.{use_case_name}"
    registration_line = f"singleOf(::{use_case_name})"

    if not target_file.exists():
        print(f"[!] Domain DI module not found at {target_file}", file=sys.stderr)
        print(f"[!] Generate the domain layer first, or apply these manually:", file=sys.stderr)
        print_instructions(str(target_file), import_statement, registration_line)
        return False

    content = target_file.read_text(encoding='utf-8')
    updated = insert_import(content, import_statement)
    updated = register_in_koin_module(updated, registration_line)

    if registration_line not in updated:
        print(f"[!] Could not find a `module {{ }}` block in {target_file}", file=sys.stderr)
        print_instructions(str(target_file), import_statement, registration_line)
        return False

    if updated == content:
        print(f"[*] {use_case_name} already registered in {target_file} (no change)")
        return True

    target_file.write_text(updated, encoding='utf-8')
    print(f"[+] Registered {use_case_name} in {target_file}")
    return True


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    
    feature_name = sys.argv[1]
    use_case_names = []
    feature_root_override = None
    project_root = None
    i = 2
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == '--shared':
            feature_root_override = 'shared'
            i += 1
        elif arg == '--feature-root':
            if i + 1 < len(sys.argv):
                feature_root_override = sys.argv[i + 1]
                i += 2
            else:
                print("[!] Error: --feature-root requires a value (e.g., shared)")
                sys.exit(1)
        elif arg == '--project-root':
            if i + 1 < len(sys.argv):
                project_root = Path(sys.argv[i + 1]).resolve()
                i += 2
            else:
                print("[!] Error: --project-root requires a path")
                sys.exit(1)
        else:
            use_case_names.append(arg)
            i += 1
    
    config = load_config()
    if feature_root_override:
        config["feature_root"] = feature_root_override

    all_ok = True
    for use_case_name in use_case_names:
        if not register_use_case(feature_name, use_case_name, config, project_root):
            all_ok = False

    if not all_ok:
        sys.exit(1)


if __name__ == "__main__":
    main()

