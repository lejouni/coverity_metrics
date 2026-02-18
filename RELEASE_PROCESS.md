# Release Process

This document describes how to create and publish releases for the coverity-metrics package.

## Prerequisites

1. **Python Build Tools**
   ```powershell
   python -m pip install --upgrade pip build twine
   ```

2. **PyPI Account & API Token**
   - Create account at https://pypi.org
   - Generate API token at https://pypi.org/manage/account/token/
   - Store in `~/.pypirc` or provide via `-TwineUsername` and `-TwinePassword`

3. **TestPyPI Account (Optional, for testing)**
   - Create account at https://test.pypi.org
   - Generate API token
   - Useful for testing releases before publishing to main PyPI

4. **GitHub Token (Optional, for GitHub releases)**
   - Create Personal Access Token at https://github.com/settings/tokens
   - Requires `repo` scope
   - Set as `GITHUB_TOKEN` environment variable or pass via `-GitHubToken`

## Using the Release Script

The `release.ps1` PowerShell script automates the entire release process.

### Basic Release (Patch Version)

```powershell
# Bumps patch version (e.g., 1.0.0 → 1.0.1)
# Builds package, uploads to PyPI, and tests installation
./release.ps1
```

### Specify Version Type

```powershell
# Bump minor version (e.g., 1.0.0 → 1.1.0)
./release.ps1 -Part minor

# Bump major version (e.g., 1.0.0 → 2.0.0)
./release.ps1 -Part major

# Set explicit version
./release.ps1 -NewVersion 1.2.3
```

### Test on TestPyPI First

```powershell
# Upload to TestPyPI instead of PyPI
./release.ps1 -Repository testpypi

# Build and test locally without uploading
./release.ps1 -NoUpload
```

### Create GitHub Release

```powershell
# Release to PyPI and create GitHub release
./release.ps1 -NewVersion 1.1.0 -Repository pypi -CreateGitHubRelease -GitHubToken "ghp_xxx"

# Or use environment variable
$env:GITHUB_TOKEN = "ghp_xxx"
./release.ps1 -NewVersion 1.1.0 -Repository pypi -CreateGitHubRelease

# With release notes from file
./release.ps1 -NewVersion 1.1.0 -Repository pypi -CreateGitHubRelease -ReleaseNotesPath RELEASE_NOTES.md
```

### Advanced Options

```powershell
# Skip install verification test
./release.ps1 -NoInstallTest

# Dry run (see what would happen without executing)
./release.ps1 -DryRun -NewVersion 1.0.1

# Skip building (use existing dist/ artifacts)
./release.ps1 -SkipBuild

# Offline mode (no internet for dependencies)
./release.ps1 -Offline -FindLinks ./wheels

# Custom repository URL
./release.ps1 -GitHubRepo "yourusername/coverity-metrics"
```

## Complete Workflow Example

### 1. Prepare Release

```powershell
# Ensure everything is committed
git status
git add .
git commit -m "Prepare for release 1.1.0"
git push
```

### 2. Test on TestPyPI

```powershell
# Test the release process
./release.ps1 -NewVersion 1.1.0 -Repository testpypi

# Verify installation from TestPyPI
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple coverity-metrics==1.1.0

# Test CLI
coverity-dashboard --help
```

### 3. Release to PyPI

```powershell
# Publish to production PyPI
./release.ps1 -NewVersion 1.1.0 -Repository pypi
```

### 4. Create GitHub Release

```powershell
# Create GitHub release with tag
./release.ps1 -NewVersion 1.1.0 -Repository pypi -CreateGitHubRelease -GitHubToken $env:GITHUB_TOKEN -ReleaseNotesPath RELEASE_NOTES.md
```

### 5. Verify

```powershell
# Install from PyPI
pip install coverity-metrics==1.1.0

# Verify CLI commands work
coverity-dashboard --help
coverity-metrics --help
coverity-export --help
```

## What the Script Does

1. **Version Bump**: Updates version in `pyproject.toml` and `coverity_metrics/__version__.py`
2. **Clean Build**: Removes old `dist/`, `build/`, `*.egg-info`
3. **Build Package**: Creates wheel and source distribution in `dist/`
4. **Upload**: Publishes to PyPI or TestPyPI via `twine`
5. **Git Tag** (if `-CreateGitHubRelease`): Creates and pushes git tag
6. **GitHub Release** (if `-CreateGitHubRelease`): Creates GitHub release with notes
7. **Verify Install**: Creates temp venv, installs package, tests CLI

## Troubleshooting

### Upload Failed - Authentication Error

```powershell
# Use explicit credentials
./release.ps1 -TwineUsername "__token__" -TwinePassword "pypi-xxx"
```

### GitHub Release Failed

```powershell
# Ensure GitHub token has 'repo' scope
# Create new token at: https://github.com/settings/tokens

# Set correct repository
./release.ps1 -GitHubRepo "yourusername/coverity-metrics"
```

### Install Test Failed - Package Not Found

The script waits for PyPI to index the new version. If timeout occurs:
- Wait a few minutes and try installing manually
- Check https://pypi.org/project/coverity-metrics/
- Use `-NoInstallTest` to skip verification

### Build Failed - Missing Dependencies

```powershell
# Upgrade build tools
python -m pip install --upgrade pip build twine setuptools wheel
```

## Manual Release (Without Script)

If needed, you can release manually:

```powershell
# 1. Update version in pyproject.toml and __version__.py
# 2. Clean and build
Remove-Item -Recurse -Force dist, build, *.egg-info -ErrorAction SilentlyContinue
python -m build

# 3. Upload to PyPI
python -m twine upload dist/*

# 4. Tag and push
git tag -a v1.1.0 -m "Release 1.1.0"
git push origin v1.1.0
```

## Version Numbering

Follow [Semantic Versioning](https://semver.org/):

- **Major** (X.0.0): Breaking changes, incompatible API changes
- **Minor** (x.X.0): New features, backwards compatible
- **Patch** (x.x.X): Bug fixes, backwards compatible

Examples:
- `1.0.0` → `1.0.1`: Bug fix
- `1.0.0` → `1.1.0`: New feature
- `1.0.0` → `2.0.0`: Breaking change
