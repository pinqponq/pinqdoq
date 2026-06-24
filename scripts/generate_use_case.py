#!/usr/bin/env python3
"""
Generate use case class from repository method.

Options:
    --shared               Target shared layer instead of feature layer
    --feature-root <root>  Root folder (feature or shared)
    --parameters           Method parameters as JSON array
    --return-type          Method return type

Usage:
    python scripts/generate_use_case.py <feature> <UseCaseName> <repository_method> --parameters <json> --return-type <type> [--shared]

Examples:
    # Generate use case for getUserSettings
    python scripts/generate_use_case.py settings GetUserSettingsUseCase getUserSettings --parameters '[{"name":"userId","type":"String"}]' --return-type 'UserSettings'
    
    # Generate use case with multiple parameters
    python scripts/generate_use_case.py shop GetProductsUseCase getProducts --parameters '[{"name":"page","type":"Int"},{"name":"limit","type":"Int"}]' --return-type 'List<Product>'

Note:
    - Requires method signature (parameters and return_type) to be provided
    - Generates invoke operator with same parameters
    - Auto-injects repository dependency
    - Use case name should be in PascalCase (e.g., GetUserSettingsUseCase)
"""

import os
import sys
import json
import re
from pathlib import Path
from typing import List, Tuple

from path_utils import (
    DEFAULT_CONFIG_PATH,
    get_package_prefix,
    get_path_segment,
)


def _parse_parameters(params_str: str) -> List[Tuple[str, str]]:
    """Parse parameters from JSON array or space-separated name:Type pairs. Robust to escaping."""
    if not params_str or not params_str.strip():
        return []
    params_str = params_str.strip().strip('\ufeff')
    # Try JSON array first
    try:
        params_json = json.loads(params_str)
        if isinstance(params_json, list):
            result = []
            for p in params_json:
                if isinstance(p, dict) and "name" in p and "type" in p:
                    result.append((str(p["name"]).strip(), str(p["type"]).strip()))
                elif isinstance(p, str) and ":" in p:
                    name, type_str = p.split(":", 1)
                    result.append((name.strip(), type_str.strip()))
            if result:
                return result
    except (json.JSONDecodeError, TypeError):
        pass
    # Second try: unquoted keys/values (e.g. {name: request, type: LoginDashboardRequest} from PowerShell)
    try:
        normalized = params_str.replace("name:", '"name":').replace("type:", '"type":')
        # Quote unquoted values after "name": and "type":
        normalized = re.sub(r'"name":\s*([^",}\]]+)', r'"name": "\1"', normalized)
        normalized = re.sub(r'"type":\s*([^",}\]]+)', r'"type": "\1"', normalized)
        params_json = json.loads(normalized)
        if isinstance(params_json, list):
            result = []
            for p in params_json:
                if isinstance(p, dict) and "name" in p and "type" in p:
                    result.append((str(p["name"]).strip(), str(p["type"]).strip()))
            if result:
                return result
    except (json.JSONDecodeError, TypeError):
        pass
    # Fallback: space-separated name:Type pairs (skip tokens that look like JSON/list)
    result = []
    for part in params_str.split():
        part = part.strip()
        if part.startswith("[") or part.startswith("{"):
            continue
        if ":" in part:
            name, type_str = part.split(":", 1)
            result.append((name.strip(), type_str.strip()))
    return result


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


# Scalar Kotlin built-ins — never a domain model, in any position.
_SCALAR_BUILTINS = {
    "Unit", "Int", "Long", "Double", "Float", "Boolean", "String", "Char",
    "Byte", "Short", "Any", "Nothing", "Number",
}
# Generic container built-ins — built-in only when used AS a container (`List<...>`).
# As a bare type or a type argument the same name is treated as a domain model,
# so a model named e.g. `Collection` (collides with kotlin.collections.Collection)
# still gets imported.
_CONTAINER_BUILTINS = {
    "List", "MutableList", "Set", "MutableSet", "Map", "MutableMap",
    "Collection", "Iterable", "Sequence", "Array", "Pair", "Triple",
}


def domain_model_types(type_str: str) -> List[str]:
    """Return the non-builtin type names referenced by a return type, in order.

    `List<Collection>` -> ['Collection']; `Collection` -> ['Collection'];
    `Map<String, Collection>` -> ['Collection']; `List<String>` -> [].
    Fully-qualified types (containing '.') are skipped — assumed already importable.
    """
    if '.' in type_str:
        return []
    seen = []
    for match in re.finditer(r'([A-Za-z_][A-Za-z0-9_]*)\s*(<?)', type_str):
        name, opens_generic = match.group(1), match.group(2)
        if name in _SCALAR_BUILTINS:
            continue
        if name in _CONTAINER_BUILTINS and opens_generic == '<':
            continue  # used as a container, e.g. List<...>
        if name not in seen:
            seen.append(name)
    return seen


def generate_use_case(
    feature_name: str,
    use_case_name: str,
    repository_method: str,
    parameters: List[Tuple[str, str]],
    return_type: str,
    package_prefix: str
) -> str:
    """Generate use case class code. package_prefix from config (path_utils.get_package_prefix)."""
    
    feature_name_pascal = to_pascal_case(feature_name)
    repository_field = to_camel_case(feature_name) + "Repository"
    
    # Build parameter list for invoke
    param_list = []
    for param_name, param_type in parameters:
        param_list.append(f"{param_name}: {param_type}")
    
    param_str = ",\n        ".join(param_list) if param_list else ""
    if param_str:
        param_str = f"\n        {param_str}\n    "
    
    # Build repository call parameters
    call_params = ", ".join([name for name, _ in parameters])
    
    # Generate imports
    imports = []
    imports.append(f"import {package_prefix}.domain.repository.{feature_name_pascal}Repository")
    
    # Add import(s) for the return type's domain model(s), incl. generics like List<Collection>
    if return_type != "Unit":
        for domain_type in domain_model_types(return_type):
            imports.append(f"import {package_prefix}.domain.model.{domain_type}")
    
    # Add imports for parameter types that are request models (data layer)
    for _param_name, param_type in parameters:
        if param_type.endswith("Request") and '<' not in param_type and '.' not in param_type:
            imports.append(f"import {package_prefix}.data.datasource.remote.model.request.{param_type}")
    
    imports_str = "\n".join(imports)
    
    # Handle Unit returns (don't add explicit ": Unit" and don't use "return")
    if return_type == "Unit":
        return_type_annotation = ""
        invoke_body = f"        {repository_field}.{repository_method}({call_params})"
    else:
        return_type_annotation = f": {return_type}"
        invoke_body = f"        return {repository_field}.{repository_method}({call_params})"
    
    # Generate use case class
    use_case_code = f"""package {package_prefix}.domain.usecase

{imports_str}

class {use_case_name}(
    private val {repository_field}: {feature_name_pascal}Repository
) {{
    suspend operator fun invoke({param_str}){return_type_annotation} {{
{invoke_body}
    }}
}}
"""
    
    return use_case_code


def create_use_case(
    feature_name: str,
    use_case_name: str,
    repository_method: str,
    config: dict,
    output_json: bool = False,
    parameters: List[Tuple[str, str]] = None,
    return_type: str = None
) -> dict:
    """Create use case file."""
    
    # Validate required parameters
    if parameters is None:
        print(f"[!] Error: parameters is required")
        sys.exit(1)
    if return_type is None:
        print(f"[!] Error: return_type is required")
        sys.exit(1)
    
    feature_name_pascal = to_pascal_case(feature_name)
    
    # Get project root - prefer environment variable, fallback to current working directory
    project_root_str = os.getenv("AI_SCRIPTS_PROJECT_ROOT")
    if project_root_str:
        project_root = Path(project_root_str)
    else:
        project_root = Path.cwd()
    
    # Build paths - resolve base_path relative to project root
    base_path_str = config.get("base_path", "composeApp/src/commonMain/kotlin")
    if Path(base_path_str).is_absolute():
        base_path = Path(base_path_str)
    else:
        base_path = project_root / base_path_str
    
    path_segment = get_path_segment(config, feature_name)
    usecase_dir = base_path / path_segment / "domain" / "usecase"
    usecase_file = usecase_dir / f"{use_case_name}.kt"
    
    package_prefix = get_package_prefix(config, feature_name)
    # Generate use case code
    use_case_code = generate_use_case(
        feature_name, use_case_name, repository_method,
        parameters, return_type, package_prefix
    )
    
    try:
        relative_path = str(usecase_file.relative_to(project_root))
    except ValueError:
        relative_path = str(usecase_file)

    result = {
        "files": [{
            "path": relative_path,
            "content": use_case_code
        }],
        "message": f"Use case {use_case_name} generated successfully for feature: {to_pascal_case(feature_name)}"
    }

    if output_json:
        # Opt-in: print file contents as JSON instead of writing to disk.
        print(json.dumps(result))
        return result

    # Default: write the use case file to disk (mirrors generate_data_model.py).
    usecase_dir.mkdir(parents=True, exist_ok=True)
    usecase_file.write_text(use_case_code, encoding='utf-8')
    print(f"[+] Generated: {usecase_file}")
    return result


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    
    feature_name = sys.argv[1]
    use_case_name = sys.argv[2]
    repository_method = sys.argv[3]
    
    # Validate use case name format (should be PascalCase)
    if not use_case_name[0].isupper():
        print(f"[!] Error: Use case name should be in PascalCase (e.g., GetUserSettingsUseCase)")
        print(f"   You provided: {use_case_name}")
        sys.exit(1)
    
    # Load config
    config = load_config()
    output_json = False
    parameters = None
    return_type = None
    
    # Optional overrides
    extra_args = sys.argv[4:]
    i = 0
    while i < len(extra_args):
        arg = extra_args[i]
        if arg == '--shared':
            i += 1
        elif arg == '--feature-root':
            if i + 1 < len(extra_args):
                config["feature_root"] = extra_args[i + 1]
                i += 2
            else:
                print("[!] Error: --feature-root requires a value (e.g., shared)")
                sys.exit(1)
        elif arg == '--output-json':
            output_json = True
            i += 1
        elif arg == '--parameters':
            # Parse parameters: --parameters "<json array>" or "name1:Type1 name2:Type2"
            if i + 1 < len(extra_args):
                params_str = extra_args[i + 1].strip()
                parameters = _parse_parameters(params_str)
                i += 2
            else:
                print("[!] Error: --parameters requires a value")
                sys.exit(1)
        elif arg == '--return-type':
            if i + 1 < len(extra_args):
                return_type = extra_args[i + 1]
                i += 2
            else:
                print("[!] Error: --return-type requires a value")
                sys.exit(1)
        else:
            i += 1
    
    # Create use case
    create_use_case(feature_name, use_case_name, repository_method, config, output_json=output_json, parameters=parameters, return_type=return_type)


if __name__ == "__main__":
    main()

