#!/usr/bin/env python3
"""
Add method to domain repository interface.

Options:
    --returns <Type>       Return type (default: Unit)
    --project-root <path>  Ignored when run from CLI (used by MCP to pass project root; skip to avoid consuming path as parameter)
    --shared               Target shared layer instead of feature layer
    --entity <name>        When --shared: use this for repository class name (e.g. DashboardUser -> DashboardUserRepository.kt)
    --feature-root <root>  Root folder (feature or shared)

Usage:
    python scripts/add_repository_method.py <feature> <method_name> [parameters...] [--returns <return_type>] [--shared]

Examples:
    # Method with parameters and return type
    python scripts/add_repository_method.py notifications getNotifications userId:Int page:Int --returns Notifications
    
    # Method with no return (Unit)
    python scripts/add_repository_method.py notifications markAsRead notificationId:Int
    
    # Method with no parameters
    python scripts/add_repository_method.py notifications getAllNotifications --returns List<Notification>
    
    # Target shared layer
    python scripts/add_repository_method.py shared getSomething id:String --returns Something --shared
"""

import os
import sys
import json
import re
from pathlib import Path
from typing import List, Tuple, Optional, Set

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


def parse_parameters(params: List[str]) -> List[Tuple[str, str]]:
    """Parse parameter strings in format 'name:Type'."""
    parameters = []
    for param in params:
        if ':' in param:
            name, type_str = param.split(':', 1)
            parameters.append((name.strip(), type_str.strip()))
    return parameters


def extract_type_name(type_str: str) -> str:
    """Extract the base type name from a type string (e.g., 'List<Product>' -> 'Product')."""
    # Handle List<T>, Map<K,V>, etc.
    generic_match = re.search(r'<(.+)>', type_str)
    if generic_match:
        inner_types = generic_match.group(1)
        # Split by comma but respect nested generics
        types = []
        depth = 0
        current = []
        for char in inner_types:
            if char == '<':
                depth += 1
                current.append(char)
            elif char == '>':
                depth -= 1
                current.append(char)
            elif char == ',' and depth == 0:
                types.append(''.join(current).strip())
                current = []
            else:
                current.append(char)
        if current:
            types.append(''.join(current).strip())
        
        # Return all non-primitive types
        result = []
        for t in types:
            t = t.replace('?', '').strip()
            if t and not is_primitive_type(t):
                result.extend(extract_type_name(t).split(','))
        return ','.join(result) if result else ''
    
    # Remove nullable marker
    base_type = type_str.replace('?', '').strip()
    
    # If it's a primitive type, return empty
    if is_primitive_type(base_type):
        return ''
    
    return base_type


def is_primitive_type(type_str: str) -> bool:
    """Check if type is a Kotlin primitive or standard library type."""
    primitives = {
        'Int', 'Long', 'Double', 'Float', 'Boolean', 'String', 'Unit',
        'Byte', 'Short', 'Char', 'Any', 'Nothing'
    }
    return type_str in primitives



def add_method_to_repository(
    feature_name: str,
    method_name: str,
    parameters: List[Tuple[str, str]],
    return_type: Optional[str],
    config: dict,
    entity_name: Optional[str] = None
) -> None:
    """Add a method to the repository interface."""
    feature_name_pascal = to_pascal_case(feature_name)
    # When feature is shared and entity_name is set, use it for the repository class/file name
    if is_shared(feature_name) and entity_name:
        class_name_pascal = to_pascal_case(entity_name)
    else:
        class_name_pascal = feature_name_pascal
    package_prefix = get_package_prefix(config, feature_name)

    base_package = f"{package_prefix}.domain.repository"
    model_package = f"{package_prefix}.domain.model"
    
    # Collect types that need imports
    types_to_import = set()
    
    # Check return type
    if return_type and return_type != 'Unit':
        extracted_types = extract_type_name(return_type)
        if extracted_types:
            for t in extracted_types.split(','):
                if t:
                    types_to_import.add(t)
    
    # Check parameter types
    for param_name, param_type in parameters:
        extracted_types = extract_type_name(param_type)
        if extracted_types:
            for t in extracted_types.split(','):
                if t:
                    types_to_import.add(t)
    
    # Build imports (no file reading - output all needed imports)
    new_imports = []
    for type_name in sorted(types_to_import):
        import_line = f"import {model_package}.{type_name}"
        new_imports.append(import_line)
    
    # Build method signature
    param_str = ", ".join([f"{name}: {type_str}" for name, type_str in parameters])
    return_str = f": {return_type}" if return_type and return_type != 'Unit' else ""
    method_signature = f"    suspend fun {method_name}({param_str}){return_str}"
    
    # Output instructions instead of modifying file
    print(f"\n[+] Repository Method Addition Instructions")
    print()

    base_path_str = config.get("base_path", "composeApp/src/commonMain/kotlin")
    path_segment = get_path_segment(config, feature_name)
    target_path = f"{base_path_str}/{path_segment}/domain/repository/{class_name_pascal}Repository.kt"
    
    if new_imports:
        print("Target Path:")
        print(f"  {target_path}")
        print()
        print("Code:")
        for imp in sorted(new_imports):
            print(f"  {imp}")
        print()
    
    print("Target Path:")
    print(f"  {target_path}")
    print()
    print("Code:")
    print(f"  {method_signature.strip()}")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    
    feature_name = sys.argv[1]
    method_name = sys.argv[2]
    
    # Parse arguments
    args = sys.argv[3:]
    return_type = None
    parameters = []
    feature_root_override = None
    entity_name = None
    project_root = None

    i = 0
    while i < len(args):
        arg = args[i]
        if arg == '--returns':
            if i + 1 < len(args):
                return_type = args[i + 1]
                i += 2
            else:
                print("[!] Error: --returns requires a type argument")
                sys.exit(1)
        elif arg == '--project-root':
            if i + 1 < len(args):
                project_root = args[i + 1]
                i += 2
            else:
                i += 1
        elif arg == '--shared':
            feature_root_override = 'shared'
            i += 1
        elif arg == '--entity':
            if i + 1 < len(args):
                entity_name = args[i + 1]
                i += 2
            else:
                print("[!] Error: --entity requires a value (e.g., DashboardUser)")
                sys.exit(1)
        elif arg == '--feature-root':
            if i + 1 < len(args):
                feature_root_override = args[i + 1]
                i += 2
            else:
                print("[!] Error: --feature-root requires a value (e.g., shared)")
                sys.exit(1)
        elif ':' in arg:
            # Parameter
            parameters.append(arg)
            i += 1
        else:
            i += 1
    
    # Parse parameters
    parsed_params = parse_parameters(parameters)
    
    # Load config
    config = load_config()
    if feature_root_override:
        config["feature_root"] = feature_root_override

    # Add method
    add_method_to_repository(feature_name, method_name, parsed_params, return_type, config, entity_name=entity_name)


if __name__ == "__main__":
    main()

