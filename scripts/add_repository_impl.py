#!/usr/bin/env python3
"""
Add repository implementation method to RepositoryImpl class.

Options:
    --mapper <MapperName>    Mapper to use for response mapping (auto-injected if not present)
    --map-list              Force list mapping with .map{} (auto-detected if return type is List<>)
    --project-root <path>   Resolve repository/service paths under this directory (default: cwd)
    --shared                 Target shared layer instead of feature layer
    --entity <name>          When --shared: use this for repository/service class names (e.g. DashboardUser -> DashboardUserRepositoryImpl.kt)
    --feature-root <root>   Root folder (feature or shared)

Usage:
    python scripts/add_repository_impl.py <feature> <domain_method> <service_method> [options]

Examples:
    # With mapper (GET endpoint returning domain model)
    python scripts/add_repository_impl.py profile getUserProfile fetchUserProfile --mapper userProfileMapper
    
    # Simple pass-through (DELETE, no mapper needed)
    python scripts/add_repository_impl.py profile deleteProfile deleteProfile
    
    # PUT/POST with mapper
    python scripts/add_repository_impl.py profile updateUserProfile updateUserProfile --mapper userProfileMapper
    
    # Target shared layer
    python scripts/add_repository_impl.py shared getSomething fetchSomething --mapper somethingMapper --shared

Note:
    - Repository simply passes domain parameters to service method
    - Service method handles request body construction internally
    - Mapper is automatically injected into repository constructor if specified
"""

import os
import sys
import json
import re
from pathlib import Path
from typing import List, Tuple, Optional, Dict

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


def pascal_to_camel(pascal: str) -> str:
    """Convert PascalCase to camelCase (FinalTestMapper -> finalTestMapper)."""
    return pascal[0].lower() + pascal[1:] if pascal else ""


def method_exists(file_path: str, method_name: str) -> bool:
    """Check if a method with the given name already exists in the file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            pattern = rf'\boverride\s+suspend\s+fun\s+{re.escape(method_name)}\s*\('
            return bool(re.search(pattern, content))
    except FileNotFoundError:
        return False


def get_domain_method_signature(repo_interface_path: str, method_name: str) -> Optional[Tuple[List[Tuple[str, str]], str]]:
    """Extract method signature (parameters and return type) from domain repository interface."""
    try:
        with open(repo_interface_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find the method declaration (return type is optional for Unit returns)
        pattern = rf'suspend\s+fun\s+{re.escape(method_name)}\s*\((.*?)\)(?:\s*:\s*([^\n{{]+))?'
        match = re.search(pattern, content, re.DOTALL)
        
        if not match:
            return None
        
        params_str = match.group(1).strip()
        # If no return type specified, it's Unit
        return_type = match.group(2).strip() if match.group(2) else "Unit"
        
        # Parse parameters
        parameters = []
        if params_str:
            for param in params_str.split(','):
                param = param.strip()
                if ':' in param:
                    name, type_str = param.split(':', 1)
                    parameters.append((name.strip(), type_str.strip()))
        
        return parameters, return_type
    
    except Exception as e:
        return None


def get_service_method_params(service_file_path: str, service_method: str) -> List[str]:
    """Extract parameter names from service method signature."""
    pairs = get_service_method_param_types(service_file_path, service_method)
    return [name for name, _ in pairs]


def get_service_method_param_types(service_file_path: str, service_method: str) -> List[Tuple[str, str]]:
    """Extract (name, type) from service method signature. Returns [(param_name, param_type), ...]."""
    try:
        with open(service_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        pattern = rf'suspend\s+fun\s+{re.escape(service_method)}\s*\((.*?)\)\s*:'
        match = re.search(pattern, content, re.DOTALL)
        if not match:
            return []
        params_str = match.group(1).strip()
        result = []
        if params_str:
            for param in params_str.split(','):
                param = param.strip()
                if ':' in param:
                    name, type_str = param.split(':', 1)
                    result.append((name.strip(), type_str.strip()))
        return result
    except Exception:
        return []


def generate_repository_method(
    method_name: str,
    parameters: List[Tuple[str, str]],
    return_type: str,
    service_method: str,
    service_field_name: str,
    mapper_name: Optional[str],
    service_params_signature: List[str],
    force_map_list: bool = False,
    service_param_types: Optional[List[Tuple[str, str]]] = None
) -> Tuple[str, List[str]]:
    """Generate the repository implementation method code and required imports."""
    
    # Build parameter list
    param_list = ", ".join([f"{name}: {type_}" for name, type_ in parameters])
    
    # Build method body
    body_lines = []
    
    # Build service call parameters
    service_params = []
    domain_param_names = [name for name, _ in parameters]
    imports = []
    
    # When service has single param "request: XRequest", build request from domain params
    if service_param_types and len(service_param_types) == 1:
        sp_name, sp_type = service_param_types[0]
        if sp_name == "request" and (sp_type.endswith("Request") or "Request" in sp_type):
            # request = RequestType(param1 = param1, param2 = param2, ...)
            domain_to_request = ", ".join(f"{name} = {name}" for name, _ in parameters)
            service_params.append(f"request = {sp_type}({domain_to_request})")
            imports.append(f"import feature.*.data.datasource.remote.model.request.{sp_type}")
        else:
            # Match by name as before
            if service_params_signature:
                for service_param in service_params_signature:
                    if service_param in domain_param_names:
                        service_params.append(f"{service_param} = {service_param}")
            else:
                service_params = [name for name, _ in parameters]
    elif service_params_signature:
        # Match domain params to service params by name
        for service_param in service_params_signature:
            if service_param in domain_param_names:
                service_params.append(f"{service_param} = {service_param}")
    else:
        # Pass all domain parameters directly
        service_params = [name for name, _ in parameters]
    
    # Mapper instance name (camelCase for constructor param; use pascal_to_camel when name is PascalCase like FinalTestMapper)
    mapper_field = (pascal_to_camel(mapper_name) if mapper_name and mapper_name[0].isupper() and "_" not in mapper_name else to_camel_case(mapper_name)) if mapper_name else None
    
    # Format service call with parameters on separate lines if more than 1 param
    if len(service_params) > 1:
        service_call_params = ',\n'.join([f"            {param}" for param in service_params])
        service_call = f"{service_method}(\n{service_call_params}\n        )"
    else:
        service_call = f"{service_method}({', '.join(service_params)})"
    
    # Handle return type
    
    # Check if return type is a List (auto-detect or forced)
    is_list_return = return_type.startswith("List<") or force_map_list
    
    if return_type == "Unit":
        # No return value, just call service
        if len(service_params) > 1:
            body_lines.append(f"        {service_field_name}.{service_call}")
        else:
            body_lines.append(f"        {service_field_name}.{service_call}")
    else:
        # Has return value
        if mapper_name:
            # Use mapper to convert response
            if len(service_params) > 1:
                body_lines.append(f"        val response = {service_field_name}.{service_call}")
            else:
                body_lines.append(f"        val response = {service_field_name}.{service_call}")
            
            if is_list_return:
                # For List returns, use .map { } to iterate and transform each item
                body_lines.append(f"        return response.map {{ {mapper_field}.mapToDomain(it) }}")
            else:
                # For single object, direct mapping
                body_lines.append(f"        return {mapper_field}.mapToDomain(response)")
        else:
            # Direct return from service
            body_lines.append(f"        return {service_field_name}.{service_call}")
    
    # Add import for domain return type (if not Unit and doesn't contain <)
    if return_type != "Unit" and '<' not in return_type and '.' not in return_type:
        imports.append(f"import feature.*.domain.model.{return_type}")
    
    # Build method signature (don't add explicit ": Unit" for Unit returns)
    return_type_annotation = "" if return_type == "Unit" else f": {return_type}"
    method = f"""    override suspend fun {method_name}({param_list}){return_type_annotation} {{
{chr(10).join(body_lines)}
    }}"""
    
    return method, imports


def insert_imports_after_last(content: str, imports: List[str]) -> str:
    """Insert import lines after the last existing import. Returns new content.
    Each item in imports may be either a full 'import x.y.z' line or a package path."""
    lines = content.splitlines(keepends=True)
    last_import_idx = -1
    for i, line in enumerate(lines):
        if line.strip().startswith("import "):
            last_import_idx = i
    if last_import_idx < 0 or not imports:
        return content
    for imp in sorted(imports):
        imp_stripped = imp.strip()
        if imp_stripped.startswith("import "):
            import_line = imp_stripped
        else:
            import_line = f"import {imp_stripped}"
        if import_line not in content and f"import {imp_stripped}" not in content:
            lines.insert(last_import_idx + 1, import_line + "\n")
            last_import_idx += 1
    return "".join(lines)


def insert_method_before_class_closing(content: str, class_name_pascal: str, method_code: str) -> str:
    """Insert method code before the closing brace of the class. Returns new content."""
    lines = content.splitlines(keepends=True)
    brace_count = 0
    in_class = False
    insert_at = -1
    for i, line in enumerate(lines):
        stripped = line.strip()
        if "class " in stripped and f"{class_name_pascal}RepositoryImpl" in stripped:
            in_class = True
        if in_class:
            brace_count += stripped.count("{") - stripped.count("}")
            if brace_count == 0 and "}" in stripped:
                insert_at = i
                break
    if insert_at < 0:
        return content
    method_lines = [ml + "\n" for ml in method_code.split("\n")]
    lines[insert_at:insert_at] = method_lines
    return "".join(lines)


def inject_mapper_in_constructor(content: str, mapper_name: str, feature_name_pascal: str, feature_name: str, package_prefix: str) -> str:
    """Inject mapper into repository constructor if not already present."""
    
    # Build mapper class name (PascalCase) and param name (camelCase)
    mapper_class = mapper_name[0].upper() + mapper_name[1:] if mapper_name else ""
    if not mapper_class:
        return content
    mapper_param = pascal_to_camel(mapper_name) if mapper_name and mapper_name[0].isupper() and "_" not in mapper_name else to_camel_case(mapper_name)
    
    # Check if mapper is already in constructor
    if f"private val {mapper_param}" in content or f"private val {mapper_class}" in content:
        return content
    
    # Find constructor closing parenthesis position
    constructor_pattern = rf'(class\s+{feature_name_pascal}RepositoryImpl\s*\(\s*)(.*?)(\s*\)\s*:\s*{feature_name_pascal}Repository)'
    match = re.search(constructor_pattern, content, re.DOTALL)
    
    if not match:
        return content
    
    class_start = match.group(1)
    constructor_params = match.group(2)
    class_end = match.group(3)
    
    # Check if there are existing parameters
    has_params = constructor_params.strip() != ''
    
    # Build new constructor
    if has_params:
        # Add comma and new mapper parameter
        new_constructor = f"{class_start}{constructor_params},\n    private val {mapper_param}: {mapper_class}{class_end}"
    else:
        new_constructor = f"{class_start}\n    private val {mapper_param}: {mapper_class}\n{class_end}"
    
    # Replace constructor
    content = content[:match.start()] + new_constructor + content[match.end():]
    
    # Add import for mapper
    import_line = f"import {package_prefix}.data.datasource.remote.model.mapper.{mapper_class}\n"
    
    # Find last import line to insert after
    import_pattern = r'(import\s+[^\n]+\n)'
    imports = list(re.finditer(import_pattern, content))
    
    if imports and import_line not in content:
        last_import = imports[-1]
        content = content[:last_import.end()] + import_line + content[last_import.end():]
    
    return content


def add_repository_implementation(
    feature_name: str,
    domain_method: str,
    service_method: str,
    mapper_name: Optional[str],
    config: dict,
    force_map_list: bool = False,
    entity_name: Optional[str] = None,
    project_root: Optional[Path] = None
) -> None:
    """Add a repository implementation method to the RepositoryImpl class."""
    feature_name_pascal = to_pascal_case(feature_name)
    # When feature is shared and entity_name is set, use it for repository/service class names
    if is_shared(feature_name) and entity_name:
        class_name_pascal = to_pascal_case(entity_name)
        service_field_name = to_camel_case(entity_name) + "Service"
    else:
        class_name_pascal = feature_name_pascal
        service_field_name = to_camel_case(feature_name) + "Service"
    path_segment = get_path_segment(config, feature_name)
    package_prefix = get_package_prefix(config, feature_name)
    base_path_str = config.get("base_path", "composeApp/src/commonMain/kotlin")
    base_path = (project_root or Path.cwd()) / base_path_str

    repo_impl_file = base_path / path_segment / "data" / "repository" / f"{class_name_pascal}RepositoryImpl.kt"
    repo_interface_file = base_path / path_segment / "domain" / "repository" / f"{class_name_pascal}Repository.kt"
    service_file = base_path / path_segment / "data" / "datasource" / "remote" / f"{class_name_pascal}Service.kt"
    
    # Check if files exist
    repo_impl_exists = repo_impl_file.exists()
    repo_interface_exists = repo_interface_file.exists()
    
    if not repo_interface_exists:
        print(f"[!] Error: Repository interface not found at {repo_interface_file}")
        if project_root is None:
            print("    When the MCP server runs from a different directory than your app, pass project_root to execute-script so the script can find your files.")
        sys.exit(1)

    # Get method signature from domain interface
    signature = get_domain_method_signature(str(repo_interface_file), domain_method)
    if not signature:
        print(f"[!] Error: Could not find method '{domain_method}' in {class_name_pascal}Repository interface")
        if project_root is None:
            print("    When the MCP server runs from a different directory than your app, pass project_root to execute-script so the script resolves paths under your app.")
        sys.exit(1)

    parameters, return_type = signature

    # Check if method already exists
    if repo_impl_exists and method_exists(str(repo_impl_file), domain_method):
        print(f"[*] Method '{domain_method}' already exists in {class_name_pascal}RepositoryImpl")
        print(f"   Skipping...")
        return

    # Get service method signature
    service_params_signature = []
    service_param_types: List[Tuple[str, str]] = []
    if service_file.exists():
        service_params_signature = get_service_method_params(str(service_file), service_method)
        service_param_types = get_service_method_param_types(str(service_file), service_method)
    
    # Read existing file if it exists
    content = ""
    lines = []
    if repo_impl_exists:
        try:
            with open(repo_impl_file, 'r', encoding='utf-8') as f:
                content = f.read()
            lines = content.splitlines(keepends=True)
        except Exception as e:
            repo_impl_exists = False
    
    # Generate method code
    method_code, new_imports = generate_repository_method(
        domain_method, parameters, return_type,
        service_method, service_field_name, mapper_name, service_params_signature,
        force_map_list, service_param_types=service_param_types
    )
    
    # Replace placeholder in imports with package prefix from config
    new_imports = [imp.replace('feature.*', package_prefix) for imp in new_imports]
    
    # Filter out imports that already exist
    imports_to_add = []
    if repo_impl_exists:
        for new_import in new_imports:
            if new_import not in content:
                imports_to_add.append(new_import)
    else:
        imports_to_add = new_imports
    
    # Determine insertion location (for instructions)
    insertion_location = "before the closing brace of the class"
    constructor_update_needed = False
    constructor_update = ""
    
    if repo_impl_exists and lines:
        # Find insertion point (before closing brace of class)
        brace_count = 0
        in_class = False
        
        for i, line in enumerate(lines):
            stripped = line.strip()

            if 'class' in stripped and class_name_pascal + 'RepositoryImpl' in stripped:
                in_class = True
            
            if in_class:
                brace_count += stripped.count('{') - stripped.count('}')
                
                # Find the closing brace of the class
                if brace_count == 0 and '}' in stripped:
                    insertion_location = f"before the closing brace at line {i+1}"
                    break
        
        # Check if mapper needs to be added to constructor
        if mapper_name and repo_impl_exists:
            # Check if mapper is already in constructor
            constructor_content = inject_mapper_in_constructor(content, mapper_name, class_name_pascal, feature_name, package_prefix)
            constructor_update_needed = constructor_content != content
    # Target path: when project_root is set, include base_path so parser resolves to app's source root
    path_segment = get_path_segment(config, feature_name)
    base_path_str = config.get("base_path", "composeApp/src/commonMain/kotlin")
    if project_root is not None:
        target_path = f"{base_path_str}/{path_segment}/data/repository/{class_name_pascal}RepositoryImpl.kt"
    else:
        target_path = f"{path_segment}/data/repository/{class_name_pascal}RepositoryImpl.kt"

    # When constructor needs mapper and we have project_root, output full file as JSON so server can write it
    if constructor_update_needed and project_root is not None and mapper_name:
        full_content = insert_imports_after_last(constructor_content, new_imports)
        full_content = insert_method_before_class_closing(full_content, class_name_pascal, method_code)
        import json
        payload = {
            "message": "Repository implementation updated with mapper in constructor and method",
            "files": [{"path": target_path.replace("\\", "/"), "content": full_content}]
        }
        print(json.dumps(payload, ensure_ascii=False))
        return

    # Output instructions instead of modifying file
    print(f"\n[+] Repository Implementation Method Addition Instructions")
    print()
    
    if imports_to_add:
        print("Target Path:")
        print(f"  {target_path}")
        print()
        print("Code:")
        for imp in sorted(imports_to_add):
            print(f"  {imp}")
        print()
    
    print("Target Path:")
    print(f"  {target_path}")
    print()
    print("Code:")
    for line in method_code.split('\n'):
        print(f"  {line}")


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    
    feature_name = sys.argv[1]
    domain_method = sys.argv[2]
    service_method = sys.argv[3]
    
    # Parse options
    args = sys.argv[4:]
    mapper_name = None
    force_map_list = False
    feature_root_override = None
    entity_name = None
    project_root = None

    i = 0
    while i < len(args):
        arg = args[i]

        if arg == '--mapper':
            if i + 1 < len(args):
                mapper_name = args[i + 1]
                i += 2
            else:
                print("[!] Error: --mapper requires a mapper name argument")
                sys.exit(1)
        elif arg == '--map-list':
            force_map_list = True
            i += 1
        elif arg == '--project-root':
            if i + 1 < len(args):
                project_root = Path(args[i + 1]).resolve()
                i += 2
            else:
                print("[!] Error: --project-root requires a path argument")
                sys.exit(1)
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
        else:
            i += 1
    
    # Load config (from project_root when set, so app's config is used when server runs elsewhere)
    config = load_config(get_config_path(project_root))
    if feature_root_override:
        config["feature_root"] = feature_root_override

    # Add implementation
    add_repository_implementation(
        feature_name, domain_method, service_method,
        mapper_name, config, force_map_list, entity_name=entity_name,
        project_root=project_root
    )


if __name__ == "__main__":
    main()

