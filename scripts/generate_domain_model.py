#!/usr/bin/env python3
"""
Domain Model Generator

Generates a domain model data class in the specified feature's domain layer.

Options:
    --shared               Target shared layer instead of feature layer
    --feature-root <root>  Root folder (feature or shared)

Usage:
    python generate_domain_model.py <feature_name> <model_name> [field:Type ...] [--shared]
    python generate_domain_model.py <feature_name> <model_name> --json <json_file> [--shared]

Examples:
    python generate_domain_model.py branchprofile BranchProfile id:Int name:String description:String? isActive:Boolean
    python generate_domain_model.py notifications Notification id:Int title:String message:String? createdAt:Long
    python generate_domain_model.py products Product --json product_model.json
    python generate_domain_model.py shared Something id:Int name:String --shared
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
)


class DomainModelGenerator:
    """Generates domain model data classes. Path and package from config (path_utils)."""
    
    def __init__(self, feature_name: str, config: dict, output_json: bool = False):
        self.feature_name = feature_name.lower()
        self.feature_name_pascal = self._to_pascal_case(feature_name)
        self.base_path = Path(config.get("base_path", "composeApp/src/commonMain/kotlin"))
        self.path_segment = get_path_segment(config, feature_name)
        self.package_prefix = get_package_prefix(config, feature_name)
        self.domain_path = self.base_path / self.path_segment / "domain" / "model"
        self.output_json = output_json
        self.files = []
    
    def generate(self, model_name: str, fields: List[Tuple[str, str]]) -> None:
        """Generate a domain model data class."""
        if not self.output_json:
            print(f"[*] Generating domain model: {model_name}")
            print(f"[>] Feature: {self.feature_name_pascal}")
            print(f"[>] Fields: {len(fields)}")
        
        # Ensure model directory exists
        if not self.output_json:
            self.domain_path.mkdir(parents=True, exist_ok=True)
        
        # Generate the model file
        self._generate_model_file(model_name, fields)
        
        if self.output_json:
            result = {
                "files": self.files,
                "message": f"Domain model {model_name} generated successfully for feature: {self.feature_name_pascal}"
            }
            print(json.dumps(result))
        else:
            print(f"\n[+] Domain model generated successfully!")
            print(f"[>] Location: {self.domain_path / f'{model_name}.kt'}")
    
    def _generate_model_file(self, model_name: str, fields: List[Tuple[str, str]]) -> None:
        """Generate a domain model data class file."""
        package = f"{self.package_prefix}.domain.model"
        
        # Build field definitions
        field_lines = []
        for field_name, field_type in fields:
            field_lines.append(f"    val {field_name}: {field_type}")
        
        fields_str = ',\n'.join(field_lines)
        
        content = f'''package {package}

data class {model_name}(
{fields_str}
)
'''
        
        file_path = self.domain_path / f'{model_name}.kt'
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


def parse_fields_from_json(json_file: str) -> Tuple[str, List[Tuple[str, str]]]:
    """Parse model name and field definitions from JSON file."""
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        model_name = data.get('modelName')
        if not model_name:
            print(f"[!] Error: JSON file must contain 'modelName' field")
            sys.exit(1)
        
        fields_dict = data.get('fields', {})
        fields = [(name, type_) for name, type_ in fields_dict.items()]
        
        return model_name, fields
    
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
        description='Generate domain model data classes',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Generate with inline fields
  python generate_domain_model.py notifications Notification id:Int title:String message:String?
  
  # Generate from JSON file
  python generate_domain_model.py products Product --json product_model.json

JSON file format:
{
  "modelName": "Product",
  "fields": {
    "id": "Int",
    "name": "String",
    "price": "Double",
    "description": "String?"
  }
}
        '''
    )
    
    parser.add_argument('feature_name', help='Name of the feature (e.g., branchprofile, notifications)')
    parser.add_argument('model_name', nargs='?', help='Name of the model class (PascalCase)')
    parser.add_argument('fields', nargs='*', help='Field definitions in format fieldName:Type')
    parser.add_argument('--json', dest='json_file', help='JSON file containing model definition')
    parser.add_argument('--config', default=None, help='Path to config.json (default: Mobile/scripts/config.json)')
    parser.add_argument('--output-json', action='store_true', help='Output file contents as JSON instead of writing to disk')
    
    args = parser.parse_args()
    
    # Parse model name and fields based on input method
    if args.json_file:
        model_name, fields = parse_fields_from_json(args.json_file)
    else:
        if not args.model_name:
            print("[!] Error: model_name is required when not using --json")
            parser.print_help()
            sys.exit(1)
        
        model_name = args.model_name
        
        if not args.fields:
            print("[!] Error: At least one field is required")
            print("[!] Usage: python generate_domain_model.py <feature> <model> field1:Type1 field2:Type2 ...")
            sys.exit(1)
        
        fields = parse_fields_from_args(args.fields)
    
    if not fields:
        print("[!] Error: No fields provided")
        sys.exit(1)
    
    # Path/package from config only
    config = load_config(getattr(args, 'config', None))
    generator = DomainModelGenerator(args.feature_name, config, output_json=args.output_json)
    generator.generate(model_name, fields)


if __name__ == '__main__':
    main()

