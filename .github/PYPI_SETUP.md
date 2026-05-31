# PyPI Trusted Publishing Setup

Follow these steps to configure automatic PyPI publishing via GitHub Actions.

## Prerequisites
- A [PyPI](https://pypi.org) account
- The project name `mcp-origin-pro` must be available on PyPI

## Step 1: Create the PyPI Project (if new)

1. Go to https://pypi.org/manage/projects/
2. Click "Create a project" (if `mcp-origin-pro` doesn't exist yet)

## Step 2: Configure Trusted Publishing

1. Go to https://pypi.org/manage/project/mcp-origin-pro/settings/publishing/
2. Scroll to "Trusted Publisher Management"
3. Click "Add a new trusted publisher"
4. Fill in:
   - **Owner**: `ZHANG-923-ZE`
   - **Repository name**: `origin-MCP`
   - **Workflow name**: `publish.yml`
   - **Environment name**: `pypi`
5. Click "Add"

## Step 3: Verify

After pushing a version tag (`v*`), the `.github/workflows/publish.yml` workflow will:
1. Build the package with `hatchling`
2. Publish to PyPI using OIDC trusted publishing (no token needed)

The first push of a `v*` tag will trigger the publish workflow automatically.

## Troubleshooting

- **"Project not found"**: Ensure the project name `mcp-origin-pro` exists on PyPI first.
- **"Trusted publisher not working"**: Verify Owner/Repo/Workflow/Environment exactly match the values above.
- **Note**: `originpro` is NOT on PyPI and is NOT a pip dependency. Users must install Origin 2025b separately.
