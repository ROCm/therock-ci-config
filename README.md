# TheRock CI Config

Centralized CI configuration for ROCm builds - GPU runner mappings, build runner weights, and test infrastructure settings.

- **[Testing changes](TESTING.md)** - How to test config changes before merging

## Overview

This repository provides dynamic CI configuration that can be updated independently of TheRock, rocm-libraries, and rocm-systems. Changes here propagate instantly to all consuming workflows without requiring PRs in each repository.

## Usage

Workflows fetch this config at runtime:

```yaml
- uses: actions/checkout@v4
  with:
    repository: ROCm/therock-ci-config
    path: ci-config
```

Then load with the versioned API:

```python
import sys
sys.path.insert(0, "ci-config")

from ci_config_api import load_config

config = load_config(2)  # or 1 for legacy workflows
runners = config.build_runners
labels = config.get_gpu_runner_labels()
```

## Version Compatibility

The API provides forward and backward compatibility between workflow versions:

```
runner-config.json     ← V1 schema (legacy, has gpu_families)
runner-config-v2.json  ← V2 schema (current, runner labels only)
ci_config_api.py       ← Versioned loaders: load_config(1), load_config(2), ...
```

**How it works:**

| Config File            | load_config(1)   | load_config(2)   |
|------------------------|------------------|------------------|
| runner-config.json     | Direct load      | -                |
| runner-config-v2.json  | -                | Direct load      |

- V1 workflows keep calling `load_config(1)` and continue working
- New workflows should use `load_config(2)` (recommended)
- Each version has its own config file for independent updates

**Deprecation timeline:**

- V1 support will be maintained until **September 29, 2026** to allow for stale PRs, release branches, and gradual migration
- New integrations should use V2 (`load_config(2)`)
- Migrate existing workflows from V1 to V2 during this period

**Adding a new version:**

1. Create new config file (e.g., `runner-config-v3.json`)
2. Add `ConfigV3` dataclass and update `load_config()` function
3. Add `3` to `SUPPORTED_VERSIONS` and `CONFIG_FILENAMES`
4. Migrate workflows incrementally to the new version

## API Reference

### Versioned API (Recommended)

```python
from ci_config_api import load_config, ConfigV2, ConfigError

config: ConfigV2 = load_config(2)
runners = config.build_runners
labels = config.get_gpu_runner_labels()
```

### Convenience Functions

For backwards compatibility with existing code patterns:

```python
from ci_config_api import (
    config_exists,
    load_runner_config,
    get_build_runners,
    get_gpu_families,
    log_config_version,
)

if config_exists(Path("ci-config")):
    config = load_runner_config(Path("ci-config"))
    log_config_version(config, Path("ci-config"))
    runners = get_build_runners(config)
    families = get_gpu_families(config, ["presubmit"])
```

## Configuration Files

### `runner-config.json`

Contains GPU family matrix and runner configurations:

- **`version`**: Schema version for API compatibility
- **`build_runners`**: Build runner labels with weighted distribution (Azure/AWS)
- **`gpu_families`**: Full per-family configuration organized by trigger type (legacy, for backward compat)
  - `presubmit`: Runs on pull requests
  - `postsubmit`: Runs on pushes to main
  - `nightly`: Runs on scheduled triggers
- **`gpu_runner_labels`**: Runner-only configuration organized by GPU family name (preferred for new code)

### Schema

**`build_runners`**:

| Field | Description |
|-------|-------------|
| `linux.default` | Weighted runner list for standard Linux builds |
| `linux.sanitizer` | Weighted runner list for sanitizer builds (asan, tsan) |
| `windows.default` | Weighted runner list for Windows builds |

**`gpu_runner_labels`** (preferred for new code needing only runner config):

| Field | Description |
|-------|-------------|
| `test-runs-on` | GitHub runner label for tests |
| `test-runs-on-labels` | Weighted runner list for load balancing |
| `test-runs-on-sandbox` | Sandbox runner label |
| `test-runs-on-multi-gpu` | Runner label for multi-GPU tests |
| `benchmark-runs-on` | Runner label for benchmarks |

**`gpu_families`** (legacy, includes build config):

Key fields per GPU family:

| Field | Description |
|-------|-------------|
| `test-runs-on` | GitHub runner label for tests |
| `test-runs-on-labels` | Weighted runner list for load balancing |
| `test-runs-on-multi-gpu` | Runner label for multi-GPU tests |
| `family` | AMD GPU family name for artifact fetching |
| `fetch-gfx-targets` | GFX targets for split artifact fetching |
| `build_variants` | Build variants to test (release, asan, tsan) |

## Testing

Run tests locally:

```bash
python -m pytest ci_config_api_test.py -v
```

## Making Changes

1. Create a PR with your runner config changes
2. Once merged, all consuming workflows pick up changes on next run
3. To rollback, revert the commit or pin workflows to a specific SHA

## Traceability

Every workflow run logs the config commit SHA at checkout time. To reproduce a CI run's configuration:

```bash
git checkout <sha-from-workflow-log>
cat runner-config.json
```
