"""
Path and package helpers driven by config.json (Plan B).
Single source of truth: path segment and package prefix come from config only.
"""

DEFAULT_CONFIG_PATH = "Mobile/scripts/config.json"


def is_shared(feature_name: str) -> bool:
    """True when feature_name is the shared layer."""
    return feature_name.lower() == "shared"


def get_path_segment(config: dict, feature_name: str) -> str:
    """
    First path segment under base_path.
    Shared: config["shared_root"] (default "shared").
    Feature: config["feature_root"]/feature_name (e.g. feature/login).
    """
    if is_shared(feature_name):
        return config.get("shared_root", "shared")
    return f"{config.get('feature_root', 'feature')}/{feature_name}"


def get_package_prefix(config: dict, feature_name: str) -> str:
    """
    Package prefix (no trailing dot).
    Shared: config["shared_root"] (default "shared").
    Feature: config["feature_root"].feature_name (e.g. feature.login).
    """
    if is_shared(feature_name):
        return config.get("shared_root", "shared")
    return f"{config.get('feature_root', 'feature')}.{feature_name}"
