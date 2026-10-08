#!/usr/bin/env python3
# Copyright Advanced Micro Devices, Inc.
# SPDX-License-Identifier: MIT

"""Tests for ci_config_api.py."""

import json
import tempfile
import unittest
from pathlib import Path

from ci_config_api import (
    CONFIG_FILENAME,
    Config,
    ConfigError,
    config_exists,
    get_build_runners,
    get_config_version,
    get_gpu_runner_labels,
    get_runner_labels,
    load_config,
    load_runner_config,
)


class TestLoadConfig(unittest.TestCase):
    def test_loads_real_config(self):
        config = load_config()
        self.assertIsInstance(config, Config)
        self.assertIn("linux", config.build_runners)
        self.assertIn("gfx94x", config.gpu_runner_labels)

    def test_missing_file_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(ConfigError) as ctx:
                load_config(Path(tmpdir))
            self.assertIn("not found", str(ctx.exception))

    def test_invalid_json_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, CONFIG_FILENAME).write_text("{invalid")
            with self.assertRaises(ConfigError) as ctx:
                load_config(Path(tmpdir))
            self.assertIn("Invalid JSON", str(ctx.exception))

    def test_missing_keys_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, CONFIG_FILENAME).write_text('{"version": 2}')
            with self.assertRaises(ConfigError) as ctx:
                load_config(Path(tmpdir))
            self.assertIn("missing required keys", str(ctx.exception))


class TestConfig(unittest.TestCase):
    def setUp(self):
        self.config = load_config()

    def test_get_gpu_runner_labels(self):
        labels = self.config.get_gpu_runner_labels()
        self.assertIn("gfx94x", labels)
        self.assertIn("linux", labels["gfx94x"])

    def test_gfx94x_has_runner_labels(self):
        labels = self.config.get_gpu_runner_labels()
        gfx94x_linux = labels["gfx94x"]["linux"]
        self.assertIn("test-runs-on", gfx94x_linux)
        self.assertIn("test-runs-on-labels", gfx94x_linux)
        self.assertIn("benchmark-runs-on", gfx94x_linux)


class TestConvenienceFunctions(unittest.TestCase):
    def test_config_exists_true(self):
        self.assertTrue(config_exists())

    def test_config_exists_false(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self.assertFalse(config_exists(Path(tmpdir)))

    def test_load_runner_config(self):
        config = load_runner_config()
        self.assertIsInstance(config, dict)
        self.assertIn("version", config)

    def test_get_config_version(self):
        config = load_runner_config()
        self.assertEqual(get_config_version(config), 2)

    def test_get_build_runners(self):
        config = load_runner_config()
        runners = get_build_runners(config)
        self.assertIn("linux", runners)
        self.assertIn("default", runners["linux"])

    def test_get_gpu_runner_labels(self):
        config = load_runner_config()
        labels = get_gpu_runner_labels(config)
        self.assertIn("gfx94x", labels)
        self.assertIn("linux", labels["gfx94x"])
        self.assertIn("test-runs-on", labels["gfx94x"]["linux"])

    def test_get_runner_labels_deprecated(self):
        """Verify deprecated get_runner_labels returns same as get_gpu_runner_labels."""
        config = load_runner_config()
        self.assertEqual(get_runner_labels(config), get_gpu_runner_labels(config))


class TestSchemaValidation(unittest.TestCase):
    def test_build_runners_structure(self):
        config = load_config()
        for platform, variants in config.build_runners.items():
            self.assertIsInstance(variants, dict)
            for variant, labels in variants.items():
                self.assertIsInstance(labels, list)
                for label_config in labels:
                    self.assertIn("label", label_config)
                    self.assertIn("weight", label_config)

    def test_build_runner_weights_sum_to_one(self):
        config = load_config()
        for platform, variants in config.build_runners.items():
            for variant, labels in variants.items():
                total_weight = sum(label["weight"] for label in labels)
                self.assertAlmostEqual(
                    total_weight,
                    1.0,
                    places=2,
                    msg=f"{platform}/{variant} build runner weights sum to {total_weight}, expected 1.0",
                )

    def test_gpu_runner_labels_structure(self):
        config = load_config()
        for family_name, platforms in config.gpu_runner_labels.items():
            self.assertIsInstance(platforms, dict)
            for platform, settings in platforms.items():
                self.assertIn(platform, ["linux", "windows", "wsl"])
                # At minimum, test-runs-on should be present
                self.assertIn("test-runs-on", settings)

    def test_test_runs_on_labels_weights_sum_to_one(self):
        """Verify that test-runs-on-labels weights sum to 1.0 for load balancing."""
        config = load_config()
        for family_name, platforms in config.gpu_runner_labels.items():
            for platform, settings in platforms.items():
                if "test-runs-on-labels" in settings:
                    labels = settings["test-runs-on-labels"]
                    total_weight = sum(label["weight"] for label in labels)
                    self.assertAlmostEqual(
                        total_weight,
                        1.0,
                        places=2,
                        msg=f"{family_name}/{platform} test-runs-on-labels weights sum to {total_weight}, expected 1.0",
                    )
                if "test-runs-on-multi-gpu-labels" in settings:
                    labels = settings["test-runs-on-multi-gpu-labels"]
                    total_weight = sum(label["weight"] for label in labels)
                    self.assertAlmostEqual(
                        total_weight,
                        1.0,
                        places=2,
                        msg=f"{family_name}/{platform} test-runs-on-multi-gpu-labels weights sum to {total_weight}, expected 1.0",
                    )


if __name__ == "__main__":
    unittest.main()
