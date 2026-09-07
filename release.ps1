<#
.SYNOPSIS
  Bump the coverity-metrics package version, refresh release documentation, commit,
  and push a version tag that triggers the GitHub Actions release workflow.

.DESCRIPTION
  - Bumps the version in coverity_metrics/__version__.py (major/minor/patch or explicit version).
  - Refreshes release dates in CHANGELOG.md and RELEASE_NOTES.md.
  - Commits the changes and pushes the branch to the git remote.
  - Creates an annotated git tag ('v<version>' by default) and pushes it.
  - The tag push triggers .github/workflows/build-binaries.yml, which builds the
    Windows/Linux binaries, publishes the package to PyPI, and creates the GitHub Release.

.PARAMETER Part
  Which part of the version to bump: patch (default), minor, or major. Ignored if -NewVersion is supplied.

.PARAMETER NewVersion
  Explicit version string to set (e.g. 1.0.1). Overrides -Part.

.PARAMETER DryRun
  Print what would be done without executing commands.

.PARAMETER Remote
  Git remote name to push to. Default: 'origin'.

.PARAMETER Branch
  Git branch to push. Default: current branch (HEAD).

.PARAMETER CommitMessage
  Commit message for the version-bump commit. Default: 'Release v<version>'.

.PARAMETER TagPrefix
  Prefix for the git tag. Default: 'v'.

.PARAMETER SkipCommit
  Skip staging, committing, and pushing the branch (only bump files locally).

.PARAMETER SkipTag
  Skip creating and pushing the tag. The GitHub Actions release workflow will NOT be triggered.

.PARAMETER SkipPreflightCI
  Skip the pre-tag CI validation run. By default, before creating the tag the script triggers a
  workflow_dispatch of build-binaries.yml on the just-pushed commit and waits for every build job
  (Windows, ubuntu-26.04 linux, ubuntu-22.04 linux-glibc2.35) to succeed. Only then are the tag
  and PyPI publish allowed to proceed. Pass this switch to fall back to the legacy "tag and hope"
  flow.

.PARAMETER AllowDirty
  Allow running with unrelated uncommitted changes in the working tree.
  By default the script aborts if the working tree is dirty before it starts.

.EXAMPLE
  # Bump patch, commit, push branch and tag — CI publishes to PyPI and GitHub Release
  ./release.ps1 -Part patch

.EXAMPLE
  # Set an explicit version
  ./release.ps1 -NewVersion 1.1.0

.EXAMPLE
  # Preview all steps without executing anything
  ./release.ps1 -Part minor -DryRun
#>

[CmdletBinding()]
param(
  [ValidateSet('patch','minor','major')]
  [string]$Part = 'patch',

  [string]$NewVersion,

  [switch]$DryRun,

  [string]$Remote = 'origin',
  [string]$Branch,
  [string]$CommitMessage,
  [string]$TagPrefix = 'v',

  [switch]$SkipCommit,
  [switch]$SkipTag,
  [switch]$SkipPreflightCI,
  [switch]$AllowDirty
)

set-strictmode -version latest
$ErrorActionPreference = 'Stop'

function Invoke-Step {
  param(
    [Parameter(Mandatory=$true)][string]$Command,
    [string]$WorkingDir
  )
  if ($DryRun) {
    Write-Host "[DRY-RUN] $Command" -ForegroundColor Yellow
    return
  }
  if ($WorkingDir) { Push-Location $WorkingDir }
  try {
    Write-Host "[RUN] $Command" -ForegroundColor Cyan
    & $env:ComSpec /c $Command
    $exit = $LASTEXITCODE
    if ($exit -ne 0) {
      throw "Command failed with exit code $($exit): $Command"
    }
  } finally {
    if ($WorkingDir) { Pop-Location }
  }
}

function Get-ProjectVersion {
  param([string]$PyProjectPath)
  # pyproject.toml uses dynamic = ["version"]; the single source of truth is __version__.py.
  $versionPath = Join-Path (Split-Path $PyProjectPath) 'coverity_metrics/__version__.py'
  if (-not (Test-Path $versionPath)) { throw "Version file not found at $versionPath" }
  $content = Get-Content -Raw -LiteralPath $versionPath
  $m = [regex]::Match($content, '__version__\s*=\s*"(?<v>\d+\.\d+\.\d+)"')
  if (-not $m.Success) { throw "Could not find __version__ in $versionPath" }
  return $m.Groups['v'].Value
}

function Set-ProjectVersion {
  param([string]$PyProjectPath, [string]$Version)
  # pyproject.toml has dynamic = ["version"] — only __version__.py needs updating.
  $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
  $versionPath = Join-Path (Split-Path $PyProjectPath) 'coverity_metrics/__version__.py'
  if (-not (Test-Path $versionPath)) { throw "Version file not found at $versionPath" }
  $versionContent = Get-Content -Raw -LiteralPath $versionPath -Encoding UTF8
  $versionNew = $versionContent -replace '__version__\s*=\s*"\d+\.\d+\.\d+"', "__version__ = `"$Version`""
  if ($DryRun) {
    Write-Host "[DRY-RUN] Would set __version__ to $Version in $versionPath (UTF-8 no BOM)" -ForegroundColor Yellow
  } else {
    [System.IO.File]::WriteAllText($versionPath, $versionNew, $utf8NoBom)
    Write-Host "Set __version__ to $Version in $versionPath" -ForegroundColor Green
  }
}

function Update-Version {
  param([string]$Current, [string]$Part)
  $a = $Current.Split('.') | ForEach-Object {[int]$_}
  switch ($Part) {
    'major' { $a[0] += 1; $a[1] = 0; $a[2] = 0 }
    'minor' { $a[1] += 1; $a[2] = 0 }
    default { $a[2] += 1 }
  }
  return ($a -join '.')
}

function Update-ReleaseDates {
  param(
    [Parameter(Mandatory=$true)][string]$Version,
    [Parameter(Mandatory=$true)][string]$RootPath
  )
  $releaseDate = Get-Date -Format "yyyy-MM-dd"
  $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
  
  # Update CHANGELOG.md
  $changelogPath = Join-Path $RootPath 'CHANGELOG.md'
  if (Test-Path $changelogPath) {
    $changelogContent = Get-Content -Raw -LiteralPath $changelogPath -Encoding UTF8
    
    # Check if version entry already exists
    if ($changelogContent -match "## \[$Version\]") {
      # Update existing entry date
      $changelogNew = $changelogContent -replace "## \[$([regex]::Escape($Version))\] - \d{4}-\d{2}-\d{2}", "## [$Version] - $releaseDate"
      $changelogNew = $changelogNew -replace "## \[$([regex]::Escape($Version))\] - \d{4}-\d{2}-XX", "## [$Version] - $releaseDate"
      $changelogNew = $changelogNew -replace "## \[$([regex]::Escape($Version))\] - YYYY-MM-DD", "## [$Version] - $releaseDate"
      $action = "Updated existing"
    } else {
      # Create new version entry at the top
      $newEntry = @"

## [$Version] - $releaseDate

### Added
- Added ``fetch_all`` parameter to metrics methods for retrieving all data instead of just top N results
- Enhanced CLI parameter documentation in README

### Changed
- Updated Python library usage examples in README

### Fixed
- Bug fixes and improvements

"@
      # Insert after the "adheres to Semantic Versioning" line
      $changelogNew = $changelogContent -replace "(and this project adheres to \[Semantic Versioning\].*?\r?\n)", "`$1$newEntry"
      $action = "Created new"
    }
    
    if ($DryRun) {
      Write-Host "[DRY-RUN] Would $action entry in CHANGELOG.md for version $Version dated $releaseDate" -ForegroundColor Yellow
    } else {
      [System.IO.File]::WriteAllText($changelogPath, $changelogNew, $utf8NoBom)
      Write-Host "$action CHANGELOG.md entry: [$Version] - $releaseDate" -ForegroundColor Green
    }
  }
  
  # Update RELEASE_NOTES.md
  $releaseNotesPath = Join-Path $RootPath 'RELEASE_NOTES.md'
  if (Test-Path $releaseNotesPath) {
    $releaseNotesContent = Get-Content -Raw -LiteralPath $releaseNotesPath -Encoding UTF8
    
    # Check if version entry already exists
    if ($releaseNotesContent -match "### Version $Version") {
      # Update existing entry date
      $releaseNotesNew = $releaseNotesContent -replace "### Version $([regex]::Escape($Version)) - \d{4}-\d{2}-\d{2}", "### Version $Version - $releaseDate"
      $releaseNotesNew = $releaseNotesNew -replace "### Version $([regex]::Escape($Version)) - \d{4}-\d{2}-XX", "### Version $Version - $releaseDate"
      $releaseNotesNew = $releaseNotesNew -replace "### Version $([regex]::Escape($Version)) - YYYY-MM-DD", "### Version $Version - $releaseDate"
      $action = "Updated existing"
    } else {
      # Create new version entry at the top
      $newEntry = @"

### Version $Version - $releaseDate

**Release Update**

#### Features
- Added ``fetch_all`` parameter to metrics methods for complete data retrieval
- Enhanced documentation with CLI parameter reference tables

#### Improvements
- Updated README with comprehensive parameter documentation
- Improved Python library usage examples

"@
      # Insert after "## Version History" line
      $releaseNotesNew = $releaseNotesContent -replace "(## Version History\r?\n)", "`$1$newEntry"
      $action = "Created new"
    }
    
    if ($DryRun) {
      Write-Host "[DRY-RUN] Would $action entry in RELEASE_NOTES.md for version $Version dated $releaseDate" -ForegroundColor Yellow
    } else {
      [System.IO.File]::WriteAllText($releaseNotesPath, $releaseNotesNew, $utf8NoBom)
      Write-Host "$action RELEASE_NOTES.md entry: Version $Version - $releaseDate" -ForegroundColor Green
    }
  }
}

$root = Resolve-Path .
$pyproj = Join-Path $root 'pyproject.toml'
if (-not (Test-Path $pyproj)) { throw "pyproject.toml not found at $pyproj" }

# Ensure git is available.
Invoke-Step -Command "git --version"

# Refuse to run on a dirty working tree so the release commit stays clean.
if (-not $AllowDirty -and -not $DryRun) {
  $status = & git status --porcelain
  if ($LASTEXITCODE -ne 0) { throw "git status failed with exit code $LASTEXITCODE" }
  if ($status) {
    Write-Host "Working tree has uncommitted changes:" -ForegroundColor Red
    Write-Host $status
    throw "Refusing to run with a dirty working tree. Commit/stash first or pass -AllowDirty."
  }
}

# Resolve the branch to push (default: current HEAD).
if (-not $Branch) {
  if ($DryRun) {
    $Branch = '<current-branch>'
  } else {
    $Branch = (& git rev-parse --abbrev-ref HEAD).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $Branch -or $Branch -eq 'HEAD') {
      throw "Could not determine current git branch. Pass -Branch explicitly."
    }
  }
}

# Compute new version.
$currentVersion = Get-ProjectVersion -PyProjectPath $pyproj
if ($NewVersion) {
  $nextVersion = $NewVersion
} else {
  $nextVersion = Update-Version -Current $currentVersion -Part $Part
}
Write-Host "Current version: $currentVersion -> Next version: $nextVersion" -ForegroundColor Magenta

# Update the single source of truth for the package version.
Set-ProjectVersion -PyProjectPath $pyproj -Version $nextVersion

# Update release dates in CHANGELOG.md and RELEASE_NOTES.md.
Update-ReleaseDates -Version $nextVersion -RootPath $root

$tag = "$TagPrefix$nextVersion"
$message = if ($CommitMessage) { $CommitMessage } else { "Release $tag" }

if (-not $SkipCommit) {
  Invoke-Step -Command "git add coverity_metrics/__version__.py CHANGELOG.md RELEASE_NOTES.md"
  if ($DryRun) {
    Write-Host "[DRY-RUN] git commit -m `"$message`"" -ForegroundColor Yellow
  } else {
    Write-Host "[RUN] git commit -m `"$message`"" -ForegroundColor Cyan
    & git commit -m $message
    if ($LASTEXITCODE -ne 0) {
      # Tolerate "nothing to commit" (e.g. re-running for the same version); anything else is fatal.
      $remaining = & git status --porcelain
      if ($remaining) { throw "git commit failed with exit code $LASTEXITCODE" }
      Write-Host "Nothing to commit; continuing." -ForegroundColor Yellow
    }
  }
  Invoke-Step -Command "git push $Remote $Branch"
} else {
  Write-Host "Skipping commit/push of branch (SkipCommit set)." -ForegroundColor Yellow
}

# Preflight: run build-binaries.yml against the just-pushed commit and refuse
# to create the tag if any binary build fails. Keeps tags, PyPI, and the GitHub
# Release page in lockstep — no half-released artefacts.
if (-not $SkipTag -and -not $SkipPreflightCI) {
  # gh CLI is the only reasonable way to trigger + poll a workflow from PS.
  $ghAvailable = $null -ne (Get-Command gh -ErrorAction SilentlyContinue)
  if (-not $ghAvailable) {
    throw @"
Preflight CI check requires the GitHub CLI ('gh') to be installed and authenticated.
Install from https://cli.github.com/ and run 'gh auth login', then re-run this script.
To skip the preflight and fall back to the legacy 'tag and hope' flow, pass -SkipPreflightCI.
"@
  }

  $sha = if ($DryRun) { '<HEAD>' } else { (& git rev-parse HEAD).Trim() }
  Write-Host "" -ForegroundColor Cyan
  Write-Host "Preflight: dispatching build-binaries.yml against $Branch@$sha and waiting for green ..." -ForegroundColor Cyan

  if ($DryRun) {
    Write-Host "[DRY-RUN] gh workflow run build-binaries.yml --ref $Branch" -ForegroundColor Yellow
    Write-Host "[DRY-RUN] gh run watch <newest-run> --exit-status" -ForegroundColor Yellow
  } else {
    # Fail fast if the token can't hit the dispatch endpoint. GitHub returns
    # HTTP 403 "Must have admin rights to Repository" when the token lacks
    # the `workflow` OAuth scope (classic PAT) or `actions:write` (fine-grained).
    # This is a common trip because `gh auth login`'s default scope set does
    # not include `workflow`.
    $scopeCheck = & gh auth status 2>&1 | Out-String
    if ($scopeCheck -notmatch '(?ims)Token scopes:.*\bworkflow\b') {
      throw @"
GitHub CLI is authenticated but the current token is missing the 'workflow' scope,
which is required to trigger workflow_dispatch runs. Fix with one command:

    gh auth refresh -h github.com -s workflow

Then re-run this script. To bypass the preflight entirely (not recommended —
this is what let 1.1.8 / 1.1.9 ship half-broken), pass -SkipPreflightCI.
"@
    }

    # Snapshot the most recent run id BEFORE dispatch so we can tell which one is ours.
    # NB: filter on the PowerShell side rather than passing $sha into a `--jq` expression —
    # PS's native-command arg passer strips escaped quotes, so `--jq '... =="$sha" ...'`
    # arrives at gh.exe with a truncated jq string and fails to parse.
    $beforeJson = & gh run list --workflow=build-binaries.yml --branch=$Branch --limit=1 --json 'databaseId' 2>$null
    $before = if ($beforeJson) { ($beforeJson | ConvertFrom-Json | Select-Object -First 1).databaseId } else { $null }

    $dispatchOut = & gh workflow run build-binaries.yml --ref $Branch 2>&1
    if ($LASTEXITCODE -ne 0) {
      if ($dispatchOut -match '403|admin rights') {
        throw @"
gh workflow run failed with HTTP 403 (Must have admin rights to Repository).
The token is authenticated but lacks the 'workflow' scope. Fix with:

    gh auth refresh -h github.com -s workflow

Then re-run this script (safe — the version-bump commit is already pushed,
so re-invoking `./release.ps1 -NewVersion $nextVersion` will just retry the
preflight and, if green, create + push the tag).
"@
      }
      throw "gh workflow run failed with exit code $LASTEXITCODE`n$dispatchOut"
    }

    # Poll until GH surfaces a new run whose head_sha matches our commit.
    $runId = $null
    $deadline = (Get-Date).AddSeconds(60)
    while ((Get-Date) -lt $deadline) {
      Start-Sleep -Seconds 3
      $listJson = & gh run list --workflow=build-binaries.yml --branch=$Branch --limit=5 --json 'databaseId,headSha' 2>$null
      if ($listJson) {
        $match = $listJson | ConvertFrom-Json | Where-Object { $_.headSha -eq $sha } | Select-Object -First 1
        if ($match -and $match.databaseId -ne $before) {
          $runId = $match.databaseId
          break
        }
      }
    }
    if (-not $runId) {
      throw "Could not find the preflight run for $Branch@$sha within 60s. Check 'gh run list --workflow=build-binaries.yml' and re-run with -SkipPreflightCI if the run actually started."
    }
    Write-Host "Watching run $runId ..." -ForegroundColor Cyan
    & gh run watch $runId --exit-status
    if ($LASTEXITCODE -ne 0) {
      throw "Preflight build-binaries run $runId failed. Tag NOT created; nothing pushed to PyPI or GitHub Release. Fix the failure and re-run this script."
    }
    Write-Host "Preflight run $runId completed successfully. Proceeding to tag." -ForegroundColor Green
  }
} elseif ($SkipTag) {
  # No tag → nothing to gate. Silent.
} else {
  Write-Host "Skipping preflight CI validation (SkipPreflightCI set). Tag will be created without verifying binaries build." -ForegroundColor Yellow
}

if (-not $SkipTag) {
  Invoke-Step -Command "git tag -a $tag -m `"$message`""
  Invoke-Step -Command "git push $Remote $tag"
  Write-Host "" -ForegroundColor Green
  Write-Host "Tag $tag pushed to $Remote." -ForegroundColor Green
  Write-Host "GitHub Actions will now build the Windows/Linux binaries, publish to PyPI," -ForegroundColor Green
  Write-Host "and create the GitHub Release for $tag." -ForegroundColor Green
} else {
  Write-Host "Skipping tag creation/push (SkipTag set). Release workflow NOT triggered." -ForegroundColor Yellow
}

Write-Host "Done." -ForegroundColor Green
