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

from ci_config_api import load_config_v1

config = load_config_v1()
runners = config.build_runners
families = config.get_gpu_families(["presubmit"])
```

## Version Compatibility

The API provides forward and backward compatibility between workflow versions:

```
runner-config.json  ← Single file, always latest schema
ci_config_api.py    ← Versioned loaders: load_config_v1(), load_config_v2(), ...
```

**How it works:**

| JSON Version | load_config_v1() | load_config_v2() |
|--------------|------------------|------------------|
| v1 (current) | Direct load      | N/A yet          |
| v2 (future)  | Adapts to v1     | Direct load      |
| v3 (future)  | Adapts to v1     | Adapts to v2     |

- Old workflows keep calling `load_config_v1()` and continue working
- New workflows call `load_config_v2()` when ready
- Each loader guarantees a stable interface regardless of JSON version

**Adding a new version:**

1. Update `runner-config.json` with new schema (e.g., `"version": "2"`)
2. Add `ConfigV2` dataclass and `load_config_v2()` function
3. Update `_adapt_to_v1()` to transform v2 data to v1 interface
4. Add `"2"` to `SUPPORTED_VERSIONS`
5. Migrate workflows incrementally from v1 to v2

## API Reference

### Versioned API (Recommended)

```python
from ci_config_api import load_config_v1, ConfigV1, ConfigError

config: ConfigV1 = load_config_v1()
runners = config.build_runners
families = config.get_gpu_families(["presubmit", "postsubmit"])
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
- **`gpu_families`**: Per-family test runner mappings organized by trigger type:
  - `presubmit`: Runs on pull requests
  - `postsubmit`: Runs on pushes to main
  - `nightly`: Runs on scheduled triggers

### Schema

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
