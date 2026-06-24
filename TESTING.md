# Testing Changes

To test changes to this repo before merging to `main`:

1. **Create a branch here** with your changes and push it

2. **Update TheRock workflows** to point to your branch:
   - [`setup_multi_arch.yml` line ~128](https://github.com/ROCm/TheRock/blob/main/.github/workflows/setup_multi_arch.yml#L128) (build)
   - [`test_artifacts.yml` line ~139](https://github.com/ROCm/TheRock/blob/main/.github/workflows/test_artifacts.yml#L139) (test)

   Change `ref: main` to `ref: your-branch-name` in the "Checkout CI config" step.

3. **Run workflow dispatch** in [TheRock Actions](https://github.com/ROCm/TheRock/actions)

4. **Revert and merge** once verified
