#!/usr/bin/env python3
"""
Add service method with DevengNetworkingModule.sendRequest to service class.

HTTP Methods: GET, POST, PUT, PATCH, DELETE

Options:
    --returns <Type>                    Return type (default: Unit)
    --query <name:Type ...>             Query parameters
    --path <name:Type ...>              Path parameters
    --request-body <Type>               Request body type name
    --request-body-fields <name:Type>   Request body field parameters (constructs request object internally)
    --shared                            Target shared layer instead of feature layer
    --entity <name>                     When --shared: use this for service class name (e.g. DashboardUser -> DashboardUserService.kt)
    --feature-root <root>               Root folder (feature or shared)

Usage:
    python scripts/add_service_method.py <feature> <method_name> <http_method> <endpoint> [options]

Examples:
    # GET with query parameters
    python scripts/add_service_method.py notifications fetchNotifications GET notifications/api/Notifications --query userId:Int page:Int --returns FetchNotificationsResponse
    
    # POST with request body (request constructed internally)
    python scripts/add_service_method.py products createProduct POST products/api/Product --request-body CreateProductRequest --request-body-fields name:String price:Double categoryId:Int --returns ProductResponse
    
    # PUT with path parameter and request body
    python scripts/add_service_method.py profile updateProfile PUT profile/api/User/{userId} --path userId:Int --request-body UpdateProfileRequest --request-body-fields name:String email:String phone:String? --returns UserProfileResponse
    
    # DELETE with path parameter
    python scripts/add_service_method.py products deleteProduct DELETE products/api/Product/{id} --path id:Int
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


def ensure_path_params_in_endpoint(endpoint: str, path_params: List[Tuple[str, str]]) -> str:
    """Ensure path parameters are present in the endpoint as placeholders."""
    if not path_params:
        return endpoint
    
    # Check if endpoint has placeholders for all path params
    for param_name, param_type in path_params:
        placeholder = f"{{{param_name}}}"
        # Case-insensitive search for the placeholder
        if not re.search(rf'\{{{param_name}\}}', endpoint, re.IGNORECASE):
            # Placeholder missing, add it to the end
            # Remove trailing slash if present
            endpoint = endpoint.rstrip('/')
            endpoint = f"{endpoint}/{placeholder}"
    
    return endpoint


def generate_service_method(
    method_name: str,
    http_method: str,
    endpoint: str,
    query_params: List[Tuple[str, str]],
    path_params: List[Tuple[str, str]],
    request_body_type: Optional[str],
    request_body_fields: List[Tuple[str, str]],
    return_type: str
) -> str:
    """Generate the service method code."""
    
    # Ensure path parameters are in the endpoint
    endpoint = ensure_path_params_in_endpoint(endpoint, path_params)
    
    # Build parameter list
    params = []
    
    # Add path parameters first
    for param_name, param_type in path_params:
        params.append(f"{param_name}: {param_type}")
    
    # Add query parameters
    for param_name, param_type in query_params:
        # Add optional default for common pagination params
        if param_name == 'page' and param_type == 'Int':
            params.append(f"{param_name}: {param_type} = 1")
        else:
            params.append(f"{param_name}: {param_type}")
    
    # Add request body fields as individual parameters
    if request_body_fields:
        for param_name, param_type in request_body_fields:
            params.append(f"{param_name}: {param_type}")
    elif request_body_type:
        # Single request body parameter (pass-through)
        params.append(f"request: {request_body_type}")
    
    param_str = ",\n        ".join(params) if params else ""
    if param_str:
        param_str = f"\n        {param_str}\n    "
    
    # Determine type parameters for sendRequest
    request_type = request_body_type if request_body_type else "Unit"
    response_type = return_type if return_type != "Unit" else "Unit"
    
    # Build query parameters map using buildMap for nullable handling
    query_map_lines = []
    if query_params:
        for param_name, param_type in query_params:
            is_nullable = '?' in param_type
            if is_nullable:
                # Use safe call for nullable parameters
                query_map_lines.append(f'                {param_name}?.let {{ put("{param_name}", it.toString()) }}')
            else:
                # Direct put for non-nullable parameters
                query_map_lines.append(f'                put("{param_name}", {param_name}.toString())')
        query_map = "queryParameters = buildMap {\n" + "\n".join(query_map_lines) + "\n            }"
    else:
        query_map = ""
    
    # Replace path parameter placeholders with Kotlin string interpolation
    final_endpoint = endpoint
    if path_params:
        for param_name, param_type in path_params:
            # Replace {paramName} with $paramName for Kotlin string interpolation
            placeholder_pattern = rf'\{{{param_name}\}}'
            final_endpoint = re.sub(placeholder_pattern, f'${param_name}', final_endpoint, flags=re.IGNORECASE)
    
    # Update endpoint to use the interpolated version
    endpoint = final_endpoint
    path_map = ""  # No longer need pathParameters map
    
    # Build request body construction
    request_body_construction = ""
    request_body_param = ""
    
    if request_body_type and request_body_fields:
        # Construct request object from fields
        field_assignments = []
        for param_name, param_type in request_body_fields:
            field_assignments.append(f"{param_name} = {param_name}")
        
        request_construction_str = ",\n            ".join(field_assignments)
        request_body_construction = f"val requestBody = {request_body_type}(\n            {request_construction_str}\n        )\n\n        "
        request_body_param = "requestBody = requestBody"
    elif request_body_type:
        # Single request parameter (pass-through)
        request_body_param = "requestBody = request"
    
    # Combine all parameters for sendRequest
    send_request_params = [
        f'endpoint = "{endpoint}"',
        f'requestMethod = DevengHttpMethod.{http_method}'
    ]
    
    if request_body_param:
        send_request_params.append(request_body_param)
    if query_map:
        send_request_params.append(query_map)
    # path_map is no longer used - we use string interpolation in endpoint directly
    
    send_request_params_str = ",\n            ".join(send_request_params)
    
    # Build return statement
    return_stmt = "return " if return_type != "Unit" else ""
    
    # Build type parameters
    if request_type == "Unit" and response_type == "Unit":
        type_params = "<Unit, Unit>"
    elif request_type != "Unit" or response_type != "Unit":
        type_params = f"<{request_type}, {response_type}>"
    else:
        type_params = ""
    
    # Generate method
    method = f"""    suspend fun {method_name}({param_str}): {return_type} {{
        {request_body_construction}{return_stmt}devengNetworkingModule.sendRequest{type_params}(
            {send_request_params_str}
        )
    }}"""
    
    # Collect imports
    imports = []
    if request_body_type and request_body_type != "Unit":
        imports.append(f"import feature.*.data.datasource.remote.model.request.{request_body_type}")
    if return_type != "Unit" and '<' not in return_type and '.' not in return_type:
        imports.append(f"import feature.*.data.datasource.remote.model.response.{return_type}")
    
    return method, imports


def add_service_method(
    feature_name: str,
    method_name: str,
    http_method: str,
    endpoint: str,
    query_params: List[Tuple[str, str]],
    path_params: List[Tuple[str, str]],
    request_body_type: Optional[str],
    request_body_fields: List[Tuple[str, str]],
    return_type: str,
    config: dict,
    entity_name: Optional[str] = None
) -> None:
    """Add a service method to the service class."""
    feature_name_pascal = to_pascal_case(feature_name)
    # When feature is shared and entity_name is set, use it for the service class/file name
    if is_shared(feature_name) and entity_name:
        class_name_pascal = to_pascal_case(entity_name)
    else:
        class_name_pascal = feature_name_pascal
    package_prefix = get_package_prefix(config, feature_name)
    path_segment = get_path_segment(config, feature_name)

    # Generate method code
    method_code, new_imports = generate_service_method(
        method_name, http_method, endpoint,
        query_params, path_params, request_body_type, request_body_fields, return_type
    )

    # Replace placeholder with actual package prefix for imports
    imports_to_add = [imp.replace('feature.*', package_prefix) for imp in new_imports]
    
    # Show the corrected endpoint with path params
    corrected_endpoint = ensure_path_params_in_endpoint(endpoint, path_params)
    
    # Output instructions instead of modifying file
    print(f"\n[+] Service Method Addition Instructions")
    print()

    base_path_str = config.get("base_path", "composeApp/src/commonMain/kotlin")
    target_path = f"{base_path_str}/{path_segment}/data/datasource/remote/{class_name_pascal}Service.kt"
    
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
    # Print method lines as-is (4 spaces for signature, 8 for body) so parser's minLeading preserves relative indent
    for line in method_code.split('\n'):
        print(line)


def main():
    if len(sys.argv) < 5:
        print(__doc__)
        sys.exit(1)
    
    feature_name = sys.argv[1]
    method_name = sys.argv[2]
    http_method = sys.argv[3].upper()
    endpoint = sys.argv[4]
    
    if http_method not in ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']:
        print(f"[!] Error: Invalid HTTP method '{http_method}'. Must be GET, POST, PUT, PATCH, or DELETE")
        sys.exit(1)
    
    # Parse options
    args = sys.argv[5:]
    return_type = "Unit"
    query_params = []
    path_params = []
    request_body_type = None
    request_body_fields = []
    # Layer root override (e.g., shared)
    feature_root_override = None
    entity_name = None

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
        
        elif arg == '--query' or arg == '--query-params':
            # Collect all query parameters until next option
            i += 1
            while i < len(args) and not args[i].startswith('--'):
                if ':' in args[i]:
                    query_params.append(args[i])
                i += 1
        
        elif arg == '--path' or arg == '--path-params':
            # Collect all path parameters until next option
            i += 1
            while i < len(args) and not args[i].startswith('--'):
                if ':' in args[i]:
                    path_params.append(args[i])
                i += 1
        
        elif arg == '--request-body':
            if i + 1 < len(args):
                request_body_type = args[i + 1]
                i += 2
            else:
                print("[!] Error: --request-body requires a type argument")
                sys.exit(1)
        
        elif arg == '--request-body-fields':
            # Collect all request body field parameters until next option
            i += 1
            while i < len(args) and not args[i].startswith('--'):
                if ':' in args[i]:
                    request_body_fields.append(args[i])
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
        
        else:
            i += 1
    
    # Parse parameters
    parsed_query = parse_parameters(query_params)
    parsed_path = parse_parameters(path_params)
    parsed_body_fields = parse_parameters(request_body_fields)
    
    # Load config
    config = load_config()
    if feature_root_override:
        config["feature_root"] = feature_root_override

    # Add method
    add_service_method(
        feature_name, method_name, http_method, endpoint,
        parsed_query, parsed_path, request_body_type, parsed_body_fields, return_type, config,
        entity_name=entity_name
    )


if __name__ == "__main__":
    main()

