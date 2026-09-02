#!/usr/bin/env python3
# Copyright Advanced Micro Devices, Inc.
# SPDX-License-Identifier: MIT

"""Versioned CI configuration API.

Schema Versions
---------------
- V1 (runner-config.json): Legacy schema with gpu_families + gpu_runner_labels.
  Maintained for backward compatibility with existing workflows.
- V2 (runner-config-v2.json): Current/recommended schema with only gpu_runner_labels.
  Use this for new integrations.

Version Compatibility
---------------------
This API provides forward and backward compatibility between workflow versions:

- Separate JSON files for each version (runner-config.json, runner-config-v2.json)
- Each load_config_vN() function loads the corresponding version file
- Existing code using load_config_v1() or load_runner_config() continues to work

Usage in workflows:
    # For new integrations (recommended):
    from ci_config_api import load_config_v2
    config = load_config_v2()

    # For existing workflows (backward compatible):
    from ci_config_api import load_config_v1
    config = load_config_v1()
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Supported versions: loaders exist for all versions in this list
SUPPORTED_VERSIONS = ["1", "2"]
LATEST_VERSION = "2"
CONFIG_FILENAMES = {
    "1": "runner-config.json",
    "2": "runner-config-v2.json",
}


class ConfigError(Exception):
    """Raised when configuration loading or validation fails."""

    pass


def _load_raw_config(
    config_path: Path | None = None, version: str | None = None
) -> dict[str, Any]:
    """Load raw JSON config file for the specified version.

    Args:
        config_path: Directory containing config files. Defaults to this file's parent.
        version: Schema version to load ("1" or "2"). Defaults to LATEST_VERSION.

    Returns:
        Raw configuration dictionary.

    Raises:
        ConfigError: If the config file doesn't exist or contains invalid JSON.
    """
    if config_path is None:
        config_path = Path(__file__).parent

    if version is None:
        version = LATEST_VERSION

    if version not in CONFIG_FILENAMES:
        raise ConfigError(
            f"Unknown config version: {version}. Supported: {list(CONFIG_FILENAMES.keys())}"
        )

    config_file = config_path / CONFIG_FILENAMES[version]

    if not config_file.exists():
        raise ConfigError(f"Config not found: {config_file}")

    try:
        with open(config_file) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigError(f"Invalid JSON in {config_file}: {e}")


# =============================================================================
# Version 1 API (Legacy - for backward compatibility)
# =============================================================================


@dataclass
class ConfigV1:
    """Version 1 configuration schema (legacy).

    V1 config file (runner-config.json) includes both gpu_families and
    gpu_runner_labels. This is maintained for backward compatibility with
    existing workflows in TheRock and other repos.

    For new integrations, use ConfigV2/load_config_v2() instead.
    """

    build_runners: dict[str, Any]
    gpu_families: dict[str, Any]
    gpu_runner_labels: dict[str, Any]
    _raw: dict[str, Any]

    def get_gpu_families(self, trigger_types: list[str]) -> dict[str, Any]:
        """Get GPU families for the specified trigger types."""
        result: dict[str, Any] = {}
        for trigger_type in trigger_types:
            if trigger_type in self.gpu_families:
                for name, config in self.gpu_families[trigger_type].items():
                    result[name] = config
        return result

    def get_gpu_runner_labels(self) -> dict[str, Any]:
        """Get GPU runner labels organized by family name and platform."""
        return self.gpu_runner_labels


def _adapt_to_v1(raw: dict[str, Any]) -> ConfigV1:
    """Adapt V1 JSON to V1 interface."""
    missing = [
        k
        for k in ("build_runners", "gpu_families", "gpu_runner_labels")
        if k not in raw
    ]
    if missing:
        raise ConfigError(f"Config missing required keys: {missing}")
    return ConfigV1(
        build_runners=raw["build_runners"],
        gpu_families=raw["gpu_families"],
        gpu_runner_labels=raw["gpu_runner_labels"],
        _raw=raw,
    )


def load_config_v1(config_path: Path | None = None) -> ConfigV1:
    """Load configuration with V1 interface (legacy).

    Loads runner-config.json (v1 schema) which includes gpu_families.
    Maintained for backward compatibility with existing workflows.

    For new integrations, use load_config_v2() instead.
    """
    raw = _load_raw_config(config_path, version="1")
    return _adapt_to_v1(raw)


# =============================================================================
# Version 2 API (Current - recommended for new integrations)
# =============================================================================


@dataclass
class ConfigV2:
    """Version 2 configuration schema (current/recommended).

    V2 removes gpu_families and uses only gpu_runner_labels for runner config.
    This is the recommended schema for new integrations.
    """

    build_runners: dict[str, Any]
    gpu_runner_labels: dict[str, Any]
    _raw: dict[str, Any]

    def get_gpu_runner_labels(self) -> dict[str, Any]:
        """Get GPU runner labels organized by family name and platform."""
        return self.gpu_runner_labels


def _adapt_to_v2(raw: dict[str, Any]) -> ConfigV2:
    """Adapt V2 JSON to V2 interface."""
    missing = [k for k in ("build_runners", "gpu_runner_labels") if k not in raw]
    if missing:
        raise ConfigError(f"Config missing required keys: {missing}")
    return ConfigV2(
        build_runners=raw["build_runners"],
        gpu_runner_labels=raw["gpu_runner_labels"],
        _raw=raw,
    )


def load_config_v2(config_path: Path | None = None) -> ConfigV2:
    """Load configuration with V2 interface (recommended).

    Loads runner-config-v2.json (v2 schema) which only has gpu_runner_labels.
    This is the recommended loader for new integrations.
    """
    raw = _load_raw_config(config_path, version="2")
    return _adapt_to_v2(raw)


# =============================================================================
# Convenience functions (backward compat with existing code patterns)
# =============================================================================


def config_exists(config_path: Path | None = None, version: str | None = None) -> bool:
    """Check if configuration file exists for the specified version."""
    if config_path is None:
        config_path = Path(__file__).parent
    if version is None:
        version = "1"  # Default to v1 for backward compatibility
    filename = CONFIG_FILENAMES.get(version, CONFIG_FILENAMES["1"])
    return (config_path / filename).exists()


def get_config_version(config: dict[str, Any]) -> str:
    """Get the version string from a raw config dict."""
    return config.get("version", "1")


def log_config_version(config: dict[str, Any], config_path: Path) -> None:
    """Log the configuration version and path for traceability."""
    version = get_config_version(config)
    logging.info(f"Loaded CI config v{version} from: {config_path}")


def load_runner_config(
    config_path: Path | None = None, version: str | None = None
) -> dict[str, Any]:
    """Load configuration and return raw dict.

    Args:
        config_path: Directory containing config files.
        version: Schema version ("1" or "2"). Defaults to "1" for backward compat.
    """
    if version is None:
        version = "1"  # Default to v1 for backward compatibility
    if version == "2":
        return load_config_v2(config_path)._raw
    return load_config_v1(config_path)._raw


def get_build_runners(config: dict[str, Any]) -> dict[str, Any]:
    """Get build runners from raw config dict."""
    return config.get("build_runners", {})


def get_gpu_families(
    config: dict[str, Any], trigger_types: list[str]
) -> dict[str, Any]:
    """Get GPU families from raw config dict for specified trigger types.

    Note: For new code that only needs runner labels, prefer get_gpu_runner_labels()
    which provides a simpler flat structure without trigger type organization.
    """
    gpu_families = config.get("gpu_families", {})
    result: dict[str, Any] = {}
    for trigger_type in trigger_types:
        if trigger_type in gpu_families:
            for name, cfg in gpu_families[trigger_type].items():
                result[name] = cfg
    return result


def get_gpu_runner_labels(config: dict[str, Any]) -> dict[str, Any]:
    """Get GPU runner labels from config dict.

    Returns the gpu_runner_labels section which contains only runner-related
    configuration (test-runs-on, benchmark-runs-on, etc.) organized by
    GPU family name and platform.

    New code should prefer this over get_gpu_families() when only runner
    labels are needed, as it provides a simpler flat structure.
    """
    return config.get("gpu_runner_labels", {})


def get_runner_labels(config: dict[str, Any]) -> dict[str, Any]:
    """Deprecated: Use get_gpu_runner_labels() instead."""
    return get_gpu_runner_labels(config)


if __name__ == "__main__":
    import sys

    path = Path(sys.argv[1]) if len(sys.argv) > 1 else None

    try:
        print("=== V1 Config (Legacy) ===")
        config_v1 = load_config_v1(path)
        print(f"Build runners: {list(config_v1.build_runners.keys())}")
        print(
            f"GPU families (presubmit): {list(config_v1.get_gpu_families(['presubmit']).keys())}"
        )
        print(f"GPU runner labels: {list(config_v1.gpu_runner_labels.keys())}")

        print("\n=== V2 Config (Recommended) ===")
        config_v2 = load_config_v2(path)
        print(f"Build runners: {list(config_v2.build_runners.keys())}")
        print(f"GPU runner labels: {list(config_v2.gpu_runner_labels.keys())}")
    except ConfigError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
