#!/usr/bin/env python3
"""
Mapper Generator

Generates mapper classes in the data layer to convert between response models and domain models.

Field Mapping Format:
    - Simple: domainField (if response field has same name)
    - Custom: domainField=responseField (if names differ)

Options:
    --shared               Target shared layer instead of feature layer
    --feature-root <root>  Root folder (feature or shared)

Usage:
    python generate_mapper.py <feature_name> <mapper_name> <response_type> <domain_type> [field_mapping ...] [--shared]
    python generate_mapper.py <feature_name> <mapper_name> --json <json_file> [--shared]

Examples:
    # Simple mapping (all fields have same names)
    python generate_mapper.py notifications NotificationMapper NotificationResponse Notification id title message isRead createdAt
    
    # Custom mapping (some fields renamed)
    python generate_mapper.py products ProductMapper ProductResponse Product id name price description=desc inStock=is_available
    
    # From JSON
    python generate_mapper.py branchprofile BranchProfileMapper --json mapper_definition.json
    
    # Target shared layer
    python generate_mapper.py shared SomethingMapper FetchSomethingResponse Something id name --shared
"""

import os
import sys
import json
import argparse
import re
from pathlib import Path
from typing import List, Tuple, Optional, Dict

from path_utils import (
    DEFAULT_CONFIG_PATH,
    get_package_prefix,
    get_path_segment,
)


class MapperGenerator:
    """Generates mapper classes. Path and package from config (path_utils)."""
    
    def __init__(self, feature_name: str, config: dict, output_json: bool = False):
        self.feature_name = feature_name.lower()
        self.feature_name_pascal = self._to_pascal_case(feature_name)
        self.base_path = Path(config.get("base_path", "composeApp/src/commonMain/kotlin"))
        self.path_segment = get_path_segment(config, feature_name)
        self.package_prefix = get_package_prefix(config, feature_name)
        self.mapper_path = self.base_path / self.path_segment / "data" / "datasource" / "remote" / "model" / "mapper"
        self.output_json = output_json
        self.files = []
    
    def generate(self, mapper_name: str, response_type: str, domain_type: str, field_mappings: List[Tuple[str, str]]) -> None:
        """Generate a mapper class."""
        if not self.output_json:
            print(f"[*] Generating mapper: {mapper_name}")
            print(f"[>] Feature: {self.feature_name_pascal}")
            print(f"[>] Response Type: {response_type}")
            print(f"[>] Domain Type: {domain_type}")
            print(f"[>] Fields: {len(field_mappings)}")
        
        # Ensure mapper directory exists
        if not self.output_json:
            self.mapper_path.mkdir(parents=True, exist_ok=True)
        
        # Generate the mapper file
        self._generate_mapper_file(mapper_name, response_type, domain_type, field_mappings)
        
        if self.output_json:
            result = {
                "files": self.files,
                "message": f"Mapper {mapper_name} generated successfully for feature: {self.feature_name_pascal}"
            }
            print(json.dumps(result))
        else:
            print(f"\n[+] Mapper generated successfully!")
            print(f"[>] Location: {self.mapper_path / f'{mapper_name}.kt'}")
    
    def _get_response_field_types(self, response_type: str) -> Dict[str, str]:
        """Get field types from response model file. No longer reads files - returns empty dict."""
        # File reading removed - field mappings should be provided explicitly
        return {}
    
    def _detect_list_mappers(self, field_mappings: List[Tuple[str, str]], field_types: Dict[str, str]) -> Dict[str, str]:
        """Detect which fields need list mapping and return mapper dependencies."""
        primitives = {'Int', 'Long', 'Double', 'Float', 'Boolean', 'String'}
        list_mappers = {}
        
        for domain_field, response_field in field_mappings:
            field_type = field_types.get(response_field, '')
            # Check if it's List<ComplexType> or List<ComplexType>?
            list_match = re.match(r'List<(\w+)>\??', field_type)
            if list_match:
                inner_type = list_match.group(1)
                is_nullable = field_type.endswith('?')
                
                # If it's not a primitive, we need a mapper
                if inner_type not in primitives:
                    # Generate mapper name: Response -> Mapper (e.g., TransactionResponse -> TransactionMapper)
                    if inner_type.endswith('Response'):
                        mapper_type = inner_type[:-8] + 'Mapper'  # Remove 'Response', add 'Mapper'
                    else:
                        mapper_type = inner_type + 'Mapper'
                    
                    mapper_param = mapper_type[0].lower() + mapper_type[1:]  # camelCase
                    list_mappers[response_field] = {
                        'type': mapper_type,
                        'param': mapper_param,
                        'domain_field': domain_field,
                        'nullable': is_nullable
                    }
        
        return list_mappers
    
    def _generate_mapper_file(self, mapper_name: str, response_type: str, domain_type: str, field_mappings: List[Tuple[str, str]]) -> None:
        """Generate a mapper class file."""
        package = f"{self.package_prefix}.data.datasource.remote.model.mapper"
        response_import = f"{self.package_prefix}.data.datasource.remote.model.response.{response_type}"
        domain_import = f"{self.package_prefix}.domain.model.{domain_type}"
        
        # Get field types from response model
        field_types = self._get_response_field_types(response_type)
        
        # Detect which fields need list mapping
        list_mappers = self._detect_list_mappers(field_mappings, field_types)
        
        # Build constructor parameters if we have list mappers
        constructor_params = ''
        if list_mappers:
            params = []
            for mapper_info in list_mappers.values():
                params.append(f"    private val {mapper_info['param']}: {mapper_info['type']}")
            constructor_params = '\n' + ',\n'.join(params) + '\n'
        
        # Build field mappings
        mapping_lines = []
        for domain_field, response_field in field_mappings:
            if response_field in list_mappers:
                # Use list mapping
                mapper_param = list_mappers[response_field]['param']
                is_nullable = list_mappers[response_field].get('nullable', False)
                map_operator = '?.map' if is_nullable else '.map'
                mapping_lines.append(f'            {domain_field} = response.{response_field}{map_operator} {{ {mapper_param}.mapToDomain(it) }}')
            else:
                # Direct mapping
                mapping_lines.append(f'            {domain_field} = response.{response_field}')
        
        mappings_str = ',\n'.join(mapping_lines)
        
        content = f'''package {package}

import {response_import}
import {domain_import}

class {mapper_name}({constructor_params}) {{
    fun mapToDomain(response: {response_type}): {domain_type} {{
        return {domain_type}(
{mappings_str}
        )
    }}
}}
'''
        
        file_path = self.mapper_path / f'{mapper_name}.kt'
        relative_path = str(file_path)
        
        if self.output_json:
            self.files.append({
                "path": relative_path,
                "content": content
            })
        else:
            file_path.write_text(content, encoding='utf-8')
            print(f"[+] Generated: {file_path}")
        
        if list_mappers:
            print(f"[!] Detected list mapping - injected {len(list_mappers)} mapper(s) in constructor")
    
    def _to_pascal_case(self, text: str) -> str:
        """Convert text to PascalCase."""
        words = text.replace('_', ' ').replace('-', ' ').split()
        return ''.join(word.capitalize() for word in words)


def parse_field_mappings_from_args(mapping_args: List[str]) -> List[Tuple[str, str]]:
    """Parse field mapping definitions from command line arguments."""
    mappings = []
    for mapping_arg in mapping_args:
        if '=' in mapping_arg:
            # Custom mapping: domainField=responseField
            domain_field, response_field = mapping_arg.split('=', 1)
            mappings.append((domain_field.strip(), response_field.strip()))
        else:
            # Simple mapping: same name for both
            field_name = mapping_arg.strip()
            mappings.append((field_name, field_name))
    
    return mappings


def parse_mapper_from_json(json_file: str) -> Tuple[str, str, str, List[Tuple[str, str]]]:
    """Parse mapper definition from JSON file."""
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        mapper_name = data.get('mapperName')
        response_type = data.get('responseType')
        domain_type = data.get('domainType')
        
        if not mapper_name or not response_type or not domain_type:
            print(f"[!] Error: JSON file must contain 'mapperName', 'responseType', and 'domainType' fields")
            sys.exit(1)
        
        # Field mappings can be a dict (custom) or list (simple)
        field_mappings_data = data.get('fieldMappings', {})
        
        if isinstance(field_mappings_data, dict):
            # Custom mappings: {"domainField": "responseField"}
            mappings = [(domain, response) for domain, response in field_mappings_data.items()]
        elif isinstance(field_mappings_data, list):
            # Simple mappings: ["field1", "field2"]
            mappings = [(field, field) for field in field_mappings_data]
        else:
            print(f"[!] Error: 'fieldMappings' must be a dict or list")
            sys.exit(1)
        
        return mapper_name, response_type, domain_type, mappings
    
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
        description='Generate mapper classes for data layer',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Simple mapping (same field names)
  python generate_mapper.py notifications NotificationMapper NotificationResponse Notification id title message
  
  # Custom mapping (different field names)
  python generate_mapper.py products ProductMapper ProductResponse Product id name price description=desc
  
  # From JSON file
  python generate_mapper.py branchprofile BranchMapper --json mapper.json

JSON file format (custom mappings):
{
  "mapperName": "BranchMapper",
  "responseType": "BranchProfileResponse",
  "domainType": "BranchProfile",
  "fieldMappings": {
    "id": "id",
    "name": "branchName",
    "isActive": "active"
  }
}

JSON file format (simple mappings):
{
  "mapperName": "ProductMapper",
  "responseType": "ProductResponse",
  "domainType": "Product",
  "fieldMappings": ["id", "name", "price", "description"]
}
        '''
    )
    
    parser.add_argument('feature_name', help='Name of the feature (e.g., notifications, products)')
    parser.add_argument('mapper_name', nargs='?', help='Name of the mapper class (PascalCase)')
    parser.add_argument('response_type', nargs='?', help='Response model type name')
    parser.add_argument('domain_type', nargs='?', help='Domain model type name')
    parser.add_argument('field_mappings', nargs='*', help='Field mappings (field or domainField=responseField)')
    parser.add_argument('--json', dest='json_file', help='JSON file containing mapper definition')
    parser.add_argument('--config', default=None, help='Path to config.json (default: config.json)')
    parser.add_argument('--output-json', action='store_true', help='Output file contents as JSON instead of writing to disk')
    
    args = parser.parse_args()
    
    # Parse mapper definition based on input method
    if args.json_file:
        mapper_name, response_type, domain_type, field_mappings = parse_mapper_from_json(args.json_file)
    else:
        if not args.mapper_name or not args.response_type or not args.domain_type:
            print("[!] Error: mapper_name, response_type, and domain_type are required when not using --json")
            parser.print_help()
            sys.exit(1)
        
        mapper_name = args.mapper_name
        response_type = args.response_type
        domain_type = args.domain_type
        
        if not args.field_mappings:
            print("[!] Error: At least one field mapping is required")
            print("[!] Usage: python generate_mapper.py <feature> <mapper> <response> <domain> field1 field2=responseField2 ...")
            sys.exit(1)
        
        field_mappings = parse_field_mappings_from_args(args.field_mappings)
    
    if not field_mappings:
        print("[!] Error: No field mappings provided")
        sys.exit(1)
    
    # Path/package from config only
    config = load_config(getattr(args, 'config', None))
    generator = MapperGenerator(args.feature_name, config, output_json=args.output_json)
    generator.generate(mapper_name, response_type, domain_type, field_mappings)


if __name__ == '__main__':
    main()

