#!/usr/bin/env python3
"""
Data Model Generator

Generates request/response model data classes in the data layer.

Model Types:
    - request: Creates model in data/datasource/remote/model/request/
    - response: Creates model in data/datasource/remote/model/response/

Options:
    --shared               Target shared layer instead of feature layer
    --feature-root <root>  Root folder (feature or shared)

Usage:
    python generate_data_model.py <feature_name> <model_type> <model_name> [field:Type ...] [--shared]
    python generate_data_model.py <feature_name> <model_type> <model_name> --json <json_file> [--shared]

Examples:
    # Request model
    python generate_data_model.py notifications request UpdateNotificationRequest isRead:Boolean notificationId:Int
    
    # Response model
    python generate_data_model.py products response FetchProductsResponse products:List<Product> totalCount:Int
    
    # From JSON
    python generate_data_model.py branchprofile request CreateBranchRequest --json branch_request.json
    
    # Target shared layer
    python generate_data_model.py shared response FetchSomethingResponse id:Int name:String --shared
"""

import os
import sys
import json
import argparse
import html
from pathlib import Path
from typing import List, Tuple

from path_utils import (
    DEFAULT_CONFIG_PATH,
    get_package_prefix,
    get_path_segment,
    is_shared,
)


class DataModelGenerator:
    """Generates data layer model data classes. Path and package from config (path_utils)."""
    
    def __init__(self, feature_name: str, config: dict, output_json: bool = False):
        self.feature_name = feature_name.lower()
        self.feature_name_pascal = self._to_pascal_case(feature_name)
        self.base_path = Path(config.get("base_path", "composeApp/src/commonMain/kotlin"))
        self.path_segment = get_path_segment(config, feature_name)
        self.package_prefix = get_package_prefix(config, feature_name)
        self.data_path = self.base_path / self.path_segment / "data" / "datasource" / "remote" / "model"
        self.output_json = output_json
        self.files = []
    
    def generate(self, model_type: str, model_name: str, fields: List[Tuple[str, str]]) -> None:
        """Generate a data model data class."""
        if model_type not in ['request', 'response']:
            print(f"[!] Error: model_type must be 'request' or 'response', got '{model_type}'")
            sys.exit(1)
        
        if not self.output_json:
            print(f"[*] Generating {model_type} model: {model_name}")
            print(f"[>] Feature: {self.feature_name_pascal}")
            print(f"[>] Fields: {len(fields)}")
        
        # Ensure model directory exists
        model_dir = self.data_path / model_type
        if not self.output_json:
            model_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate the model file
        self._generate_model_file(model_type, model_name, fields)
        
        if self.output_json:
            result = {
                "files": self.files,
                "message": f"Data model {model_name} ({model_type}) generated successfully for feature: {self.feature_name_pascal}"
            }
            print(json.dumps(result))
        else:
            print(f"\n[+] Data model generated successfully!")
            print(f"[>] Location: {model_dir / f'{model_name}.kt'}")
    
    def _generate_model_file(self, model_type: str, model_name: str, fields: List[Tuple[str, str]]) -> None:
        """Generate a data model data class file."""
        package = f"{self.package_prefix}.data.datasource.remote.model.{model_type}"
        
        # Build field definitions with @SerialName annotations
        field_blocks = []
        for field_name, field_type in fields:
            field_blocks.append(f'    @SerialName("{field_name}")\n    val {field_name}: {field_type}')
        
        fields_str = ',\n'.join(field_blocks)
        
        content = f'''package {package}

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class {model_name}(
{fields_str}
)
'''
        
        file_path = self.data_path / model_type / f'{model_name}.kt'
        relative_path = str(file_path)
        
        if self.output_json:
            self.files.append({
                "path": relative_path,
                "content": content
            })
        else:
            file_path.write_text(content, encoding='utf-8')
            print(f"[+] Generated: {file_path}")
    
    def _to_pascal_case(self, text: str) -> str:
        """Convert text to PascalCase."""
        words = text.replace('_', ' ').replace('-', ' ').split()
        return ''.join(word.capitalize() for word in words)


def parse_fields_from_args(field_args: List[str]) -> List[Tuple[str, str]]:
    """Parse field definitions from command line arguments."""
    fields = []
    for field_arg in field_args:
        if ':' not in field_arg:
            print(f"[!] Error: Invalid field format '{field_arg}'. Expected 'fieldName:Type'")
            sys.exit(1)
        
        field_name, field_type = field_arg.split(':', 1)
        # Decode HTML entities (e.g., &lt; -> <, &gt; -> >)
        field_type = html.unescape(field_type.strip())
        fields.append((field_name.strip(), field_type))
    
    return fields


def parse_fields_from_json(json_file: str) -> Tuple[str, str, List[Tuple[str, str]]]:
    """Parse model type, name and field definitions from JSON file."""
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        model_type = data.get('modelType')
        model_name = data.get('modelName')
        
        if not model_type or not model_name:
            print(f"[!] Error: JSON file must contain 'modelType' and 'modelName' fields")
            sys.exit(1)
        
        fields_dict = data.get('fields', {})
        fields = [(name, type_) for name, type_ in fields_dict.items()]
        
        return model_type, model_name, fields
    
    except FileNotFoundError:
        print(f"[!] Error: JSON file not found: {json_file}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"[!] Error: Invalid JSON format: {e}")
        sys.exit(1)


def load_config(config_path: str = None) -> dict:
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


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description='Generate data layer model data classes (request/response)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Generate request model
  python generate_data_model.py notifications request UpdateNotificationRequest isRead:Boolean
  
  # Generate response model
  python generate_data_model.py products response FetchProductsResponse products:List<Product> total:Int
  
  # Generate from JSON file
  python generate_data_model.py branchprofile request CreateBranchRequest --json request.json

JSON file format:
{
  "modelType": "request",
  "modelName": "CreateBranchRequest",
  "fields": {
    "name": "String",
    "description": "String?",
    "address": "String"
  }
}
        '''
    )
    
    parser.add_argument('feature_name', help='Name of the feature (e.g., notifications, products)')
    parser.add_argument('model_type', nargs='?', help='Model type: "request" or "response"')
    parser.add_argument('model_name', nargs='?', help='Name of the model class (PascalCase)')
    parser.add_argument('fields', nargs='*', help='Field definitions in format fieldName:Type')
    parser.add_argument('--json', dest='json_file', help='JSON file containing model definition')
    parser.add_argument('--config', default=None, help='Path to config.json (default: config.json)')
    parser.add_argument('--output-json', action='store_true', help='Output file contents as JSON instead of writing to disk')
    
    args = parser.parse_args()
    
    # Parse model type, name and fields based on input method
    if args.json_file:
        model_type, model_name, fields = parse_fields_from_json(args.json_file)
    else:
        if not args.model_type or not args.model_name:
            print("[!] Error: model_type and model_name are required when not using --json")
            parser.print_help()
            sys.exit(1)
        
        model_type = args.model_type
        model_name = args.model_name
        
        if not args.fields:
            print("[!] Error: At least one field is required")
            print("[!] Usage: python generate_data_model.py <feature> <type> <model> field1:Type1 field2:Type2 ...")
            sys.exit(1)
        
        fields = parse_fields_from_args(args.fields)
    
    if not fields:
        print("[!] Error: No fields provided")
        sys.exit(1)
    
    # Path/package from config only
    config = load_config(getattr(args, 'config', None))
    generator = DataModelGenerator(args.feature_name, config, output_json=args.output_json)
    generator.generate(model_type, model_name, fields)


if __name__ == '__main__':
    main()

