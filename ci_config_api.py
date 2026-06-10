#!/usr/bin/env python3
# Copyright Advanced Micro Devices, Inc.
# SPDX-License-Identifier: MIT

"""Versioned CI configuration API.

This module provides a stable API for loading CI configuration from
therock-ci-config. Consumers should use versioned functions (e.g.,
load_config_v1) to ensure compatibility across schema changes.

Usage:
    from ci_config_api import load_config_v1

    config = load_config_v1()  # Loads from current directory
    runners = config.build_runners
    families = config.get_gpu_families(["presubmit"])
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CURRENT_VERSION = "1"
CONFIG_FILENAME = "runner-config.json"


class ConfigError(Exception):
    """Raised when configuration loading or validation fails."""

    pass


@dataclass
class ConfigV1:
    """Version 1 configuration schema.

    Attributes:
        build_runners: Build runner labels with weighted distribution.
        gpu_families: GPU family configurations by trigger type.
    """

    build_runners: dict[str, Any]
    gpu_families: dict[str, Any]
    _raw: dict[str, Any]

    def get_gpu_families(self, trigger_types: list[str]) -> dict[str, Any]:
        """Get GPU families for the specified trigger types.

        Args:
            trigger_types: List of trigger types (presubmit, postsubmit, nightly).

        Returns:
            Combined dict of GPU family configurations.
        """
        result: dict[str, Any] = {}
        for trigger_type in trigger_types:
            if trigger_type in self.gpu_families:
                for name, config in self.gpu_families[trigger_type].items():
                    result[name] = config
        return result


def load_config_v1(config_path: Path | None = None) -> ConfigV1:
    """Load version 1 configuration.

    Args:
        config_path: Path to config directory. Defaults to current directory.

    Returns:
        ConfigV1 instance with loaded configuration.

    Raises:
        ConfigError: If config file is missing, invalid, or version mismatch.
    """
    if config_path is None:
        config_path = Path(__file__).parent

    config_file = config_path / CONFIG_FILENAME

    if not config_file.exists():
        raise ConfigError(f"Config not found: {config_file}")

    try:
        with open(config_file) as f:
            raw = json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigError(f"Invalid JSON in {config_file}: {e}")

    version = raw.get("version", "1")
    if version != CURRENT_VERSION:
        raise ConfigError(
            f"Config version mismatch: got {version}, expected {CURRENT_VERSION}"
        )

    missing = [k for k in ("build_runners", "gpu_families") if k not in raw]
    if missing:
        raise ConfigError(f"Config missing required keys: {missing}")

    return ConfigV1(
        build_runners=raw["build_runners"],
        gpu_families=raw["gpu_families"],
        _raw=raw,
    )


def config_exists(config_path: Path | None = None) -> bool:
    """Check if configuration file exists.

    Args:
        config_path: Path to config directory. Defaults to current directory.

    Returns:
        True if runner-config.json exists in the specified path.
    """
    if config_path is None:
        config_path = Path(__file__).parent
    return (config_path / CONFIG_FILENAME).exists()


def get_config_version(config: dict[str, Any]) -> str:
    """Get the version string from a raw config dict.

    Args:
        config: Raw configuration dictionary.

    Returns:
        Version string (defaults to "1" if not specified).
    """
    return config.get("version", "1")


def log_config_version(config: dict[str, Any], config_path: Path) -> None:
    """Log the configuration version and path for traceability.

    Args:
        config: Raw configuration dictionary.
        config_path: Path where config was loaded from.
    """
    version = get_config_version(config)
    logging.info(f"Loaded CI config v{version} from: {config_path}")


# Convenience functions for working with raw config dicts
# (backwards compatibility with existing code patterns)


def load_runner_config(config_path: Path | None = None) -> dict[str, Any]:
    """Load configuration and return raw dict.

    Args:
        config_path: Path to config directory.

    Returns:
        Raw configuration dictionary.
    """
    return load_config_v1(config_path)._raw


def get_build_runners(config: dict[str, Any]) -> dict[str, Any]:
    """Get build runners from raw config dict.

    Args:
        config: Raw configuration dictionary.

    Returns:
        Build runners configuration.
    """
    return config.get("build_runners", {})


def get_gpu_families(config: dict[str, Any], trigger_types: list[str]) -> dict[str, Any]:
    """Get GPU families from raw config dict.

    Args:
        config: Raw configuration dictionary.
        trigger_types: List of trigger types to include.

    Returns:
        Combined GPU family configurations.
    """
    gpu_families = config.get("gpu_families", {})
    result: dict[str, Any] = {}
    for trigger_type in trigger_types:
        if trigger_type in gpu_families:
            for name, cfg in gpu_families[trigger_type].items():
                result[name] = cfg
    return result


if __name__ == "__main__":
    import sys

    path = Path(sys.argv[1]) if len(sys.argv) > 1 else None

    try:
        config = load_config_v1(path)
        print(f"Loaded config v{CURRENT_VERSION}")
        print(f"Build runners: {list(config.build_runners.keys())}")
        print(f"GPU families (presubmit): {list(config.get_gpu_families(['presubmit']).keys())}")
    except ConfigError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
