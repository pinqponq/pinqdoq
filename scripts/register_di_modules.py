#!/usr/bin/env python3
"""
Register DI modules in initKoin.kt.

Usage:
    python scripts/register_di_modules.py <feature_name> [--project-root <path>]

Options:
    --project-root <path>   Load config from <path>/config.json (for correct initKoin_path when server runs from another directory)

Examples:
    # Register all 3 modules for a feature
    python scripts/register_di_modules.py orders
    
    # With app project root (e.g. when MCP server runs from different directory)
    python scripts/register_di_modules.py orders --project-root /path/to/app
    
    # Registers:
    # - ordersDomainModule
    # - ordersDataModule  
    # - ordersPresentationModule
"""

import os
import sys
import json
import re
from pathlib import Path
from typing import List, Tuple, Optional

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
            config = json.load(f)
            if "initKoin_path" not in config:
                config["initKoin_path"] = None
            return config
    except FileNotFoundError:
        return {
            "base_path": "composeApp/src/commonMain/kotlin",
            "base_package": "",
            "feature_root": "feature",
            "shared_root": "shared",
            "initKoin_path": None,
        }


def get_config_path(project_root: Optional[Path] = None) -> str:
    """Resolve config path: under project_root if given, else default (cwd-relative)."""
    if project_root is not None:
        return str(project_root / "Mobile" / "scripts" / "config.json")
    return DEFAULT_CONFIG_PATH


def to_pascal_case(text: str) -> str:
    """Convert text to PascalCase."""
    return ''.join(word.capitalize() for word in text.split('_'))


def to_camel_case(text: str) -> str:
    """Convert text to camelCase."""
    pascal = to_pascal_case(text)
    return pascal[0].lower() + pascal[1:] if pascal else ""


def get_feature_modules(feature_name: str, config: dict) -> List[Tuple[str, str]]:
    """
    Get list of modules to register for a feature.
    Returns: [(module_name, import_path), ...]
    Path and package from config (shared_root / feature_root + feature_name).
    """
    package_prefix = get_package_prefix(config, feature_name)
    feature_name_lower = feature_name.lower()
    feature_name_camel = to_camel_case(feature_name)

    if is_shared(feature_name):
        domain_module_name = "sharedDomainModule"
        data_module_name = "sharedDataModule"
        presentation_module_name = "sharedPresentationModule"
    else:
        domain_module_name = f"{feature_name_camel}DomainModule"
        data_module_name = f"{feature_name_camel}DataModule"
        presentation_module_name = f"{feature_name_camel}PresentationModule"

    domain_import = f"{package_prefix}.domain.di.{domain_module_name}"
    data_import = f"{package_prefix}.data.di.{data_module_name}"
    presentation_import = f"{package_prefix}.presentation.di.{presentation_module_name}"

    return [
        (domain_module_name, domain_import),
        (data_module_name, data_import),
        (presentation_module_name, presentation_import),
    ]


def import_exists(lines: List[str], import_statement: str) -> bool:
    """Check if import already exists in file."""
    import_line = f"import {import_statement}"
    return any(import_line in line for line in lines)


def module_registered(lines: List[str], module_name: str) -> bool:
    """Check if module is already registered in modules() call."""
    # Look for module_name followed by optional comma, in the modules section
    pattern = rf'\b{re.escape(module_name)}\b\s*,?'
    return any(re.search(pattern, line) for line in lines)


def add_imports(lines: List[str], imports: List[str]) -> List[str]:
    """Add imports to file in alphabetical order."""
    # Find the import section
    first_import_idx = -1
    last_import_idx = -1
    
    for i, line in enumerate(lines):
        if line.strip().startswith('import '):
            if first_import_idx == -1:
                first_import_idx = i
            last_import_idx = i
    
    if first_import_idx == -1:
        print("[!] Error: Could not find import section in initKoin.kt")
        return lines
    
    # Collect existing imports
    existing_imports = []
    for i in range(first_import_idx, last_import_idx + 1):
        line = lines[i].strip()
        if line.startswith('import '):
            import_statement = line.replace('import ', '').strip()
            existing_imports.append(import_statement)
    
    # Add new imports
    new_imports_added = []
    for import_statement in imports:
        if not import_exists(lines, import_statement):
            existing_imports.append(import_statement)
            new_imports_added.append(import_statement)
    
    # Sort all imports
    existing_imports.sort()
    
    # Rebuild import section
    new_lines = lines[:first_import_idx]
    for imp in existing_imports:
        new_lines.append(f"import {imp}\n")
    new_lines.extend(lines[last_import_idx + 1:])
    
    if new_imports_added:
        print(f"[+] Added {len(new_imports_added)} import(s):")
        for imp in new_imports_added:
            print(f"    import {imp}")
    
    return new_lines


def add_modules_to_registration(lines: List[str], modules: List[str]) -> List[str]:
    """Add modules to modules() call in alphabetical order."""
    # Find the modules() call
    modules_start_idx = -1
    modules_end_idx = -1
    
    for i, line in enumerate(lines):
        if 'modules(' in line:
            modules_start_idx = i
            # Find the closing parenthesis
            brace_count = line.count('(') - line.count(')')
            j = i + 1
            while j < len(lines) and brace_count > 0:
                brace_count += lines[j].count('(') - lines[j].count(')')
                if brace_count == 0:
                    modules_end_idx = j
                    break
                j += 1
            break
    
    if modules_start_idx == -1 or modules_end_idx == -1:
        print("[!] Error: Could not find modules() call in initKoin.kt")
        return lines
    
    # Extract existing module registrations
    existing_modules = []
    for i in range(modules_start_idx + 1, modules_end_idx):
        line = lines[i].strip()
        if line and not line.startswith('//'):
            # Extract module name (remove comma and whitespace)
            module_name = line.rstrip(',').strip()
            if module_name and module_name != ')':
                existing_modules.append(module_name)
    
    # Add new modules (check only within existing_modules, not all lines)
    new_modules_added = []
    for module_name in modules:
        if module_name not in existing_modules:
            existing_modules.append(module_name)
            new_modules_added.append(module_name)
    
    # Sort all modules
    existing_modules.sort()
    
    # Rebuild modules section
    new_lines = lines[:modules_start_idx + 1]
    for module in existing_modules:
        new_lines.append(f"            {module},\n")
    # Remove trailing comma from last module
    if new_lines[-1].endswith(',\n'):
        new_lines[-1] = new_lines[-1].rstrip(',\n') + '\n'
    new_lines.extend(lines[modules_end_idx:])
    
    if new_modules_added:
        print(f"[+] Registered {len(new_modules_added)} module(s) in modules():")
        for module in new_modules_added:
            print(f"    {module}")
    
    return new_lines




def print_instructions(target_path: str, import_statements: List[str], module_names: List[str]) -> None:
    """Fallback: print Target Path + Code when initKoin.kt can't be edited in place."""
    if import_statements:
        print("Target Path:")
        print(f"  {target_path}")
        print()
        print("Code:")
        for imp in sorted(import_statements):
            print(f"  import {imp}")
        print()
    if module_names:
        print("Target Path:")
        print(f"  {target_path}")
        print()
        print("Code:")
        for module in sorted(module_names):
            print(f"  {module},")


def register_di_modules(feature_name: str, config: dict, project_root: Optional[Path] = None) -> None:
    """Register DI modules for a feature in initKoin.kt."""
    try:
        modules_info = get_feature_modules(feature_name, config)
        # When project_root is set, only include modules whose di file exists (skip presentation if not generated)
        if project_root is not None:
            base_path_str = config.get("base_path", "composeApp/src/commonMain/kotlin")
            path_segment = get_path_segment(config, feature_name)
            base = Path(project_root)
            for part in base_path_str.split("/"):
                base = base / part
            feature_camel = to_camel_case(feature_name)
            existing = []
            for name, import_path in modules_info:
                if "Domain" in name:
                    p = base / path_segment / "domain" / "di" / f"{feature_camel}DomainModule.kt"
                elif "Data" in name:
                    p = base / path_segment / "data" / "di" / f"{feature_camel}DataModule.kt"
                else:
                    p = base / path_segment / "presentation" / "di" / f"{feature_camel}PresentationModule.kt"
                if p.exists():
                    existing.append((name, import_path))
            if existing:
                modules_info = existing
        module_names = [name for name, _ in modules_info]
        import_statements = [imp for _, imp in modules_info]

        # Resolve the initKoin.kt path: (project_root or cwd) / base_path / initKoin_path.
        # initKoin_path in config is relative to base_path (see README config sample).
        base_path_str = config.get("base_path", "composeApp/src/commonMain/kotlin")
        init_koin_rel = config.get("initKoin_path") or "core/data/di/initKoin.kt"
        base_dir = (project_root if project_root is not None else Path.cwd()) / base_path_str
        target_file = base_dir / init_koin_rel

        if not target_file.exists():
            print(f"[!] initKoin file not found at {target_file}", file=sys.stderr)
            print(f"[!] Set initKoin_path in config.json, or apply these manually:", file=sys.stderr)
            print_instructions(str(target_file), import_statements, module_names)
            return

        lines = target_file.read_text(encoding='utf-8').splitlines(keepends=True)
        original = "".join(lines)
        lines = add_imports(lines, import_statements)
        lines = add_modules_to_registration(lines, module_names)
        updated = "".join(lines)

        if updated == original:
            print(f"[*] All modules already registered in {target_file} (no change)")
        else:
            target_file.write_text(updated, encoding='utf-8')
            print(f"[+] Updated {target_file}")
    except Exception as e:
        import traceback
        error_msg = f"[!] Error in register_di_modules: {str(e)}\n"
        error_msg += f"Traceback:\n{traceback.format_exc()}"
        print(error_msg, file=sys.stderr)
        sys.exit(1)


def main():
    try:
        if len(sys.argv) < 2:
            print(__doc__)
            sys.exit(1)
        
        feature_name = sys.argv[1]
        project_root = None
        
        # Parse --project-root if present
        args = sys.argv[2:]
        i = 0
        while i < len(args):
            if args[i] == "--project-root" and i + 1 < len(args):
                project_root = Path(args[i + 1]).resolve()
                i += 2
            else:
                i += 1
        
        # Load config (from project_root when set; if that path doesn't exist, use server config so we have base_path/initKoin_path)
        config_path = get_config_path(project_root)
        if project_root is not None and not os.path.isfile(config_path):
            config_path = DEFAULT_CONFIG_PATH
        config = load_config(config_path)

        # Register DI modules
        register_di_modules(feature_name, config, project_root)
    except Exception as e:
        import traceback
        error_msg = f"[!] Fatal error: {str(e)}\n"
        error_msg += f"Traceback:\n{traceback.format_exc()}"
        print(error_msg, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

