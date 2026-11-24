#!/usr/bin/env python3
# Copyright Advanced Micro Devices, Inc.
# SPDX-License-Identifier: MIT

"""Command line interface for resolving runner labels from the CI config.

Consumers that are not already Python scripts (plain `run:` steps, standalone
workflows) can resolve a label without importing ci_config_api:

    python ci-config/ci_config_cli.py build-runner --platform=linux --pool=small

GitHub evaluates `runs-on` before a runner is allocated, so a workflow cannot
resolve its own label. Invoke this in a prior job and feed the output forward:

    jobs:
      resolve:
        runs-on: ubuntu-26.04
        outputs:
          runner: ${{ steps.pick.outputs.label }}
        steps:
          - uses: actions/checkout@v4
            with:
              repository: ROCm/therock-ci-config
              path: ci-config
            continue-on-error: true
          - id: pick
            run: |
              python ci-config/ci_config_cli.py build-runner \
                --platform=linux --pool=small \
                --output=github --fallback=ubuntu-26.04
      build:
        needs: resolve
        runs-on: ${{ needs.resolve.outputs.runner }}

Exit codes:
    0  label resolved (or --fallback used for a missing config)
    1  config present but malformed, or the requested pool does not exist
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import random
import sys
from pathlib import Path
from typing import Any

from ci_config_api import CONFIG_FILENAME, ConfigError, config_exists, load_config

# "large" is the caller-facing name for the unqualified pool.
POOL_ALIASES = {"large": "default"}
BUILD_POOLS = ("default", "large", "small", "medium", "bump", "sanitizer")


def _load_quietly(config_path: Path | None):
    """Load the config with its progress logs on stderr.

    load_config() prints to stdout, which would corrupt `--output=plain` for
    callers doing `LABEL=$(... build-runner ...)`. Other consumers rely on those
    logs, so redirect here rather than changing the API.
    """
    with contextlib.redirect_stdout(sys.stderr):
        return load_config(config_path)


def select_weighted_label(
    labels: list[dict[str, Any]], rng: random.Random, context: str
) -> str:
    """Pick one label from a weighted pool.

    Mirrors TheRock's select_weighted_label: 'count' wins over 'weight', solo
    entries are returned as-is, and weights are relative rather than normalized.
    """
    if not labels:
        raise ConfigError(f"{context}: pool is empty")
    if len(labels) == 1:
        return labels[0]["label"]

    weight_key = "count" if "count" in labels[0] else "weight"
    try:
        weights = [entry[weight_key] for entry in labels]
    except KeyError as e:
        raise ConfigError(f"{context}: entry missing {e} field") from e

    if sum(weights) <= 0:
        # Zero-weight entries are how a pool is drained; all-zero is a mistake
        # that would otherwise surface as an opaque ValueError from choices().
        raise ConfigError(f"{context}: all entries have zero {weight_key}")

    return rng.choices(labels, weights=weights, k=1)[0]["label"]


def resolve_build_pool(
    platform_pools: dict[str, Any],
    pool: str,
    variant: str,
    triggers: set[str],
) -> str:
    """Resolve which build pool to draw from.

    Precedence matches TheRock's select_build_runner so the two cannot drift:
    sanitizer variants and bump PRs override the requested pool, and a platform
    without the requested pool falls back to 'default'.
    """
    if "san" in variant and "sanitizer" in platform_pools:
        return "sanitizer"
    if "submodule_bump" in triggers and "bump" in platform_pools:
        return "bump"
    resolved = POOL_ALIASES.get(pool, pool)
    return resolved if resolved in platform_pools else "default"


def emit(value: str, output: str, name: str) -> None:
    """Write the resolved label in the requested format."""
    if output == "plain":
        print(value)
        return
    if output == "json":
        print(json.dumps({name: value}))
        return

    # output == "github"
    if "\n" in value or "\n" in name:
        raise ConfigError(f"Refusing to write multi-line GitHub output: {name}")
    github_output = os.environ.get("GITHUB_OUTPUT")
    if not github_output:
        raise ConfigError("--output=github requires GITHUB_OUTPUT to be set")
    with open(github_output, "a") as f:
        f.write(f"{name}={value}\n")
    print(f"{name}={value}", file=sys.stderr)


def cmd_build_runner(args: argparse.Namespace, rng: random.Random) -> str:
    config = _load_quietly(args.config_path)
    platform_pools = config.build_runners.get(args.platform)
    if not platform_pools:
        raise ConfigError(
            f"No build runners for platform '{args.platform}'. "
            f"Known: {sorted(config.build_runners)}"
        )

    triggers = set(args.trigger or [])
    pool = resolve_build_pool(platform_pools, args.pool, args.variant, triggers)
    context = f"build-runner ({args.platform}, {pool})"
    print(f"[therock-ci-config] {context}", file=sys.stderr)
    return select_weighted_label(platform_pools[pool], rng, context)


def cmd_gpu_runner(args: argparse.Namespace, rng: random.Random) -> str:
    config = _load_quietly(args.config_path)
    family = config.gpu_runner_labels.get(args.family)
    if not family:
        raise ConfigError(
            f"No GPU runners for family '{args.family}'. "
            f"Known: {sorted(config.gpu_runner_labels)}"
        )
    platform_entry = family.get(args.platform)
    if not platform_entry:
        raise ConfigError(
            f"Family '{args.family}' has no '{args.platform}' entry. "
            f"Known: {sorted(family)}"
        )

    context = f"gpu-runner ({args.family}, {args.platform}, {args.key})"
    # Prefer the weighted list so load balancing is honored; the bare key is the
    # unweighted default kept for callers that want a stable label.
    weighted = platform_entry.get(f"{args.key}-labels")
    if weighted:
        print(f"[therock-ci-config] {context}", file=sys.stderr)
        return select_weighted_label(weighted, rng, context)
    label = platform_entry.get(args.key)
    if not label:
        raise ConfigError(
            f"{context}: not configured. "
            f"Known keys: {sorted(k for k in platform_entry if not k.endswith('-labels'))}"
        )
    return label


def build_parser() -> argparse.ArgumentParser:
    # Shared options live on the subcommands so they can be written in natural
    # order (`build-runner --platform=linux --seed=1`) rather than having to
    # precede the subcommand.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--config-path",
        type=Path,
        default=None,
        help=f"Directory containing {CONFIG_FILENAME}. "
        "Defaults to this script's directory.",
    )
    common.add_argument(
        "--output",
        choices=("plain", "github", "json"),
        default="plain",
        help="plain prints the label, github appends to $GITHUB_OUTPUT (default: %(default)s).",
    )
    common.add_argument(
        "--name",
        default="label",
        help="Output key for --output=github/json (default: %(default)s).",
    )
    common.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Seed the weighted pick for reproducible selection. "
        "Without it, selection is random per invocation.",
    )
    common.add_argument(
        "--fallback",
        default=None,
        help="Label to emit when the config is absent, for forks where the "
        "checkout is skipped. A malformed config still fails.",
    )

    parser = argparse.ArgumentParser(
        prog="ci_config_cli.py",
        description="Resolve CI runner labels from runner-config-v2.json.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser(
        "build-runner", parents=[common], help="Resolve a build runner label."
    )
    build.add_argument("--platform", required=True, help="linux or windows.")
    build.add_argument(
        "--pool",
        default="default",
        choices=BUILD_POOLS,
        help="Runner pool; falls back to 'default' if the platform lacks it "
        "(default: %(default)s).",
    )
    build.add_argument(
        "--variant",
        default="",
        help="Build variant, e.g. release or asan. Variants containing 'san' "
        "use the sanitizer pool.",
    )
    build.add_argument(
        "--trigger",
        action="append",
        help="Active CI trigger, repeatable. 'submodule_bump' uses the bump pool.",
    )
    build.set_defaults(func=cmd_build_runner)

    gpu = sub.add_parser(
        "gpu-runner", parents=[common], help="Resolve a GPU test runner label."
    )
    gpu.add_argument("--family", required=True, help="GPU family, e.g. gfx94x.")
    gpu.add_argument("--platform", required=True, help="linux or windows.")
    gpu.add_argument(
        "--key",
        default="test-runs-on",
        help="Runner key, e.g. test-runs-on or test-runs-on-multi-gpu "
        "(default: %(default)s).",
    )
    gpu.set_defaults(func=cmd_gpu_runner)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    rng = random.Random(args.seed) if args.seed is not None else random.SystemRandom()

    if args.fallback is not None and not config_exists(args.config_path):
        # Missing config is expected on forks, where the checkout is skipped.
        print(
            f"[therock-ci-config] No {CONFIG_FILENAME} found, using fallback: {args.fallback}",
            file=sys.stderr,
        )
        emit(args.fallback, args.output, args.name)
        return 0

    try:
        label = args.func(args, rng)
        emit(label, args.output, args.name)
    except ConfigError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
