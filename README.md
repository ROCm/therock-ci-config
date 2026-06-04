# TheRock CI Config

Centralized CI configuration for ROCm builds - GPU runner mappings, build runner weights, and test infrastructure settings.

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
from ci_config_loader import load_config_v1

config = load_config_v1(Path("ci-config"))
runners = config.build_runners
families = config.get_gpu_families(["presubmit"])
```

## Versioning

The config uses semantic versioning for schema compatibility:

```json
{
  "version": "1",
  "build_runners": {...},
  "gpu_families": {...}
}
```

**Version contract:**
- Consumers call `load_config_v1()` to load version 1 schema
- Version mismatch raises `ConfigError` with clear message
- Breaking schema changes bump the version number
- Old consumers continue working until they upgrade

**Adding a new version:**
1. Update `runner-config.json` with `"version": "2"`
2. Add `load_config_v2()` and `ConfigV2` in TheRock's `ci_config_loader.py`
3. Migrate consumers incrementally
4. Deprecate old version after migration complete

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

## Making Changes

1. Create a PR with your runner config changes
2. Once merged, all consuming workflows pick up changes on next run
3. To rollback, revert the commit or pin workflows to a specific SHA

## Testing Changes

Test runner changes before merging:

1. Create a branch in therock-ci-config with your changes
2. In TheRock, update `setup_multi_arch.yml` to point to your branch
3. Validate the CI run uses your new configuration
4. Once validated, merge to main

## Traceability

Every workflow run logs the config commit SHA at checkout time. To reproduce a CI run's configuration:

```bash
git checkout <sha-from-workflow-log>
cat runner-config.json
```
