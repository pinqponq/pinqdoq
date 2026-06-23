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
    is_shared,
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


def register_use_case(feature_name: str, use_case_name: str, config: dict, project_root: Optional[Path] = None) -> bool:
    """Register a use case in the domain DI module."""
    feature_name_pascal = to_pascal_case(feature_name)
    path_segment = get_path_segment(config, feature_name)
    package_prefix = get_package_prefix(config, feature_name)
    base_path_str = config.get("base_path", "composeApp/src/commonMain/kotlin")

    use_case_package = f"{package_prefix}.domain.usecase"
    if is_shared(feature_name):
        rel_path = f"{path_segment}/domain/di/SharedDomainModule.kt"
    else:
        rel_path = f"{path_segment}/domain/di/{feature_name_pascal}DomainModule.kt"

    target_path = f"{base_path_str}/{rel_path}" if project_root is not None else rel_path

    import_line = f"import {use_case_package}.{use_case_name}"
    registration_line = f"    singleOf(::{use_case_name})"

    print(f"\n[+] Use Case Registration Instructions")
    print()
    print("Target Path:")
    print(f"  {target_path}")
    print()
    print("Code:")
    print(f"  {import_line}")
    print()
    print(f"  {registration_line}")
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

    registered_count = 0
    for use_case_name in use_case_names:
        if register_use_case(feature_name, use_case_name, config, project_root):
            registered_count += 1
    
    if registered_count > 0:
        print(f"\n[+] Successfully registered {registered_count} use case(s)", file=sys.stderr)


if __name__ == "__main__":
    main()

