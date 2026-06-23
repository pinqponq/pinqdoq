#!/usr/bin/env python3
"""
Register screen in navigation system.

Options:
    --params <name:Type ...>    Screen parameters (e.g., orderId:Int productName:String)
    --json-params <name:Type>   Parameters that need JSON serialization (complex types)

Usage:
    python scripts/register_navigation.py <feature_name> <ScreenName> [options]

Examples:
    # Simple screen (no params)
    python scripts/register_navigation.py orders OrdersScreen
    
    # Screen with simple parameters
    python scripts/register_navigation.py orderdetail OrderDetailScreen --params orderId:Int
    
    # Screen with complex JSON parameters
    python scripts/register_navigation.py productedit ProductEditScreen --params productId:Int? --json-params productAction:ProductAction
"""

import os
import sys
import json
import re
from pathlib import Path
from typing import List, Tuple, Optional

from path_utils import DEFAULT_CONFIG_PATH


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


def to_camel_case(text: str) -> str:
    """Convert text to camelCase."""
    pascal = to_pascal_case(text)
    return pascal[0].lower() + pascal[1:] if pascal else ""


def parse_parameters(params: List[str]) -> List[Tuple[str, str]]:
    """Parse parameter strings in format 'name:Type'."""
    parameters = []
    for param in params:
        if ':' in param:
            name, type_str = param.split(':', 1)
            parameters.append((name.strip(), type_str.strip()))
    return parameters


def screen_exists_in_sealed_class(file_path: str, screen_name: str) -> bool:
    """Check if screen already exists in Screen.kt sealed class."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            pattern = rf'\b(data\s+object|data\s+class)\s+{re.escape(screen_name)}\s*'
            return bool(re.search(pattern, content))
    except FileNotFoundError:
        return False


def add_screen_to_sealed_class(
    screen_name: str,
    parameters: List[Tuple[str, str]],
    config: dict
) -> None:
    """Add screen definition to Screen.kt sealed class."""
    base_path = Path(config.get("base_path", "composeApp/src/commonMain/kotlin"))
    screen_file = base_path / "core" / "util" / "Screen.kt"
    
    if not screen_file.exists():
        print(f"[!] Error: Screen.kt not found at {screen_file}")
        sys.exit(1)
    
    # Check if screen already exists
    if screen_exists_in_sealed_class(str(screen_file), screen_name):
        print(f"[*] Screen '{screen_name}' already exists in Screen.kt")
        return
    
    # Read file
    with open(screen_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Generate screen definition
    if parameters:
        # Data class with parameters
        param_list = ",\n        ".join([f"val {name}: {type_}" for name, type_ in parameters])
        screen_def = f"""    @Serializable
    data class {screen_name}(
        {param_list}
    ) : Screen()
"""
    else:
        # Data object (no parameters)
        screen_def = f"""    @Serializable
    data object {screen_name} : Screen()
"""
    
    # Find insertion point (before closing brace of sealed class)
    insert_line = -1
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip() == '}':
            insert_line = i
            break
    
    if insert_line == -1:
        print(f"[!] Error: Could not find closing brace in Screen.kt")
        sys.exit(1)
    
    # Insert screen definition
    lines.insert(insert_line, screen_def + '\n')
    
    # Write back
    with open(screen_file, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print(f"[+] Added {screen_name} to Screen.kt")


def route_exists_in_navigation(file_path: str, screen_name: str) -> bool:
    """Check if screen route already exists in AppNavigation.kt."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            pattern = rf'composable<Screen\.{re.escape(screen_name)}>'
            return bool(re.search(pattern, content))
    except FileNotFoundError:
        return False


def add_screen_import(
    feature_name: str,
    screen_name: str,
    nav_file_path: str
) -> None:
    """Add screen import to AppNavigation.kt."""
    feature_name_lower = feature_name.lower()
    import_line = f"import feature.{feature_name_lower}.presentation.{screen_name}\n"
    
    # Read file
    with open(nav_file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Check if import already exists
    if any(import_line.strip() in line for line in lines):
        return
    
    # Find last feature import
    last_feature_import = -1
    for i, line in enumerate(lines):
        if line.strip().startswith('import feature.'):
            last_feature_import = i
    
    if last_feature_import == -1:
        # Find package declaration
        for i, line in enumerate(lines):
            if line.strip().startswith('package '):
                last_feature_import = i + 1
                break
    
    # Insert import alphabetically
    if last_feature_import != -1:
        # Find correct position alphabetically
        insert_pos = last_feature_import + 1
        for i in range(last_feature_import + 1, len(lines)):
            if not lines[i].strip().startswith('import feature.'):
                break
            if lines[i] > import_line:
                insert_pos = i
                break
            insert_pos = i + 1
        
        lines.insert(insert_pos, import_line)
    
    # Write back
    with open(nav_file_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print(f"[+] Added import for {screen_name} to AppNavigation.kt")


def generate_composable_route(
    screen_name: str,
    parameters: List[Tuple[str, str]],
    json_params: List[Tuple[str, str]]
) -> str:
    """Generate composable route code."""
    
    if not parameters and not json_params:
        # Simple screen with no parameters
        return f"""        composable<Screen.{screen_name}> {{
            {screen_name}(
                navController = navController
            )
        }}
"""
    else:
        # Screen with parameters
        lines = [f"        composable<Screen.{screen_name}> {{ backStackEntry ->"]
        
        # Add parameter extraction
        if parameters or json_params:
            lines.append(f"            val backStack = backStackEntry.toRoute<Screen.{screen_name}>()")
            
            for param_name, param_type in parameters:
                lines.append(f"            val {param_name} = backStack.{param_name}")
            
            for param_name, param_type in json_params:
                lines.append(f"            val {param_name}Json = backStack.{param_name}")
                lines.append(f"            val {param_name} = fromJson<{param_type}>({param_name}Json)")
            
            lines.append("")
        
        # Add screen composable call
        param_list = []
        if parameters or json_params:
            for param_name, _ in parameters + json_params:
                param_list.append(f"{param_name} = {param_name}")
        
        lines.append(f"            {screen_name}(")
        lines.append(f"                navController = navController" + ("," if param_list else ""))
        for i, param in enumerate(param_list):
            comma = "," if i < len(param_list) - 1 else ""
            lines.append(f"                {param}{comma}")
        lines.append("            )")
        lines.append("        }\n")
        
        return "\n".join(lines)


def add_route_to_navigation(
    screen_name: str,
    parameters: List[Tuple[str, str]],
    json_params: List[Tuple[str, str]],
    nav_file_path: str
) -> None:
    """Add composable route to AppNavigation.kt."""
    
    # Check if route already exists
    if route_exists_in_navigation(nav_file_path, screen_name):
        print(f"[*] Route for '{screen_name}' already exists in AppNavigation.kt")
        return
    
    # Read file
    with open(nav_file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Generate route code
    route_code = generate_composable_route(screen_name, parameters, json_params)
    
    # Find insertion point (before closing brace of navGraph)
    insert_line = -1
    brace_count = 0
    in_nav_graph = False
    
    for i, line in enumerate(lines):
        if 'val navGraph = navController.createGraph(' in line:
            in_nav_graph = True
        
        if in_nav_graph:
            brace_count += line.count('{') - line.count('}')
            
            # Find the closing brace of createGraph
            if brace_count == 0 and '}' in line:
                insert_line = i
                break
    
    if insert_line == -1:
        print(f"[!] Error: Could not find insertion point in AppNavigation.kt")
        sys.exit(1)
    
    # Insert route
    lines.insert(insert_line, '\n' + route_code)
    
    # Write back
    with open(nav_file_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print(f"[+] Added composable route for {screen_name} to AppNavigation.kt")


def register_screen_navigation(
    feature_name: str,
    screen_name: str,
    parameters: List[Tuple[str, str]],
    json_params: List[Tuple[str, str]],
    config: dict
) -> None:
    """Register screen in navigation system."""
    base_path = Path(config.get("base_path", "composeApp/src/commonMain/kotlin"))
    
    # Paths
    nav_file = base_path / "feature" / "main" / "presentation" / "AppNavigation.kt"
    
    if not nav_file.exists():
        print(f"[!] Error: AppNavigation.kt not found at {nav_file}")
        sys.exit(1)
    
    # Step 1: Add screen to Screen.kt
    all_params = parameters + [(name, "String") for name, _ in json_params]  # JSON params stored as String
    add_screen_to_sealed_class(screen_name, all_params, config)
    
    # Step 2: Add import to AppNavigation.kt
    add_screen_import(feature_name, screen_name, str(nav_file))
    
    # Step 3: Add route to AppNavigation.kt
    add_route_to_navigation(screen_name, parameters, json_params, str(nav_file))
    
    print(f"\n[+] Successfully registered {screen_name} in navigation!")
    print(f"[>] Screen.kt: Screen.{screen_name}")
    print(f"[>] AppNavigation.kt: composable<Screen.{screen_name}>")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    
    feature_name = sys.argv[1]
    screen_name = sys.argv[2]
    
    # Parse arguments
    args = sys.argv[3:]
    parameters = []
    json_params = []
    
    i = 0
    while i < len(args):
        arg = args[i]
        
        if arg == '--params':
            # Collect all simple parameters
            i += 1
            while i < len(args) and not args[i].startswith('--'):
                if ':' in args[i]:
                    parameters.append(args[i])
                i += 1
        
        elif arg == '--json-params':
            # Collect all JSON parameters
            i += 1
            while i < len(args) and not args[i].startswith('--'):
                if ':' in args[i]:
                    json_params.append(args[i])
                i += 1
        else:
            i += 1
    
    # Parse parameters
    parsed_params = parse_parameters(parameters)
    parsed_json_params = parse_parameters(json_params)
    
    # Load config
    config = load_config()
    
    # Register navigation
    register_screen_navigation(
        feature_name, screen_name,
        parsed_params, parsed_json_params, config
    )


if __name__ == "__main__":
    main()

