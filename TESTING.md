# Testing Changes

To test changes to this repo before merging to `main`:

1. **Create a branch here** with your changes and push it

2. **Update TheRock workflows** to point to your branch:

   In `.github/workflows/setup_multi_arch.yml` (build) and `.github/workflows/test_artifacts.yml` (test), find the "Checkout CI config" step and change `ref`:

   ```yaml
   - name: Checkout CI config
     uses: actions/checkout@v4
     with:
       repository: ROCm/therock-ci-config
       ref: your-branch-name  # change from 'main' to your branch
       path: ci-config
   ```

3. **Run workflow dispatch** in TheRock Actions

4. **Revert and merge** once verified
