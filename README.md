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
    # No ref = latest main, SHA logged for traceability
```

The checkout logs the exact commit SHA used, ensuring full traceability for debugging CI issues.

## Configuration Files

### `runner-config.json`

Contains GPU family matrix and runner configurations:

- **`build_runners`**: Build runner labels with weighted distribution (Azure/AWS)
- **`gpu_families`**: Per-family test runner mappings organized by trigger type:
  - `presubmit`: Runs on pull requests
  - `postsubmit`: Runs on pushes to main
  - `nightly`: Runs on scheduled triggers

### Schema

See [runner-config.json](runner-config.json) for the full structure. Key fields per GPU family:

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

## Traceability

Every workflow run logs the config commit SHA at checkout time. To reproduce a CI run's configuration:

```bash
git checkout <sha-from-workflow-log>
cat runner-config.json
```
