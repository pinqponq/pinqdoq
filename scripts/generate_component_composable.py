#!/usr/bin/env python3
"""
Generate a template Composable file under presentation/component for a feature.

Usage:
    python scripts/generate_component_composable.py <feature_name> <ComponentName>

Examples:
    python scripts/generate_component_composable.py orders OrderCard

Behavior:
    - Creates file: composeApp/src/commonMain/kotlin/feature/<feature>/presentation/component/<ComponentName>.kt
    - Adds a basic @Composable and a @Preview in the same file
    - Uses project config from scripts/config.json
"""

import json
import sys
from pathlib import Path

from path_utils import (
    DEFAULT_CONFIG_PATH,
    get_package_prefix,
    get_path_segment,
)


def load_config(config_path: str = None) -> dict:
    path = config_path or DEFAULT_CONFIG_PATH
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            "base_path": "composeApp/src/commonMain/kotlin",
            "base_package": "",
            "feature_root": "feature",
            "shared_root": "shared",
        }


def to_pascal_case(text: str) -> str:
    parts = [p for p in text.replace('-', '_').split('_') if p]
    return ''.join(p[:1].upper() + p[1:] for p in parts)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    feature_name = sys.argv[1].lower()
    component_name = to_pascal_case(sys.argv[2])

    config = load_config()
    base_path = Path(config.get('base_path', 'composeApp/src/commonMain/kotlin'))
    path_segment = get_path_segment(config, feature_name)
    package_prefix = get_package_prefix(config, feature_name)

    target_dir = base_path / path_segment / 'presentation' / 'component'
    target_dir.mkdir(parents=True, exist_ok=True)

    target_file = target_dir / f'{component_name}.kt'

    if target_file.exists():
        print(f"[*]  Component already exists: {target_file}")
        print("    Skipping...")
        return

    package_name = f"{package_prefix}.presentation.component"

    template = """package __PACKAGE__

import androidx.compose.desktop.ui.tooling.preview.Preview
import androidx.compose.runtime.Composable
import core.presentation.theme.AppTheme

@Composable
fun __COMPONENT__() {
}

@Preview
@Composable
fun __COMPONENT__Preview() {
    AppTheme {
        __COMPONENT__()
    }
}
"""

    template = template.replace('__PACKAGE__', package_name).replace('__COMPONENT__', component_name)

    with open(target_file, 'w', encoding='utf-8') as f:
        f.write(template)

    print("[+] Generated component:", target_file)
    print("[>] Package:", package_name)


if __name__ == '__main__':
    main()


