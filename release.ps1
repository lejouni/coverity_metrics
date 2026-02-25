<#
.SYNOPSIS
  Build and publish the coverity-metrics package, with version bumping and optional install verification.

.DESCRIPTION
  - Bumps the version in pyproject.toml (major/minor/patch or explicit version).
  - Builds wheel and sdist into dist/ using `python -m build`.
  - Uploads to TestPyPI by default via `twine upload` (or to PyPI if selected).
  - Optionally creates a temporary venv to pip install from the target index and verifies the CLI.

.PARAMETER Part
  Which part of the version to bump: patch (default), minor, or major. Ignored if -NewVersion is supplied.

.PARAMETER NewVersion
  Explicit version string to set (e.g. 1.0.1). Overrides -Part.

.PARAMETER Repository
  Target repository: testpypi (default) or pypi.

.PARAMETER NoInstallTest
  Skip the post-upload install verification step.

.PARAMETER SkipBuild
  Skip the build step (use existing artifacts in dist/).

.PARAMETER DryRun
  Print what would be done without executing commands.

.PARAMETER NoUpload
  Skip uploading artifacts; useful for local-only sharing. If install test is enabled, it will install from local dist/.

.PARAMETER SkipToolsUpgrade
  Skip upgrading pip and installing build/twine tools. Use if that step is slow or managed externally.

.PARAMETER PipArgs
  Extra arguments to pass to pip install commands (e.g., "--timeout 30 --retries 1 --index-url https://... --trusted-host ...").

.PARAMETER NoIsolation
  Run `python -m build` with `--no-isolation` to avoid creating a temporary isolated env (use current venv). Useful in restricted networks.

.PARAMETER Offline
  Use offline mode for install verification (adds --no-index and --find-links). Requires dependency wheels to be present locally.

.PARAMETER FindLinks
  Additional folder path for --find-links when -Offline is used (e.g., a cache of dependency wheels).

.PARAMETER CreateGitHubRelease
  Create a GitHub release after successful upload.

.PARAMETER GitHubRepo
  GitHub repository in owner/repo format. Default: yourusername/coverity-metrics

.PARAMETER GitHubToken
  GitHub personal access token for creating releases. If not provided, uses GITHUB_TOKEN environment variable.

.PARAMETER SkipGitTag
  Skip creating and pushing git tag.

.PARAMETER TagPrefix
  Prefix for git tags. Default: 'v'

.PARAMETER ReleaseNotesPath
  Path to a file containing release notes to include in the GitHub release.

.EXAMPLE
  # Bump patch, build, upload to TestPyPI, and verify install
  ./release.ps1 -Part patch -Repository testpypi

.EXAMPLE
  # Set an explicit version and publish to PyPI without install test
  ./release.ps1 -NewVersion 1.0.1 -Repository pypi -NoInstallTest

.EXAMPLE
  # Create a GitHub release
  ./release.ps1 -NewVersion 1.1.0 -Repository pypi -CreateGitHubRelease -GitHubToken "ghp_..."
#>

[CmdletBinding()]
param(
  [ValidateSet('patch','minor','major')]
  [string]$Part = 'patch',

  [string]$NewVersion,

  [ValidateSet('testpypi','pypi')]
  [string]$Repository = 'pypi',

  [switch]$NoInstallTest,
  [switch]$SkipBuild,
  [switch]$DryRun,
  [switch]$NoUpload,
  [switch]$SkipToolsUpgrade,
  [string]$PipArgs,
  [switch]$NoIsolation,
  [switch]$Offline,
  [string]$FindLinks,
  [string]$TwineUsername,
  [string]$TwinePassword,

  # Git/GitHub release options
  [switch]$CreateGitHubRelease,
  [string]$GitHubRepo = 'lejouni/coverity_metrics',
  [string]$GitHubToken,
  [switch]$SkipGitTag,
  [string]$TagPrefix = 'v',
  [string]$ReleaseNotesPath
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
  $content = Get-Content -Raw -LiteralPath $PyProjectPath
  $m = [regex]::Match($content, 'version\s*=\s*"(?<v>\d+\.\d+\.\d+)"')
  if (-not $m.Success) { throw "Could not find version in $PyProjectPath" }
  return $m.Groups['v'].Value
}

function Set-ProjectVersion {
  param([string]$PyProjectPath, [string]$Version)
  $content = Get-Content -Raw -LiteralPath $PyProjectPath -Encoding UTF8
  # Use -replace and escape quotes for PowerShell with backticks
  $new = $content -replace 'version\s*=\s*"\d+\.\d+\.\d+"', "version = `"$Version`""
  if ($DryRun) {
    Write-Host "[DRY-RUN] Would set version to $Version in $PyProjectPath (UTF-8 no BOM)" -ForegroundColor Yellow
  } else {
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($PyProjectPath, $new, $utf8NoBom)
    Write-Host "Set version to $Version in $PyProjectPath" -ForegroundColor Green
  }

  # Also update __version__ in coverity_metrics/__version__.py
  $versionPath = Join-Path (Split-Path $PyProjectPath) 'coverity_metrics/__version__.py'
  if (Test-Path $versionPath) {
    $versionContent = Get-Content -Raw -LiteralPath $versionPath -Encoding UTF8
    $versionNew = $versionContent -replace '__version__\s*=\s*"\d+\.\d+\.\d+"', "__version__ = `"$Version`""
    if ($DryRun) {
      Write-Host "[DRY-RUN] Would set __version__ to $Version in $versionPath (UTF-8 no BOM)" -ForegroundColor Yellow
    } else {
      [System.IO.File]::WriteAllText($versionPath, $versionNew, $utf8NoBom)
      Write-Host "Set __version__ to $Version in $versionPath" -ForegroundColor Green
    }
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

function New-GitTagAndPush {
  param(
    [Parameter(Mandatory=$true)][string]$Tag,
    [string]$Message = $("Release $Tag")
  )
  # Ensure git exists
  Invoke-Step -Command "git --version"
  # Create annotated tag and push
  Invoke-Step -Command "git tag -a $Tag -m `"$Message`""
  Invoke-Step -Command "git push origin $Tag"
}

function New-GitHubRelease {
  param(
    [Parameter(Mandatory=$true)][string]$Repo,
    [Parameter(Mandatory=$true)][string]$Tag,
    [string]$Name,
    [string]$Body,
    [string]$Token
  )
  $tokenToUse = if ($Token) { $Token } elseif ($env:GITHUB_TOKEN) { $env:GITHUB_TOKEN } else { $null }
  if (-not $tokenToUse) { throw "GitHub token not provided. Use -GitHubToken or set GITHUB_TOKEN env var." }

  $headers = @{
    Authorization = "Bearer $tokenToUse";
    Accept        = 'application/vnd.github+json';
    'User-Agent'  = 'coverity-metrics-release-script'
  }
  # Build JSON payload
  $releaseName = if ($Name) { $Name } else { $Tag }
  $releaseBody = if ($Body) { $Body } else { "Release $Tag" }
  $payloadObj = [ordered]@{
    tag_name   = $Tag
    name       = $releaseName
    body       = $releaseBody
    draft      = $false
    prerelease = $false
  }
  $payload = $payloadObj | ConvertTo-Json -Depth 5

  $url = "https://api.github.com/repos/$Repo/releases"
  if ($DryRun) {
    Write-Host "[DRY-RUN] Would create GitHub Release: $url tag=$Tag name=$Name" -ForegroundColor Yellow
    return
  }
  Write-Host "Creating GitHub Release $Tag in $Repo..." -ForegroundColor Green
  $resp = Invoke-RestMethod -Method Post -Uri $url -Headers $headers -Body $payload -ContentType 'application/json'
  if (-not $resp.id) { throw "Failed to create GitHub Release for tag $Tag" }
  Write-Host "GitHub Release created: $($resp.html_url)" -ForegroundColor Green
}

$root = Resolve-Path .
$pyproj = Join-Path $root 'pyproject.toml'
if (-not (Test-Path $pyproj)) { throw "pyproject.toml not found at $pyproj" }

# Ensure Python is available
Invoke-Step -Command "python --version"
if (-not $SkipToolsUpgrade) {
  $pipArgsText = $PipArgs
  if ($pipArgsText) { Write-Host "Using pip extra args: $pipArgsText" -ForegroundColor DarkCyan }
  Invoke-Step -Command "python -m pip install $pipArgsText --upgrade pip"
  Invoke-Step -Command "python -m pip install $pipArgsText --upgrade build twine"
} else {
  Write-Host "Skipping pip/build/twine upgrade (SkipToolsUpgrade set)." -ForegroundColor Yellow
}

# Compute new version
$currentVersion = Get-ProjectVersion -PyProjectPath $pyproj
if ($NewVersion) {
  $nextVersion = $NewVersion
} else {
  $nextVersion = Update-Version -Current $currentVersion -Part $Part
}
Write-Host "Current version: $currentVersion -> Next version: $nextVersion" -ForegroundColor Magenta

# Update version in pyproject.toml and __version__.py
Set-ProjectVersion -PyProjectPath $pyproj -Version $nextVersion

# Update release dates in CHANGELOG.md and RELEASE_NOTES.md
Update-ReleaseDates -Version $nextVersion -RootPath $root

if (-not $SkipBuild) {
  # Clean existing artifacts
  foreach ($p in @('dist','build')) {
    if (Test-Path $p) {
      if ($DryRun) { Write-Host "[DRY-RUN] Would remove $p" -ForegroundColor Yellow }
      else { Remove-Item -Recurse -Force $p }
    }
  }
  Get-ChildItem -Filter '*.egg-info' | ForEach-Object {
    if ($DryRun) { Write-Host "[DRY-RUN] Would remove $($_.FullName)" -ForegroundColor Yellow }
    else { Remove-Item -Recurse -Force $_.FullName }
  }
  # Build
  $buildCmd = "python -m build"
  if ($NoIsolation) { $buildCmd += " --no-isolation" }
  Invoke-Step -Command $buildCmd
}

if (-not $NoUpload) {
  # Upload
  $cleanuppw = $false
  try {
    if ($TwineUsername) {
      if ($DryRun) { Write-Host "[DRY-RUN] Would set TWINE_USERNAME for upload" -ForegroundColor Yellow } else { $env:TWINE_USERNAME = $TwineUsername }     
    }
    if ($TwinePassword) {
      if ($DryRun) { Write-Host "[DRY-RUN] Would set TWINE_PASSWORD for upload" -ForegroundColor Yellow } else { $env:TWINE_PASSWORD = $TwinePassword }     
      $cleanuppw = $true
    }
    if ($Repository -eq 'testpypi') {
      Write-Host "Uploading to TestPyPI..." -ForegroundColor Green
      Invoke-Step -Command "python -m twine upload --repository testpypi dist/*"
    } else {
      Write-Host "Uploading to PyPI..." -ForegroundColor Green
      Invoke-Step -Command "python -m twine upload dist/*"
    }
  }
  finally {
    if (-not $DryRun) {
      if ($TwineUsername) { Remove-Item Env:TWINE_USERNAME -ErrorAction SilentlyContinue }
      if ($cleanuppw) { Remove-Item Env:TWINE_PASSWORD -ErrorAction SilentlyContinue }
    }
  }
} else {
  Write-Host "Skipping upload (NoUpload set)." -ForegroundColor Yellow
}

# Optionally tag and create a GitHub Release
try {
  if ($CreateGitHubRelease) {
    $tag = "$TagPrefix$nextVersion"
    $relBody = $null
    if ($ReleaseNotesPath -and (Test-Path $ReleaseNotesPath)) {
      $relBody = Get-Content -Raw -LiteralPath $ReleaseNotesPath -Encoding UTF8
    } else {
      $relBody = "Release $tag`n`nPublished to $Repository as coverity-metrics $nextVersion."
    }

    if (-not $SkipGitTag) {
      New-GitTagAndPush -Tag $tag -Message "Release $tag"
    } else {
      Write-Host "Skipping git tag creation/push (SkipGitTag set)." -ForegroundColor Yellow
    }

    New-GitHubRelease -Repo $GitHubRepo -Tag $tag -Name $tag -Body $relBody -Token $GitHubToken
  }
} catch {
  Write-Host "GitHub release step failed: $($_.Exception.Message)" -ForegroundColor Red
  throw
}

if ((-not $NoInstallTest) -and (-not $DryRun)) {
  # Wait for PyPI/TestPyPI to index the new version and for the wheel file to be downloadable
  if (-not $NoUpload) {
    $maxWait = 180
    $interval = 5
    $waited = 0
    $pypiUrl = "https://pypi.org/pypi/coverity-metrics/json"
    Write-Host "Checking PyPI for version $nextVersion..." -ForegroundColor Yellow
    $wheelFound = $false
    while ($true) {
      try {
        $resp = Invoke-WebRequest -Uri $pypiUrl -UseBasicParsing -ErrorAction Stop
        $json = $resp.Content | ConvertFrom-Json
        if ($json.releases.PSObject.Properties.Name -contains $nextVersion) {
          # Check for wheel file
          $releaseFiles = $json.releases.$nextVersion
          foreach ($file in $releaseFiles) {
            if ($file.filename -like "*.whl") {
              $wheelFileUrl = $file.url
              try {
                $wheelResp = Invoke-WebRequest -Uri $wheelFileUrl -Method Head -UseBasicParsing -ErrorAction Stop
                if ($wheelResp.StatusCode -eq 200) {
                  Write-Host "Wheel file for $nextVersion is downloadable!" -ForegroundColor Green
                  $wheelFound = $true
                  break
                }
              } catch {
                Write-Host "Wheel file not yet downloadable. Waiting $interval seconds..." -ForegroundColor Yellow
              }
            }
          }
          if ($wheelFound) { break }
          Write-Host "Version $nextVersion listed, but wheel file not yet downloadable. Waiting $interval seconds..." -ForegroundColor Yellow
        } else {
          Write-Host "Version $nextVersion not yet listed. Waiting $interval seconds..." -ForegroundColor Yellow
        }
      } catch {
        Write-Host "Error checking PyPI: $($_.Exception.Message)" -ForegroundColor Red
      }
      Start-Sleep -Seconds $interval
      $waited += $interval
      if ($waited -ge $maxWait) {
        Write-Host "Timeout waiting for PyPI to list and serve wheel for version $nextVersion. Proceeding anyway." -ForegroundColor Red
        break
      }
    }
  }

  if ($NoUpload) {
    Write-Host "Verifying local install from dist/ (NoUpload set)..." -ForegroundColor Green
  } else {
    Write-Host "Verifying install from $Repository..." -ForegroundColor Green
  }
  $venv = Join-Path $root '.pkgtest'
  if (-not $DryRun) {
    if (Test-Path $venv) {
      # Windows: Try to remove, retry if locked
      $retries = 3
      for ($i = 1; $i -le $retries; $i++) {
        try {
          Remove-Item -Recurse -Force $venv -ErrorAction Stop
          break
        } catch {
          if ($i -lt $retries) {
            Write-Host "Failed to remove $venv (attempt $i/$retries), retrying..." -ForegroundColor Yellow
            Start-Sleep -Seconds 2
          } else {
            Write-Host "Warning: Could not remove $venv, using a new directory instead" -ForegroundColor Yellow
            $venv = Join-Path $root ".pkgtest_$(Get-Date -Format 'yyyyMMddHHmmss')"
          }
        }
      }
    }
  } else {
    Write-Host "[DRY-RUN] Would create temp venv at $venv" -ForegroundColor Yellow
  }
  Invoke-Step -Command "python -m venv `"$venv`""
  $testPy = Join-Path $venv 'Scripts/python.exe'
  Invoke-Step -Command "`"$testPy`" -m pip install --upgrade pip"
  
  if ($NoUpload) {
    # Install from local dist wheel
    $wheel = Get-ChildItem -Path (Join-Path $root 'dist') -Filter "*-$nextVersion-*.whl" | Select-Object -First 1
    if (-not $wheel) { throw "No wheel for version $nextVersion found in dist/." }
    if ($Offline) {
      # Fully offline: require local dependency wheels via --find-links
      $cmd = "$testPy -m pip install --no-index --find-links dist"
      if ($FindLinks) { $cmd += " --find-links `"$FindLinks`"" }
      $cmd += " `"$($wheel.FullName)`""
      Invoke-Step -Command $cmd
    } else {
      # Normal local install: dependencies resolved from PyPI as needed
      Invoke-Step -Command "$testPy -m pip install `"$($wheel.FullName)`""
    }
  } else {
    if ($Repository -eq 'testpypi') {
      $installCmd = "$testPy -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple coverity-metrics==$nextVersion"
    } else {
      $installCmd = "$testPy -m pip install --index-url https://pypi.org/simple/ coverity-metrics==$nextVersion"
    }
    
    $maxInstallWait = 180
    $installInterval = 5
    $installWaited = 0
    while ($true) {
      try {
        Invoke-Step -Command $installCmd
        break
      } catch {
        Write-Host "pip install failed, retrying in $installInterval seconds..." -ForegroundColor Yellow
      }
      Start-Sleep -Seconds $installInterval
      $installWaited += $installInterval
      if ($installWaited -ge $maxInstallWait) {
        Write-Host "Timeout waiting for pip install to succeed. Proceeding anyway." -ForegroundColor Red
        break
      }
    }
  }
  
  # Verify CLI commands
  Write-Host "Verifying coverity-dashboard CLI..." -ForegroundColor Cyan
  Invoke-Step -Command "$testPy -m coverity_metrics.cli.dashboard --help"
  Write-Host "Verifying coverity-metrics CLI..." -ForegroundColor Cyan
  Invoke-Step -Command "$testPy -c `"from coverity_metrics import __version__; print('Version:', __version__)`""
}

Write-Host "Done." -ForegroundColor Green
