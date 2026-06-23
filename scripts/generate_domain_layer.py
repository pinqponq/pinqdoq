#!/usr/bin/env python3
"""
Domain Layer Boilerplate Generator for Clean Architecture

This script generates the domain layer structure for a new feature following Clean Architecture principles.
It creates the necessary folders and Kotlin boilerplate files.

Usage:
    python generate_domain_layer.py <feature_name> [--config config.json]

Example:
    python generate_domain_layer.py userprofile
    python generate_domain_layer.py notifications --config my_config.json
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Dict, Optional

from path_utils import (
    DEFAULT_CONFIG_PATH,
    get_package_prefix,
    get_path_segment,
    is_shared,
)


class DomainLayerGenerator:
    """Generates domain layer boilerplate for a feature."""
    
    def __init__(self, config: Dict, output_json: bool = False):
        """
        Initialize the generator with configuration.
        
        Args:
            config: Configuration dictionary containing paths and package info
            output_json: If True, return file contents as JSON instead of writing to disk
        """
        self.config = config
        self.base_path = Path(config.get('base_path', '.'))
        self.base_package = config.get('base_package', 'com.example.app')
        self.feature_root = config.get('feature_root', 'feature')
        self.output_json = output_json
        self.files = []
        self.path_segment = ""
        self.package_prefix = ""
        self._shared = False
        
    def generate(self, feature_name: str) -> None:
        """
        Generate the complete domain layer for a feature.
        
        Args:
            feature_name: Name of the feature (e.g., 'userprofile', 'notifications')
        """
        feature_name_lower = feature_name.lower()
        feature_name_pascal = self._to_pascal_case(feature_name)

        self.path_segment = get_path_segment(self.config, feature_name)
        self.package_prefix = get_package_prefix(self.config, feature_name)
        self._shared = is_shared(feature_name)

        if not self.output_json:
            print(f"[*] Generating domain layer for feature: {feature_name_pascal}")
        
        folders = self._create_folder_structure(feature_name_lower)
        
        if self._shared:
            # Shared mode: only create folder structure + DI module.
            # Individual repository interfaces are added per domain concept (e.g., ProductsRepository, not SharedRepository).
            self._generate_domain_module_file(feature_name_lower, feature_name_pascal)
        else:
            self._generate_repository_interface(feature_name_lower, feature_name_pascal)
            self._generate_domain_module_file(feature_name_lower, feature_name_pascal)
            # Output JSON with file contents
        
        if self.output_json:
            result = {
                "files": self.files,
                "message": f"Domain layer generated successfully for feature: {feature_name_pascal}"
            }
            print(json.dumps(result))
        else:
            print(f"\n[+] Domain layer generated successfully!")
            loc = self.base_path / self.path_segment / 'domain'
            print(f"[>] Location: {loc}")
            if self._shared:
                print(f"\n[!] Next steps:")
                print(f"   1. Add domain models in model/")
                print(f"   2. Add individual repository interfaces (e.g., ProductsRepository) with add_repository_method")
                print(f"   3. Create use cases in usecase/")
                print(f"   4. Register use cases in SharedDomainModule")
            else:
                print(f"\n[!] Next steps:")
                print(f"   1. Add domain models in model/")
                print(f"   2. Define repository methods in {feature_name_pascal}Repository")
                print(f"   3. Create use cases in usecase/")
                print(f"   4. Register use cases in {feature_name_pascal}DomainModule")
        
    def _create_folder_structure(self, feature_name: str) -> Dict[str, Path]:
        """Create the folder structure. Path from config."""
        feature_path = self.base_path / self.path_segment
        
        folders = {
            'domain': feature_path / 'domain',
            'repository': feature_path / 'domain' / 'repository',
            'model': feature_path / 'domain' / 'model',
            'usecase': feature_path / 'domain' / 'usecase',
            'di': feature_path / 'domain' / 'di',
        }
        
        if not self.output_json:
            for name, path in folders.items():
                path.mkdir(parents=True, exist_ok=True)
                print(f"[+] Created: {path}")
        else:
            # Still create folders even in JSON mode
            for name, path in folders.items():
                path.mkdir(parents=True, exist_ok=True)
        
        return folders
    
    def _build_package(self, suffix: str) -> str:
        """Build package name from config package_prefix."""
        rest = suffix.split(".", 1)[-1] if "." in suffix else suffix
        if suffix.startswith("shared."):
            rest = suffix[7:] if len(suffix) > 7 else ""
        if self.base_package:
            return f"{self.base_package}.{self.package_prefix}.{rest}" if rest else f"{self.base_package}.{self.package_prefix}"
        return f"{self.package_prefix}.{rest}" if rest else self.package_prefix
    
    def _generate_repository_interface(self, feature_name: str, feature_name_pascal: str) -> None:
        """Generate the Repository interface file. Only called for non-shared features."""
        repo_class = f"{feature_name_pascal}Repository"
        package = self._build_package(f"{feature_name}.domain.repository")
        
        content = f'''package {package}

interface {repo_class} {{
}}
'''
        
        file_path = self.base_path / self.path_segment / 'domain' / 'repository' / f'{repo_class}.kt'
        relative_path = str(file_path)
        
        if self.output_json:
            self.files.append({
                "path": relative_path,
                "content": content
            })
        else:
            self._write_file(file_path, content)
            print(f"[+] Generated: {file_path}")
    
    def _generate_domain_module_file(self, feature_name: str, feature_name_pascal: str) -> None:
        """Generate the Domain Module DI file."""
        module_var = "sharedDomainModule" if self._shared else f"{feature_name}DomainModule"
        package = self._build_package(f"{feature_name}.domain.di")
        
        # Both shared and feature modes start with an empty module — use cases registered later
        content = f'''package {package}

import org.koin.core.module.dsl.singleOf
import org.koin.dsl.module

val {module_var} = module {{
}}
'''
        
        if self._shared:
            file_path = self.base_path / self.path_segment / 'domain' / 'di' / 'SharedDomainModule.kt'
        else:
            file_path = self.base_path / self.path_segment / 'domain' / 'di' / f'{feature_name_pascal}DomainModule.kt'
        relative_path = str(file_path)
        
        if self.output_json:
            self.files.append({
                "path": relative_path,
                "content": content
            })
        else:
            self._write_file(file_path, content)
            print(f"[+] Generated: {file_path}")
    
    def _write_file(self, path: Path, content: str) -> None:
        """Write content to a file."""
        path.write_text(content, encoding='utf-8')
    
    def _to_pascal_case(self, text: str) -> str:
        """Convert text to PascalCase."""
        words = text.replace('_', ' ').replace('-', ' ').split()
        return ''.join(word.capitalize() for word in words)


def load_config(config_path: Optional[str] = None) -> Dict:
    """
    Load configuration from file or use defaults.
    
    Args:
        config_path: Path to configuration JSON file
        
    Returns:
        Configuration dictionary
    """
    default_config = {
        "base_path": "composeApp/src/commonMain/kotlin",
        "base_package": "",
        "feature_root": "feature",
        "shared_root": "shared",
    }
    
    config_path = config_path or DEFAULT_CONFIG_PATH
    if config_path and os.path.exists(config_path):
        with open(config_path, 'r') as f:
            user_config = json.load(f)
            for key, value in user_config.items():
                default_config[key] = value
    
    return default_config


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description='Generate domain layer boilerplate for a new feature',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python generate_domain_layer.py userprofile
  python generate_domain_layer.py notifications --config custom_config.json
        '''
    )
    
    parser.add_argument(
        'feature_name',
        type=str,
        help='Name of the feature to generate (e.g., userprofile, notifications)'
    )
    
    parser.add_argument(
        '--config',
        type=str,
        help='Path to configuration JSON file',
        default=None
    )
    
    parser.add_argument(
        '--output-json',
        action='store_true',
        help='Output file contents as JSON instead of writing to disk'
    )
    
    parser.add_argument(
        '--shared',
        action='store_true',
        help='Target shared layer (path shared/..., packages shared.*)'
    )
    
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)
    
    args = parser.parse_args()
    
    config = load_config(args.config)
    generator = DomainLayerGenerator(config, output_json=args.output_json)
    generator.generate(args.feature_name)


if __name__ == '__main__':
    main()

