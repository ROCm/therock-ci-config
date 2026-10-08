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

Then load with the API:

```python
import sys
sys.path.insert(0, "ci-config")

from ci_config_api import load_config

config = load_config()
runners = config.build_runners
labels = config.get_gpu_runner_labels()
```

## API Reference

```python
from ci_config_api import load_config, Config, ConfigError

config: Config = load_config()
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
    get_gpu_runner_labels,
    log_config_version,
)

if config_exists(Path("ci-config")):
    config = load_runner_config(Path("ci-config"))
    log_config_version(config, Path("ci-config"))
    runners = get_build_runners(config)
```

## Configuration Files

### `runner-config-v2.json`

Contains GPU runner labels and build runner configurations:

- **`version`**: Schema version for API compatibility
- **`build_runners`**: Build runner labels with weighted distribution (Azure/AWS)
- **`gpu_runner_labels`**: Runner configuration organized by GPU family name

### Schema

**`build_runners`**:

| Field | Description |
|-------|-------------|
| `linux.default` | Weighted runner list for standard Linux builds |
| `linux.sanitizer` | Weighted runner list for sanitizer builds (asan, tsan) |
| `windows.default` | Weighted runner list for Windows builds |

**`gpu_runner_labels`**:

Each GPU family has one entry per platform: `linux`, `windows`, and optionally `wsl`. A `wsl` entry
holds the runner label for WSL-hosted GPU runners (a Windows host whose GitHub runner runs inside
WSL2). TheRock runs the Linux test matrix on it as separate opt-in `<job> (WSL)` jobs.

| Field | Description |
|-------|-------------|
| `test-runs-on` | GitHub runner label for tests |
| `test-runs-on-labels` | Weighted runner list for load balancing |
| `test-runs-on-sandbox` | Sandbox runner label |
| `test-runs-on-multi-gpu` | Runner label for multi-GPU tests |
| `benchmark-runs-on` | Runner label for benchmarks |

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
cat runner-config-v2.json
```
