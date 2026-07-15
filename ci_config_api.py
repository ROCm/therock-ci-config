#!/usr/bin/env python3
# Copyright Advanced Micro Devices, Inc.
# SPDX-License-Identifier: MIT

"""Versioned CI configuration API.

Version Compatibility
---------------------
This API provides forward and backward compatibility between workflow versions:

- Single JSON file (runner-config.json) always contains the latest schema
- Each load_config_vN() function provides a stable interface for version N
- When JSON schema upgrades, older loaders adapt the new data to their interface

Example: When JSON upgrades from v1 to v2:
- load_config_v1() reads v2 JSON and transforms it to v1 interface (backward compat)
- load_config_v2() reads v2 JSON directly
- Old workflows keep calling load_config_v1() and continue working

Usage in workflows:
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
SUPPORTED_VERSIONS = ["1"]
LATEST_VERSION = "1"
CONFIG_FILENAME = "runner-config.json"


class ConfigError(Exception):
    """Raised when configuration loading or validation fails."""

    pass


def _load_raw_config(config_path: Path | None = None) -> dict[str, Any]:
    """Load raw JSON config file."""
    if config_path is None:
        config_path = Path(__file__).parent

    config_file = config_path / CONFIG_FILENAME

    if not config_file.exists():
        raise ConfigError(f"Config not found: {config_file}")

    try:
        with open(config_file) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigError(f"Invalid JSON in {config_file}: {e}")


# =============================================================================
# Version 1 API
# =============================================================================


@dataclass
class ConfigV1:
    """Version 1 configuration schema."""

    build_runners: dict[str, Any]
    gpu_families: dict[str, Any]
    _raw: dict[str, Any]

    def get_gpu_families(self, trigger_types: list[str]) -> dict[str, Any]:
        """Get GPU families for the specified trigger types."""
        result: dict[str, Any] = {}
        for trigger_type in trigger_types:
            if trigger_type in self.gpu_families:
                for name, config in self.gpu_families[trigger_type].items():
                    result[name] = config
        return result


def _adapt_to_v1(raw: dict[str, Any]) -> ConfigV1:
    """Adapt any supported JSON version to V1 interface."""
    version = raw.get("version", "1")

    if version == "1":
        # Direct load
        missing = [k for k in ("build_runners", "gpu_families") if k not in raw]
        if missing:
            raise ConfigError(f"Config missing required keys: {missing}")
        return ConfigV1(
            build_runners=raw["build_runners"],
            gpu_families=raw["gpu_families"],
            _raw=raw,
        )

    # Future: when v2 exists, transform v2 data to v1 interface here
    # if version == "2":
    #     return ConfigV1(
    #         build_runners=raw["build_runners"],
    #         gpu_families=_transform_v2_families_to_v1(raw),
    #         _raw=raw,
    #     )

    raise ConfigError(
        f"Config version {version} not supported by load_config_v1(). "
        f"Supported: {SUPPORTED_VERSIONS}"
    )


def load_config_v1(config_path: Path | None = None) -> ConfigV1:
    """Load configuration with V1 interface (backward compatible)."""
    raw = _load_raw_config(config_path)
    return _adapt_to_v1(raw)


# =============================================================================
# Future: Version 2 API (uncomment when v2 schema is ready)
# =============================================================================

# @dataclass
# class ConfigV2:
#     """Version 2 configuration schema."""
#     build_runners: dict[str, Any]
#     gfx_targets: dict[str, Any]  # Example: renamed from gpu_families
#     _raw: dict[str, Any]
#
#     def get_targets(self, trigger_types: list[str]) -> dict[str, Any]:
#         ...
#
# def _adapt_to_v2(raw: dict[str, Any]) -> ConfigV2:
#     """Adapt any supported JSON version to V2 interface."""
#     version = raw.get("version", "1")
#     if version == "2":
#         return ConfigV2(...)  # Direct load
#     raise ConfigError(f"Config version {version} cannot be loaded as V2")
#
# def load_config_v2(config_path: Path | None = None) -> ConfigV2:
#     """Load configuration with V2 interface."""
#     raw = _load_raw_config(config_path)
#     return _adapt_to_v2(raw)


# =============================================================================
# Convenience functions (backward compat with existing code patterns)
# =============================================================================


def config_exists(config_path: Path | None = None) -> bool:
    """Check if configuration file exists."""
    if config_path is None:
        config_path = Path(__file__).parent
    return (config_path / CONFIG_FILENAME).exists()


def get_config_version(config: dict[str, Any]) -> str:
    """Get the version string from a raw config dict."""
    return config.get("version", "1")


def log_config_version(config: dict[str, Any], config_path: Path) -> None:
    """Log the configuration version and path for traceability."""
    version = get_config_version(config)
    logging.info(f"Loaded CI config v{version} from: {config_path}")


def load_runner_config(config_path: Path | None = None) -> dict[str, Any]:
    """Load configuration and return raw dict."""
    return load_config_v1(config_path)._raw


def get_build_runners(config: dict[str, Any]) -> dict[str, Any]:
    """Get build runners from raw config dict."""
    return config.get("build_runners", {})


def get_gpu_families(
    config: dict[str, Any], trigger_types: list[str]
) -> dict[str, Any]:
    """Get GPU families from raw config dict for specified trigger types.

    Note: For new code that only needs runner labels, prefer get_runner_labels()
    which provides a simpler flat structure without trigger type organization.
    """
    gpu_families = config.get("gpu_families", {})
    result: dict[str, Any] = {}
    for trigger_type in trigger_types:
        if trigger_type in gpu_families:
            for name, cfg in gpu_families[trigger_type].items():
                result[name] = cfg
    return result


def get_runner_labels(config: dict[str, Any]) -> dict[str, Any]:
    """Get runner labels from config dict.

    Returns the runner_labels section which contains only runner-related
    configuration (test-runs-on, benchmark-runs-on, etc.) organized by
    family name and platform.

    New code should prefer this over get_gpu_families() when only runner
    labels are needed, as it provides a simpler flat structure.
    """
    return config.get("runner_labels", {})


if __name__ == "__main__":
    import sys

    path = Path(sys.argv[1]) if len(sys.argv) > 1 else None

    try:
        config = load_config_v1(path)
        print(f"Loaded config (latest: v{LATEST_VERSION})")
        print(f"Build runners: {list(config.build_runners.keys())}")
        print(
            f"GPU families (presubmit): {list(config.get_gpu_families(['presubmit']).keys())}"
        )
    except ConfigError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
