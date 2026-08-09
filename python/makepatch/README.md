# makepatch

Hatchling build hook that helps developers freely modify and build Python
packages through patches, like [`pnpm patch`](https://pnpm.io/cli/patch).

> [!WARN]
> This package was developed for personal use and is still unstable and poorly
> developed. Only confirmed to work with `uv`. PRs are welcome.

## Usage

> [!IMPORTANT]
> Patching installed packages is not yet supported. To patch a package, you must
> create a separate project (recommend using workspace).

To include patched packages automatically during the build, you need to add
`makepatch` to `build-system` and register the hook as follows:
```toml pyproject.toml
[build-system]
requires = ["hatchling", "makepatch"]
build-backend = "hatchling.build"

[tool.hatch.build.hooks.makepatch.options]
# Add options here
```

- To initialize the patch development environment, run the following command: <br/>
  `uv run apply-patches` <br/>
  This will create a patched source in `work/patched`.
- To create a patch file with modifications to `work/patched`, run the following
  command: <br/>
  `uv run rebuild-patches`

### Configuration

```toml pyproject.toml
[tool.hatch.build.hooks.makepatch.options]
module-source = "path of the actual package relative to `work/sources` (e.g., `src/mcp`)"
excludes = [
    # Files to exclude within `module-source`
    # DO NOT delete files from `work/patched`, you must exclude it from there
]
dev-excludes = [
    # Files to exclude when copied from `work/sources` to `work/patched`
    # does not affect build results and only for reducing copy time and storage usage.
    # will be changed to only copy `module-source` in the future.
]
```
