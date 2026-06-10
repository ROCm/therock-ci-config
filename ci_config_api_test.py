#!/usr/bin/env python3
# Copyright Advanced Micro Devices, Inc.
# SPDX-License-Identifier: MIT

"""Tests for ci_config_api.py."""

import json
import tempfile
import unittest
from pathlib import Path

from ci_config_api import (
    LATEST_VERSION,
    SUPPORTED_VERSIONS,
    ConfigError,
    ConfigV1,
    config_exists,
    get_build_runners,
    get_config_version,
    get_gpu_families,
    load_config_v1,
    load_runner_config,
)


class TestLoadConfigV1(unittest.TestCase):
    def test_loads_real_config(self):
        config = load_config_v1()
        self.assertIsInstance(config, ConfigV1)
        self.assertIn("linux", config.build_runners)
        self.assertIn("presubmit", config.gpu_families)

    def test_missing_file_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(ConfigError) as ctx:
                load_config_v1(Path(tmpdir))
            self.assertIn("not found", str(ctx.exception))

    def test_invalid_json_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "runner-config.json").write_text("{invalid")
            with self.assertRaises(ConfigError) as ctx:
                load_config_v1(Path(tmpdir))
            self.assertIn("Invalid JSON", str(ctx.exception))

    def test_unsupported_version_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "runner-config.json").write_text(
                '{"version": "99", "build_runners": {}, "gpu_families": {}}'
            )
            with self.assertRaises(ConfigError) as ctx:
                load_config_v1(Path(tmpdir))
            self.assertIn("not supported", str(ctx.exception))

    def test_missing_keys_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "runner-config.json").write_text('{"version": "1"}')
            with self.assertRaises(ConfigError) as ctx:
                load_config_v1(Path(tmpdir))
            self.assertIn("missing required keys", str(ctx.exception))


class TestConfigV1(unittest.TestCase):
    def setUp(self):
        self.config = load_config_v1()

    def test_get_gpu_families_presubmit(self):
        families = self.config.get_gpu_families(["presubmit"])
        self.assertIn("gfx94x", families)
        self.assertIn("linux", families["gfx94x"])

    def test_get_gpu_families_multiple(self):
        families = self.config.get_gpu_families(["presubmit", "postsubmit"])
        self.assertIn("gfx94x", families)
        self.assertIn("gfx950", families)

    def test_get_gpu_families_empty(self):
        families = self.config.get_gpu_families([])
        self.assertEqual(families, {})

    def test_get_gpu_families_unknown_type(self):
        families = self.config.get_gpu_families(["unknown"])
        self.assertEqual(families, {})


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
        self.assertEqual(get_config_version(config), "1")

    def test_get_build_runners(self):
        config = load_runner_config()
        runners = get_build_runners(config)
        self.assertIn("linux", runners)
        self.assertIn("default", runners["linux"])

    def test_get_gpu_families(self):
        config = load_runner_config()
        families = get_gpu_families(config, ["presubmit"])
        self.assertIn("gfx94x", families)


class TestVersioning(unittest.TestCase):
    def test_latest_version_in_supported(self):
        self.assertIn(LATEST_VERSION, SUPPORTED_VERSIONS)

    def test_real_config_version_supported(self):
        config = load_runner_config()
        self.assertIn(config["version"], SUPPORTED_VERSIONS)

    def test_v1_loads_v1_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_data = {
                "version": "1",
                "build_runners": {"linux": {"default": []}},
                "gpu_families": {"presubmit": {"gfx94x": {"linux": {"family": "test"}}}},
            }
            Path(tmpdir, "runner-config.json").write_text(json.dumps(config_data))
            config = load_config_v1(Path(tmpdir))
            self.assertEqual(config.build_runners, {"linux": {"default": []}})


class TestSchemaValidation(unittest.TestCase):
    def test_build_runners_structure(self):
        config = load_config_v1()
        for platform, variants in config.build_runners.items():
            self.assertIsInstance(variants, dict)
            for variant, labels in variants.items():
                self.assertIsInstance(labels, list)
                for label_config in labels:
                    self.assertIn("label", label_config)
                    self.assertIn("weight", label_config)

    def test_gpu_families_structure(self):
        config = load_config_v1()
        for trigger_type, families in config.gpu_families.items():
            self.assertIn(trigger_type, ["presubmit", "postsubmit", "nightly"])
            for family_name, platforms in families.items():
                self.assertIsInstance(platforms, dict)
                for platform, settings in platforms.items():
                    self.assertIn("family", settings)
                    self.assertIn("fetch-gfx-targets", settings)


if __name__ == "__main__":
    unittest.main()
