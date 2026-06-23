#!/usr/bin/env python3
"""
Presentation Layer Boilerplate Generator for Clean Architecture

This script generates the presentation layer structure for a new feature following Clean Architecture principles.
It creates the necessary folders and Kotlin boilerplate files.

Usage:
    python generate_presentation_layer.py <feature_name> [--config config.json]

Example:
    python generate_presentation_layer.py userprofile
    python generate_presentation_layer.py notifications --config my_config.json
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


class PresentationLayerGenerator:
    """Generates presentation layer boilerplate for a feature."""
    
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
        
    def generate(self, feature_name: str) -> None:
        """
        Generate the complete presentation layer for a feature.
        
        Args:
            feature_name: Name of the feature (e.g., 'userprofile', 'notifications')
        """
        feature_name_lower = feature_name.lower()
        feature_name_pascal = self._to_pascal_case(feature_name)

        self.path_segment = get_path_segment(self.config, feature_name)
        self.package_prefix = get_package_prefix(self.config, feature_name)

        if not self.output_json:
            print(f"[*] Generating presentation layer for feature: {feature_name_pascal}")
        
        folders = self._create_folder_structure(feature_name_lower)
        
        self._generate_contract_file(feature_name_lower, feature_name_pascal)
        self._generate_viewmodel_file(feature_name_lower, feature_name_pascal)
        self._generate_screen_file(feature_name_lower, feature_name_pascal)
        self._generate_screen_content_file(feature_name_lower, feature_name_pascal)
        self._generate_presentation_module_file(feature_name_lower, feature_name_pascal)
        
        if self.output_json:
            # Output JSON with file contents
            result = {
                "files": self.files,
                "message": f"Presentation layer generated successfully for feature: {feature_name_pascal}"
            }
            print(json.dumps(result))
        else:
            print(f"\n[+] Presentation layer generated successfully!")
            print(f"[>] Location: {self.base_path / self.path_segment / 'presentation'}")
            print(f"\n[!] Next steps:")
            print(f"   1. Define events, state, and effects in {feature_name_pascal}Contract")
            print(f"   2. Implement event handling in {feature_name_pascal}ViewModel")
            print(f"   3. Add UI models in model/")
            print(f"   4. Create screen content composable in component/")
        
    def _create_folder_structure(self, feature_name: str) -> Dict[str, Path]:
        """Create the folder structure. Path from config."""
        feature_path = self.base_path / self.path_segment
        
        folders = {
            'presentation': feature_path / 'presentation',
            'component': feature_path / 'presentation' / 'component',
            'model': feature_path / 'presentation' / 'model',
            'di': feature_path / 'presentation' / 'di',
        }
        
        if not self.output_json:
            for name, path in folders.items():
                path.mkdir(parents=True, exist_ok=True)
                print(f"[+] Created: {path}")
        
        return folders
    
    def _build_package(self, suffix: str) -> str:
        """Build package name from config package_prefix."""
        rest = suffix.split(".", 1)[-1] if "." in suffix else suffix
        if suffix.startswith("shared."):
            rest = suffix[7:] if len(suffix) > 7 else ""
        if self.base_package:
            return f"{self.base_package}.{self.package_prefix}.{rest}" if rest else f"{self.base_package}.{self.package_prefix}"
        return f"{self.package_prefix}.{rest}" if rest else self.package_prefix
    
    def _generate_contract_file(self, feature_name: str, feature_name_pascal: str) -> None:
        """Generate the Contract file (MVI pattern)."""
        package = self._build_package(f"{feature_name}.presentation")
        
        content = f'''package {package}

import core.presentation.baseviewmodel.UiState
import core.presentation.baseviewmodel.ViewEvent
import core.presentation.baseviewmodel.ViewSideEffect

class {feature_name_pascal}Contract {{
    sealed class Event : ViewEvent {{
        data class Init(
            val isInit: Boolean
        ) : Event()
    }}

    data class State(
        val test: Boolean = false
    ) : UiState

    sealed class Effect : ViewSideEffect {{
        sealed class Navigation : Effect() {{
            data object Back : Navigation()
        }}
    }}
}}
'''
        
        file_path = self.base_path / self.path_segment / 'presentation' / f'{feature_name_pascal}Contract.kt'
        relative_path = str(file_path)
        
        if self.output_json:
            self.files.append({
                "path": relative_path,
                "content": content
            })
        else:
            self._write_file(file_path, content)
            print(f"[+] Generated: {file_path}")
    
    def _generate_viewmodel_file(self, feature_name: str, feature_name_pascal: str) -> None:
        """Generate the ViewModel file."""
        package = self._build_package(f"{feature_name}.presentation")
        
        content = f'''package {package}

import core.presentation.baseviewmodel.BaseViewModel
import core.presentation.baseviewmodel.launch
import core.util.CustomDispatchers
import core.util.Dispatcher
import {package}.{feature_name_pascal}Contract.Effect
import {package}.{feature_name_pascal}Contract.Event
import {package}.{feature_name_pascal}Contract.State
import kotlinx.coroutines.CoroutineDispatcher

class {feature_name_pascal}ViewModel(
    @Dispatcher(CustomDispatchers.IO)
    private val ioDispatcher: CoroutineDispatcher
) : BaseViewModel<State, Event, Effect>(State()) {{
    override fun handleEvents(event: Event) {{
        when (event) {{
            is Event.Init -> {{
            }}
        }}
    }}
}}
'''
        
        file_path = self.base_path / self.path_segment / 'presentation' / f'{feature_name_pascal}ViewModel.kt'
        relative_path = str(file_path)
        
        if self.output_json:
            self.files.append({
                "path": relative_path,
                "content": content
            })
        else:
            self._write_file(file_path, content)
            print(f"[+] Generated: {file_path}")
    
    def _generate_screen_file(self, feature_name: str, feature_name_pascal: str) -> None:
        """Generate the Screen composable file."""
        package = self._build_package(f"{feature_name}.presentation")
        
        content = f'''package {package}

import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.navigation.NavController
import core.presentation.CustomLaunchedEffect
import core.presentation.baseviewmodel.SIDE_EFFECTS_KEY
import core.presentation.baseviewmodel.StateLayout
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.flow.onEach
import org.koin.compose.viewmodel.koinViewModel

@Composable
fun {feature_name_pascal}Screen(
    navController: NavController,
    viewModel: {feature_name_pascal}ViewModel = koinViewModel()
) {{
    val state = viewModel.getState()

    CustomLaunchedEffect(key = Unit) {{ isInit ->
        viewModel.setEvent(
            {feature_name_pascal}Contract.Event.Init(
                isInit = isInit
            )
        )
    }}

    LaunchedEffect(SIDE_EFFECTS_KEY) {{
        viewModel.effect.onEach {{ effect ->
            when (effect) {{
                is {feature_name_pascal}Contract.Effect.Navigation.Back -> {{
                    navController.popBackStack()
                }}
            }}
        }}.collect()
    }}

    StateLayout(
        state = state,
        onCloseError = viewModel::hideError
    ) {{
        {feature_name_pascal}ScreenContent(
            state = state,
            onEventSent = {{ event -> viewModel.setEvent(event) }}
        )
    }}
}}
'''
        
        file_path = self.base_path / self.path_segment / 'presentation' / f'{feature_name_pascal}Screen.kt'
        relative_path = str(file_path)
        
        if self.output_json:
            self.files.append({
                "path": relative_path,
                "content": content
            })
        else:
            self._write_file(file_path, content)
            print(f"[+] Generated: {file_path}")
    
    def _generate_screen_content_file(self, feature_name: str, feature_name_pascal: str) -> None:
        """Generate the Screen Content composable file (empty template)."""
        package = self._build_package(f"{feature_name}.presentation")
        
        content = f'''package {package}

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import core.presentation.baseviewmodel.State

@Composable
fun {feature_name_pascal}ScreenContent(
    state: State<{feature_name_pascal}Contract.State>,
    onEventSent: (event: {feature_name_pascal}Contract.Event) -> Unit
) {{
    // TODO: Implement UI content here
}}
'''
        
        file_path = self.base_path / self.path_segment / 'presentation' / f'{feature_name_pascal}ScreenContent.kt'
        relative_path = str(file_path)
        
        if self.output_json:
            self.files.append({
                "path": relative_path,
                "content": content
            })
        else:
            self._write_file(file_path, content)
            print(f"[+] Generated: {file_path}")
    
    def _generate_presentation_module_file(self, feature_name: str, feature_name_pascal: str) -> None:
        """Generate the Presentation Module DI file."""
        package = self._build_package(f"{feature_name}.presentation.di")
        presentation_package = self._build_package(f"{feature_name}.presentation")
        
        content = f'''package {package}

import {presentation_package}.{feature_name_pascal}ViewModel
import core.util.CustomDispatchers
import org.koin.core.module.dsl.viewModel
import org.koin.core.qualifier.named
import org.koin.dsl.module

val {feature_name}PresentationModule = module {{
    viewModel {{
        {feature_name_pascal}ViewModel(
            ioDispatcher = get(named(CustomDispatchers.IO))
        )
    }}
}}
'''
        
        file_path = self.base_path / self.path_segment / 'presentation' / 'di' / f'{feature_name_pascal}PresentationModule.kt'
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
        """Write content to a file or store it for JSON output."""
        relative_path = str(path)
        
        if self.output_json:
            self.files.append({
                "path": relative_path,
                "content": content
            })
        else:
            path.write_text(content, encoding='utf-8')
            print(f"[+] Generated: {path}")
    
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
        description='Generate presentation layer boilerplate for a new feature',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python generate_presentation_layer.py userprofile
  python generate_presentation_layer.py notifications --config custom_config.json
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
        default='scripts/config.json'
    )
    
    parser.add_argument(
        '--output-json',
        action='store_true',
        help='Output file contents as JSON instead of writing to disk'
    )
    
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)
    
    args = parser.parse_args()
    
    config = load_config(args.config)
    
    generator = PresentationLayerGenerator(config, output_json=args.output_json)
    generator.generate(args.feature_name)


if __name__ == '__main__':
    main()

