#!/usr/bin/env python3
"""
Data Layer Boilerplate Generator for Clean Architecture

This script generates the data layer structure for a new feature following Clean Architecture principles.
It creates the necessary folders and Kotlin boilerplate files.

Usage:
    python generate_data_layer.py <feature_name> [--config config.json]

Example:
    python generate_data_layer.py userprofile
    python generate_data_layer.py notifications --config my_config.json
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


class DataLayerGenerator:
    """Generates data layer boilerplate for a feature."""
    
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
        Generate the complete data layer for a feature.
        
        Args:
            feature_name: Name of the feature (e.g., 'userprofile', 'notifications')
        """
        feature_name_lower = feature_name.lower()
        feature_name_pascal = self._to_pascal_case(feature_name)

        self.path_segment = get_path_segment(self.config, feature_name)
        self.package_prefix = get_package_prefix(self.config, feature_name)
        self._shared = is_shared(feature_name)

        if not self.output_json:
            print(f"[*] Generating data layer for feature: {feature_name_pascal}")
        
        # Create folder structure
        folders = self._create_folder_structure(feature_name_lower)
        
        if self._shared:
            # Shared mode: only create folder structure + DI module.
            # Individual services/repos are added per domain concept (e.g., ProductsService, not SharedService).
            self._generate_data_module_file(feature_name_lower, feature_name_pascal,
                                            service_class=None, repo_class=None, repo_impl_class=None)
        else:
            service_class = f"{feature_name_pascal}Service"
            repo_class = f"{feature_name_pascal}Repository"
            repo_impl_class = f"{feature_name_pascal}RepositoryImpl"
            self._generate_service_file(feature_name_lower, feature_name_pascal, service_class)
            self._generate_repository_impl_file(feature_name_lower, feature_name_pascal, repo_class, repo_impl_class)
            self._generate_data_module_file(feature_name_lower, feature_name_pascal, service_class, repo_class, repo_impl_class)
            # Output JSON with file contents
        
        if self.output_json:
            result = {
                "files": self.files,
                "message": f"Data layer generated successfully for feature: {feature_name_pascal}"
            }
            print(json.dumps(result))
        else:
            print(f"\n[+] Data layer generated successfully!")
            loc = self.base_path / self.path_segment / 'data'
            print(f"[>] Location: {loc}")
            if self._shared:
                print(f"\n[!] Next steps:")
                print(f"   1. Add individual services (e.g., ProductsService) with add_service_method")
                print(f"   2. Add individual repositories with add_repository_method")
                print(f"   3. Add request/response models, mappers, and use cases per domain concept")
                print(f"   4. Register each in SharedDataModule")
            else:
                print(f"\n[!] Next steps:")
                print(f"   1. Add request/response models in model/request/ and model/response/")
                print(f"   2. Create mapper functions in model/mapper/")
                print(f"   3. Implement service methods in {feature_name_pascal}Service")
                print(f"   4. Implement repository methods in {feature_name_pascal}RepositoryImpl")
        
    def _create_folder_structure(self, feature_name: str) -> Dict[str, Path]:
        """Create the folder structure for the data layer. Path from config."""
        feature_path = self.base_path / self.path_segment
        
        folders = {
            'data': feature_path / 'data',
            'datasource': feature_path / 'data' / 'datasource',
            'remote': feature_path / 'data' / 'datasource' / 'remote',
            'model': feature_path / 'data' / 'datasource' / 'remote' / 'model',
            'mapper': feature_path / 'data' / 'datasource' / 'remote' / 'model' / 'mapper',
            'request': feature_path / 'data' / 'datasource' / 'remote' / 'model' / 'request',
            'response': feature_path / 'data' / 'datasource' / 'remote' / 'model' / 'response',
            'repository': feature_path / 'data' / 'repository',
            'di': feature_path / 'data' / 'di',
        }
        
        if not self.output_json:
            for name, path in folders.items():
                path.mkdir(parents=True, exist_ok=True)
                print(f"[+] Created: {path}")
        
        return folders
    
    def _build_package(self, suffix: str, feature_name: str = "") -> str:
        """Build package name from config package_prefix."""
        rest = suffix.split(".", 1)[-1] if "." in suffix else suffix
        if suffix.startswith("shared."):
            rest = suffix[7:] if len(suffix) > 7 else ""
        if self.base_package:
            return f"{self.base_package}.{self.package_prefix}.{rest}" if rest else f"{self.base_package}.{self.package_prefix}"
        return f"{self.package_prefix}.{rest}" if rest else self.package_prefix
    
    def _generate_service_file(self, feature_name: str, feature_name_pascal: str, service_class: str = None) -> None:
        """Generate the Service class file. Only called for non-shared features."""
        if service_class is None:
            service_class = f"{feature_name_pascal}Service"
        package = self._build_package(f"{feature_name}.data.datasource.remote", feature_name)
        
        content = f'''package {package}

import networking.DevengNetworkingModule
import networking.util.DevengHttpMethod

class {service_class}(
    private val devengNetworkingModule: DevengNetworkingModule
) {{
}}
'''
        
        file_path = self.base_path / self.path_segment / 'data' / 'datasource' / 'remote' / f'{service_class}.kt'
        relative_path = str(file_path)
        
        if self.output_json:
            self.files.append({
                "path": relative_path,
                "content": content
            })
        else:
            self._write_file(file_path, content)
            print(f"[+] Generated: {file_path}")
    
    def _generate_repository_impl_file(self, feature_name: str, feature_name_pascal: str, repo_class: str, repo_impl_class: str) -> None:
        """Generate the Repository implementation file. Only called for non-shared features."""
        package = self._build_package(f"{feature_name}.data.repository")
        domain_package = self._build_package(f"{feature_name}.domain")
        service_package = self._build_package(f"{feature_name}.data.datasource.remote")
        service_class = f"{feature_name_pascal}Service"
        service_name_camel = feature_name_pascal[0].lower() + feature_name_pascal[1:] + "Service"
        
        content = f'''package {package}

import {domain_package}.repository.{repo_class}
import {service_package}.{service_class}

class {repo_impl_class}(
    private val {service_name_camel}: {service_class}
) : {repo_class} {{
}}
'''
        
        file_path = self.base_path / self.path_segment / 'data' / 'repository' / f'{repo_impl_class}.kt'
        relative_path = str(file_path)
        
        if self.output_json:
            self.files.append({
                "path": relative_path,
                "content": content
            })
        else:
            self._write_file(file_path, content)
            print(f"[+] Generated: {file_path}")

    def _generate_data_module_file(self, feature_name: str, feature_name_pascal: str, service_class: str, repo_class: str, repo_impl_class: str) -> None:
        """Generate the Data Module DI file."""
        package = self._build_package(f"{feature_name}.data.di")
        module_var = "sharedDataModule" if self._shared else f"{feature_name}DataModule"
        
        if self._shared:
            content = f'''package {package}

import org.koin.core.module.dsl.singleOf
import org.koin.dsl.bind
import org.koin.dsl.module

val {module_var} = module {{
}}
'''
        else:
            service_package = self._build_package(f"{feature_name}.data.datasource.remote")
            repo_impl_package = self._build_package(f"{feature_name}.data.repository")
            repo_package = self._build_package(f"{feature_name}.domain.repository")
            
            content = f'''package {package}

import {service_package}.{service_class}
import {repo_impl_package}.{repo_impl_class}
import {repo_package}.{repo_class}
import org.koin.core.module.dsl.singleOf
import org.koin.dsl.bind
import org.koin.dsl.module

val {module_var} = module {{
    singleOf(::{service_class})
    singleOf(::{repo_impl_class}).bind<{repo_class}>()
}}
'''
        
        if self._shared:
            file_path = self.base_path / self.path_segment / 'data' / 'di' / 'SharedDataModule.kt'
        else:
            file_path = self.base_path / self.path_segment / 'data' / 'di' / f'{feature_name_pascal}DataModule.kt'
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
        # Handle camelCase, snake_case, kebab-case
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
            # Update defaults with user config (including empty strings)
            for key, value in user_config.items():
                default_config[key] = value
    
    return default_config


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description='Generate data layer boilerplate for a new feature',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python generate_data_layer.py userprofile
  python generate_data_layer.py notifications --config custom_config.json

Configuration file (JSON format):
  {
    "base_path": "composeApp/src/commonMain/kotlin",
    "base_package": "com.example.app",
    "feature_root": "feature"
  }
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
    
    # Load configuration (path from config only; --shared means feature_name is shared)
    config = load_config(args.config)

    # Generate data layer
    generator = DataLayerGenerator(config, output_json=args.output_json)
    generator.generate(args.feature_name)


if __name__ == '__main__':
    main()

