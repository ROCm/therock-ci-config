#!/usr/bin/env python3
# Copyright Advanced Micro Devices, Inc.
# SPDX-License-Identifier: MIT

"""Tests for ci_config_cli.py."""

import io
import json
import os
import random
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from ci_config_api import CONFIG_FILENAME, ConfigError
from ci_config_cli import main, resolve_build_pool, select_weighted_label

# Minimal config exercising every pool precedence rule. Windows deliberately
# has only "default", mirroring the real config.
FIXTURE = {
    "version": 2,
    "build_runners": {
        "linux": {
            "default": [{"label": "linux-default", "weight": 1.0}],
            "small": [{"label": "linux-small", "weight": 1.0}],
            "bump": [{"label": "linux-bump", "weight": 1.0}],
            "sanitizer": [{"label": "linux-sanitizer", "weight": 1.0}],
        },
        "windows": {"default": [{"label": "windows-default", "weight": 1.0}]},
    },
    "gpu_runner_labels": {
        "gfx94x": {
            "linux": {
                "test-runs-on": "gfx94x-unweighted",
                "test-runs-on-labels": [{"label": "gfx94x-weighted", "weight": 1.0}],
                "test-runs-on-multi-gpu": "gfx94x-8gpu",
            }
        }
    },
}


class CliTestCase(unittest.TestCase):
    """Runs the CLI against a temporary config and captures stdout."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.config_dir = Path(self._tmp.name)
        self.write_config(FIXTURE)

    def write_config(self, payload):
        path = self.config_dir / CONFIG_FILENAME
        path.write_text(payload if isinstance(payload, str) else json.dumps(payload))

    def run_cli(self, *args, expect_code=0):
        """Invoke main() with --config-path injected; returns stripped stdout."""
        stdout, stderr = io.StringIO(), io.StringIO()
        argv = [args[0], f"--config-path={self.config_dir}", *args[1:]]
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(argv)
        self.assertEqual(
            code, expect_code, f"stdout={stdout.getvalue()} stderr={stderr.getvalue()}"
        )
        return stdout.getvalue().strip()


class TestBuildRunner(CliTestCase):
    def test_resolves_requested_pool(self):
        self.assertEqual(
            self.run_cli("build-runner", "--platform=linux", "--pool=small"),
            "linux-small",
        )

    def test_large_is_an_alias_for_default(self):
        self.assertEqual(
            self.run_cli("build-runner", "--platform=linux", "--pool=large"),
            "linux-default",
        )

    def test_missing_pool_falls_back_to_default(self):
        # Windows has no "small" pool, matching the real config.
        self.assertEqual(
            self.run_cli("build-runner", "--platform=windows", "--pool=small"),
            "windows-default",
        )

    def test_sanitizer_variant_overrides_pool(self):
        self.assertEqual(
            self.run_cli(
                "build-runner", "--platform=linux", "--pool=small", "--variant=asan"
            ),
            "linux-sanitizer",
        )

    def test_bump_trigger_overrides_pool(self):
        self.assertEqual(
            self.run_cli(
                "build-runner",
                "--platform=linux",
                "--pool=small",
                "--trigger=submodule_bump",
            ),
            "linux-bump",
        )

    def test_sanitizer_wins_over_bump(self):
        self.assertEqual(
            self.run_cli(
                "build-runner",
                "--platform=linux",
                "--variant=asan",
                "--trigger=submodule_bump",
            ),
            "linux-sanitizer",
        )

    def test_unknown_platform_fails(self):
        self.run_cli("build-runner", "--platform=solaris", expect_code=1)

    def test_stdout_carries_only_the_label(self):
        """Callers do LABEL=$(...), so config logs must not reach stdout."""
        out = self.run_cli("build-runner", "--platform=linux")
        self.assertEqual(out, "linux-default")
        self.assertNotIn("therock-ci-config", out)


class TestDeterminism(CliTestCase):
    def setUp(self):
        super().setUp()
        self.write_config(
            {
                **FIXTURE,
                "build_runners": {
                    "linux": {
                        "default": [
                            {"label": "a", "weight": 0.5},
                            {"label": "b", "weight": 0.5},
                        ]
                    }
                },
            }
        )

    def test_same_seed_gives_same_label(self):
        picks = {
            self.run_cli("build-runner", "--platform=linux", "--seed=7")
            for _ in range(5)
        }
        self.assertEqual(len(picks), 1)

    def test_selection_stays_within_the_pool(self):
        picks = {self.run_cli("build-runner", "--platform=linux") for _ in range(20)}
        self.assertTrue(picks <= {"a", "b"})


class TestOutputModes(CliTestCase):
    def test_github_output_appends_key_value(self):
        github_output = self.config_dir / "gh_out"
        github_output.touch()
        os.environ["GITHUB_OUTPUT"] = str(github_output)
        self.addCleanup(os.environ.pop, "GITHUB_OUTPUT", None)
        self.run_cli(
            "build-runner", "--platform=linux", "--output=github", "--name=runner"
        )
        self.assertEqual(github_output.read_text(), "runner=linux-default\n")

    def test_github_output_requires_the_env_var(self):
        os.environ.pop("GITHUB_OUTPUT", None)
        self.run_cli(
            "build-runner", "--platform=linux", "--output=github", expect_code=1
        )

    def test_json_output(self):
        out = self.run_cli(
            "build-runner", "--platform=linux", "--output=json", "--name=runner"
        )
        self.assertEqual(json.loads(out), {"runner": "linux-default"})


class TestFallback(CliTestCase):
    def test_missing_config_uses_fallback(self):
        (self.config_dir / CONFIG_FILENAME).unlink()
        self.assertEqual(
            self.run_cli("build-runner", "--platform=linux", "--fallback=ubuntu-26.04"),
            "ubuntu-26.04",
        )

    def test_missing_config_without_fallback_fails(self):
        (self.config_dir / CONFIG_FILENAME).unlink()
        self.run_cli("build-runner", "--platform=linux", expect_code=1)

    def test_malformed_config_fails_even_with_fallback(self):
        """A present-but-broken config is a bug, not a fork; fail loudly."""
        self.write_config("{not json")
        self.run_cli(
            "build-runner",
            "--platform=linux",
            "--fallback=ubuntu-26.04",
            expect_code=1,
        )


class TestGpuRunner(CliTestCase):
    def test_prefers_the_weighted_list(self):
        self.assertEqual(
            self.run_cli("gpu-runner", "--family=gfx94x", "--platform=linux"),
            "gfx94x-weighted",
        )

    def test_falls_back_to_the_bare_key(self):
        self.assertEqual(
            self.run_cli(
                "gpu-runner",
                "--family=gfx94x",
                "--platform=linux",
                "--key=test-runs-on-multi-gpu",
            ),
            "gfx94x-8gpu",
        )

    def test_unknown_family_fails(self):
        self.run_cli("gpu-runner", "--family=gfx999", "--platform=linux", expect_code=1)

    def test_unknown_platform_for_family_fails(self):
        self.run_cli(
            "gpu-runner", "--family=gfx94x", "--platform=windows", expect_code=1
        )


class TestSelectionHelpers(unittest.TestCase):
    def test_count_takes_precedence_over_weight(self):
        labels = [
            {"label": "a", "count": 0, "weight": 1},
            {"label": "b", "count": 5, "weight": 0},
        ]
        picks = {
            select_weighted_label(labels, random.Random(seed), "t")
            for seed in range(10)
        }
        self.assertEqual(picks, {"b"})

    def test_solo_entry_ignores_weight(self):
        labels = [{"label": "only", "weight": 0.0}]
        self.assertEqual(select_weighted_label(labels, random.Random(1), "t"), "only")

    def test_all_zero_weights_is_an_error(self):
        labels = [{"label": "a", "weight": 0}, {"label": "b", "weight": 0}]
        with self.assertRaises(ConfigError):
            select_weighted_label(labels, random.Random(1), "t")

    def test_pool_precedence(self):
        pools = {"default": [], "small": [], "bump": [], "sanitizer": []}
        self.assertEqual(resolve_build_pool(pools, "small", "asan", set()), "sanitizer")
        self.assertEqual(
            resolve_build_pool(pools, "small", "", {"submodule_bump"}), "bump"
        )
        self.assertEqual(resolve_build_pool(pools, "small", "", set()), "small")
        self.assertEqual(resolve_build_pool(pools, "large", "", set()), "default")
        self.assertEqual(
            resolve_build_pool({"default": []}, "small", "", set()), "default"
        )


if __name__ == "__main__":
    unittest.main()
