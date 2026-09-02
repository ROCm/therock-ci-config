#!/usr/bin/env python3
# Copyright Advanced Micro Devices, Inc.
# SPDX-License-Identifier: MIT

"""Tests for ci_config_api.py."""

import json
import tempfile
import unittest
from pathlib import Path

from ci_config_api import (
    CONFIG_FILENAMES,
    LATEST_VERSION,
    SUPPORTED_VERSIONS,
    ConfigError,
    ConfigV1,
    ConfigV2,
    config_exists,
    get_build_runners,
    get_config_version,
    get_gpu_families,
    get_gpu_runner_labels,
    get_runner_labels,
    load_config_v1,
    load_config_v2,
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

    def test_v1_file_not_found_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create v2 config but not v1
            Path(tmpdir, "runner-config-v2.json").write_text(
                '{"version": "2", "build_runners": {}, "gpu_runner_labels": {}}'
            )
            with self.assertRaises(ConfigError) as ctx:
                load_config_v1(Path(tmpdir))
            self.assertIn("not found", str(ctx.exception))

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

    def test_gfx125x_is_presubmit_build_only(self):
        families = self.config.get_gpu_families(["presubmit"])
        self.assertEqual(
            families["gfx125x"]["linux"],
            {
                "test-runs-on": "",
                "family": "gfx125X-dcgpu",
                "fetch-gfx-targets": [],
                "build_variants": ["release"],
            },
        )

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

    def test_get_gpu_runner_labels(self):
        labels = self.config.get_gpu_runner_labels()
        self.assertIn("gfx94x", labels)
        self.assertIn("linux", labels["gfx94x"])


class TestLoadConfigV2(unittest.TestCase):
    def test_loads_real_config(self):
        config = load_config_v2()
        self.assertIsInstance(config, ConfigV2)
        self.assertIn("linux", config.build_runners)
        self.assertIn("gfx94x", config.gpu_runner_labels)

    def test_missing_file_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(ConfigError) as ctx:
                load_config_v2(Path(tmpdir))
            self.assertIn("not found", str(ctx.exception))

    def test_invalid_json_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "runner-config-v2.json").write_text("{invalid")
            with self.assertRaises(ConfigError) as ctx:
                load_config_v2(Path(tmpdir))
            self.assertIn("Invalid JSON", str(ctx.exception))

    def test_missing_keys_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "runner-config-v2.json").write_text('{"version": "2"}')
            with self.assertRaises(ConfigError) as ctx:
                load_config_v2(Path(tmpdir))
            self.assertIn("missing required keys", str(ctx.exception))


class TestConfigV2(unittest.TestCase):
    def setUp(self):
        self.config = load_config_v2()

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
            self.assertFalse(config_exists(Path(tmpdir), version="1"))
            self.assertFalse(config_exists(Path(tmpdir), version="2"))

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


class TestVersioning(unittest.TestCase):
    def test_latest_version_in_supported(self):
        self.assertIn(LATEST_VERSION, SUPPORTED_VERSIONS)

    def test_real_config_version_supported(self):
        config = load_runner_config(version="1")
        self.assertIn(config["version"], SUPPORTED_VERSIONS)
        config = load_runner_config(version="2")
        self.assertIn(config["version"], SUPPORTED_VERSIONS)

    def test_v1_loads_v1_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_data = {
                "version": "1",
                "build_runners": {"linux": {"default": []}},
                "gpu_families": {
                    "presubmit": {"gfx94x": {"linux": {"family": "test"}}}
                },
                "gpu_runner_labels": {"gfx94x": {"linux": {"test-runs-on": "test"}}},
            }
            Path(tmpdir, "runner-config.json").write_text(json.dumps(config_data))
            config = load_config_v1(Path(tmpdir))
            self.assertEqual(config.build_runners, {"linux": {"default": []}})

    def test_v2_loads_v2_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_data = {
                "version": "2",
                "build_runners": {"linux": {"default": []}},
                "gpu_runner_labels": {"gfx94x": {"linux": {"test-runs-on": "test"}}},
            }
            Path(tmpdir, "runner-config-v2.json").write_text(json.dumps(config_data))
            config = load_config_v2(Path(tmpdir))
            self.assertEqual(config.build_runners, {"linux": {"default": []}})

    def test_each_version_has_config_file(self):
        for version in SUPPORTED_VERSIONS:
            self.assertIn(version, CONFIG_FILENAMES)
            self.assertTrue(config_exists(version=version))


class TestSchemaValidationV1(unittest.TestCase):
    def test_build_runners_structure(self):
        config = load_config_v1()
        for platform, variants in config.build_runners.items():
            self.assertIsInstance(variants, dict)
            for variant, labels in variants.items():
                self.assertIsInstance(labels, list)
                for label_config in labels:
                    self.assertIn("label", label_config)
                    self.assertIn("weight", label_config)

    def test_build_runner_weights_sum_to_one(self):
        config = load_config_v1()
        for platform, variants in config.build_runners.items():
            for variant, labels in variants.items():
                total_weight = sum(label["weight"] for label in labels)
                self.assertAlmostEqual(
                    total_weight,
                    1.0,
                    places=2,
                    msg=f"{platform}/{variant} build runner weights sum to {total_weight}, expected 1.0",
                )

    def test_gpu_families_structure(self):
        config = load_config_v1()
        for trigger_type, families in config.gpu_families.items():
            self.assertIn(trigger_type, ["presubmit", "postsubmit", "nightly"])
            for family_name, platforms in families.items():
                self.assertIsInstance(platforms, dict)
                for platform, settings in platforms.items():
                    self.assertIn("family", settings)
                    self.assertIn("fetch-gfx-targets", settings)

    def test_test_runs_on_labels_weights_sum_to_one(self):
        """Verify that test-runs-on-labels weights sum to 1.0 for load balancing."""
        config = load_config_v1()
        for trigger_type, families in config.gpu_families.items():
            for family_name, platforms in families.items():
                for platform, settings in platforms.items():
                    if "test-runs-on-labels" in settings:
                        labels = settings["test-runs-on-labels"]
                        total_weight = sum(label["weight"] for label in labels)
                        self.assertAlmostEqual(
                            total_weight,
                            1.0,
                            places=2,
                            msg=f"{trigger_type}/{family_name}/{platform} test-runs-on-labels weights sum to {total_weight}, expected 1.0",
                        )
                    if "test-runs-on-multi-gpu-labels" in settings:
                        labels = settings["test-runs-on-multi-gpu-labels"]
                        total_weight = sum(label["weight"] for label in labels)
                        self.assertAlmostEqual(
                            total_weight,
                            1.0,
                            places=2,
                            msg=f"{trigger_type}/{family_name}/{platform} test-runs-on-multi-gpu-labels weights sum to {total_weight}, expected 1.0",
                        )


class TestSchemaValidationV2(unittest.TestCase):
    def test_build_runners_structure(self):
        config = load_config_v2()
        for platform, variants in config.build_runners.items():
            self.assertIsInstance(variants, dict)
            for variant, labels in variants.items():
                self.assertIsInstance(labels, list)
                for label_config in labels:
                    self.assertIn("label", label_config)
                    self.assertIn("weight", label_config)

    def test_build_runner_weights_sum_to_one(self):
        config = load_config_v2()
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
        config = load_config_v2()
        for family_name, platforms in config.gpu_runner_labels.items():
            self.assertIsInstance(platforms, dict)
            for platform, settings in platforms.items():
                self.assertIn(platform, ["linux", "windows"])
                # At minimum, test-runs-on should be present
                self.assertIn("test-runs-on", settings)

    def test_test_runs_on_labels_weights_sum_to_one(self):
        """Verify that test-runs-on-labels weights sum to 1.0 for load balancing."""
        config = load_config_v2()
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
