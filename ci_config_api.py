#!/usr/bin/env python3
# Copyright Advanced Micro Devices, Inc.
# SPDX-License-Identifier: MIT

"""CI configuration API.

Schema
------
- V2 (runner-config-v2.json): Current schema with build_runners and gpu_runner_labels.

Usage in workflows:
    from ci_config_api import load_config
    config = load_config()
    runners = config.build_runners
    labels = config.get_gpu_runner_labels()
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CONFIG_FILENAME = "runner-config-v2.json"


class ConfigError(Exception):
    """Raised when configuration loading or validation fails."""

    pass


def _load_raw_config(config_path: Path | None) -> dict[str, Any]:
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


@dataclass
class Config:
    """Configuration schema."""

    build_runners: dict[str, Any]
    gpu_runner_labels: dict[str, Any]
    _raw: dict[str, Any]

    def get_gpu_runner_labels(self) -> dict[str, Any]:
        """Get GPU runner labels organized by family name and platform."""
        return self.gpu_runner_labels


def _adapt_config(raw: dict[str, Any]) -> Config:
    """Adapt JSON to Config interface."""
    missing = [k for k in ("build_runners", "gpu_runner_labels") if k not in raw]
    if missing:
        raise ConfigError(f"Config missing required keys: {missing}")
    return Config(
        build_runners=raw["build_runners"],
        gpu_runner_labels=raw["gpu_runner_labels"],
        _raw=raw,
    )


def load_config(config_path: Path | None = None) -> Config:
    """Load configuration. Recommended entry point."""
    raw = _load_raw_config(config_path)
    return _adapt_config(raw)


# =============================================================================
# Convenience functions (backward compat with existing code patterns)
# =============================================================================


def config_exists(config_path: Path | None = None) -> bool:
    """Check if configuration file exists."""
    if config_path is None:
        config_path = Path(__file__).parent
    return (config_path / CONFIG_FILENAME).exists()


def get_config_version(config: dict[str, Any]) -> int:
    """Get the version from a raw config dict."""
    return config.get("version", 2)


def log_config_version(config: dict[str, Any], config_path: Path) -> None:
    """Log the configuration version and path for traceability."""
    version = get_config_version(config)
    logging.info(f"Loaded CI config v{version} from: {config_path}")


def load_runner_config(config_path: Path | None = None) -> dict[str, Any]:
    """Load configuration and return raw dict."""
    return load_config(config_path)._raw


def get_build_runners(config: dict[str, Any]) -> dict[str, Any]:
    """Get build runners from raw config dict."""
    return config.get("build_runners", {})


def get_gpu_runner_labels(config: dict[str, Any]) -> dict[str, Any]:
    """Get GPU runner labels from config dict."""
    return config.get("gpu_runner_labels", {})


def get_runner_labels(config: dict[str, Any]) -> dict[str, Any]:
    """Deprecated: Use get_gpu_runner_labels() instead."""
    return get_gpu_runner_labels(config)


def print_config_summary(config_path: Path | None = None) -> None:
    """Print a summary of configuration."""
    print("=== Config ===")
    config = load_config(config_path)
    print(f"Build runners: {list(config.build_runners.keys())}")
    print(f"GPU runner labels: {list(config.gpu_runner_labels.keys())}")


if __name__ == "__main__":
    import sys

    path = Path(sys.argv[1]) if len(sys.argv) > 1 else None

    try:
        print_config_summary(path)
    except ConfigError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
