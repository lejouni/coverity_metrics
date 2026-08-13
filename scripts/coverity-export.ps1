<#
.SYNOPSIS
  Quickstart for coverity-export on Windows.

.DESCRIPTION
  Downloads the coverity-metrics standalone binary for the given release tag
  (or the latest release), sets the required connection environment variables,
  and runs 'coverity-metrics export'. No Python install required on the host.

  EDIT the "EDIT THESE VALUES" block near the top to match your environment,
  or set the same variable names in your PowerShell session before running
  this script — the script only assigns a default when the variable is empty.

.PARAMETER Tag
  Release tag to download (default: latest resolved from the GitHub API).

.PARAMETER Output
  Output directory for the ZIP export (default: exports).

.PARAMETER Days
  Trend analysis window in days (default: 365).

.PARAMETER Project
  Comma-separated project filter (default: all projects).

.PARAMETER Workers
  Number of parallel workers for per-project export (default: 1, capped at 8
  by the binary). Each worker opens its own Postgres connection.

.PARAMETER Anonymize
  Replace real project/stream names with sequential ids and write a sibling
  <zip>.mapping.json file.

.PARAMETER NoSnapshots
  Skip the Snapshots metric (privacy).

.PARAMETER NoLeaderboards
  Skip the Leaderboards metrics (privacy).

.PARAMETER Insecure
  Skip TLS certificate verification for the GitHub API call and binary
  download. Use only when your environment presents a broken TLS chain
  (e.g. corporate SSL-inspection proxies with an untrusted root). Last-resort
  escape hatch — you're on your own to verify the downloaded binary.

.PARAMETER BinDir
  Where to cache the downloaded binary (default: .\bin next to this script).

.EXAMPLE
  # Download the latest release and export everything
  ./coverity-export.ps1

.EXAMPLE
  # Pin a specific tag, anonymize, and skip snapshots + leaderboards
  ./coverity-export.ps1 -Tag v1.0.22 -Anonymize -NoSnapshots -NoLeaderboards
#>

[CmdletBinding()]
param(
    [string]$Tag = '',
    [string]$Output = 'exports',
    [int]   $Days = 365,
    [string]$Project = '',
    [int]   $Workers = 1,
    [switch]$Anonymize,
    [switch]$NoSnapshots,
    [switch]$NoLeaderboards,
    [switch]$Insecure,
    [string]$BinDir = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# --------------------------------------------------------------------------- #
# EDIT THESE VALUES to point at your Coverity Postgres database.
# --------------------------------------------------------------------------- #
if (-not $env:COVERITY_DB_HOST)       { $env:COVERITY_DB_HOST       = 'coverity-prod.company.com' }
if (-not $env:COVERITY_DB_PORT)       { $env:COVERITY_DB_PORT       = '5432' }
if (-not $env:COVERITY_DB_NAME)       { $env:COVERITY_DB_NAME       = 'cim' }
if (-not $env:COVERITY_DB_USER)       { $env:COVERITY_DB_USER       = 'coverity_ro' }
if (-not $env:COVERITY_DB_PASSWORD)   { $env:COVERITY_DB_PASSWORD   = 'change-me' }
if (-not $env:COVERITY_INSTANCE_NAME) { $env:COVERITY_INSTANCE_NAME = 'Production' }
# --------------------------------------------------------------------------- #

$Repo = 'lejouni/coverity_metrics'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $BinDir) { $BinDir = Join-Path $ScriptDir 'bin' }

# Last-resort escape hatch for corporate SSL-inspection proxies with an
# untrusted MITM root. Only affects Invoke-WebRequest / Invoke-RestMethod
# inside this script; nothing else in the session is changed.
if ($Insecure) {
    Write-Host 'WARNING: -Insecure set - skipping TLS certificate verification on GitHub downloads.' -ForegroundColor Yellow
    Add-Type -TypeDefinition @'
using System.Net;
using System.Net.Security;
using System.Security.Cryptography.X509Certificates;
public static class _CoverityQuickstartInsecure {
    public static void Enable() {
        ServicePointManager.ServerCertificateValidationCallback =
            delegate { return true; };
    }
}
'@ -ErrorAction SilentlyContinue
    [_CoverityQuickstartInsecure]::Enable()
}

$BinPath = $null

# When -Tag is not supplied, prefer a cached binary from a previous run so we
# don't hit the GitHub API (or the network at all) unnecessarily.
if (-not $Tag -and (Test-Path $BinDir)) {
    $cached = Get-ChildItem -Path $BinDir -Filter 'coverity-metrics-windows-*.exe' -File -ErrorAction SilentlyContinue |
              Sort-Object LastWriteTime -Descending |
              Select-Object -First 1
    if ($cached) {
        $BinPath = $cached.FullName
        $Tag = $cached.BaseName -replace '^coverity-metrics-windows-', ''
        Write-Host "Using cached binary: $BinPath (tag $Tag)" -ForegroundColor DarkGray
    }
}

# Resolve the latest tag from the GitHub API only if we still don't know one.
if (-not $Tag) {
    Write-Host "Resolving latest release tag from GitHub..." -ForegroundColor Cyan
    $apiUrl = "https://api.github.com/repos/$Repo/releases/latest"
    try {
        $release = Invoke-RestMethod -Uri $apiUrl -UseBasicParsing -Headers @{ 'User-Agent' = 'coverity-export-quickstart' }
        $Tag = $release.tag_name
    } catch {
        throw "Could not resolve latest tag from $apiUrl : $($_.Exception.Message)"
    }
    if (-not $Tag) { throw "Could not resolve latest tag from $apiUrl" }
    Write-Host "Latest tag: $Tag" -ForegroundColor Green
}

$BinName = "coverity-metrics-windows-$Tag.exe"
if (-not $BinPath) { $BinPath = Join-Path $BinDir $BinName }
$Url = "https://github.com/$Repo/releases/download/$Tag/$BinName"

if (Test-Path $BinPath -PathType Leaf) {
    Write-Host "Using cached binary: $BinPath" -ForegroundColor DarkGray
} else {
    Write-Host "Downloading $Url" -ForegroundColor Cyan
    New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
    try {
        Invoke-WebRequest -Uri $Url -OutFile $BinPath -UseBasicParsing
    } catch {
        if (Test-Path $BinPath) { Remove-Item -Force $BinPath }
        throw "Failed to download $Url : $($_.Exception.Message)"
    }
}

# Refuse to run with the placeholder password so nobody triggers a real export
# with an unedited copy of this script.
if ($env:COVERITY_DB_PASSWORD -eq 'change-me') {
    throw "COVERITY_DB_PASSWORD is still the placeholder value 'change-me'. Edit this script (or set `$env:COVERITY_DB_PASSWORD`) before running."
}

$argsList = @('export', '--output', $Output, '--days', $Days.ToString(), '--workers', $Workers.ToString())
if ($Project)        { $argsList += @('--project', $Project) }
if ($Anonymize)      { $argsList += '--anonymize' }
if ($NoSnapshots)    { $argsList += '--no-snapshots' }
if ($NoLeaderboards) { $argsList += '--no-leaderboards' }
# Forward PowerShell's built-in -Verbose common parameter to the binary's --verbose flag.
if ($VerbosePreference -ne 'SilentlyContinue') { $argsList += '--verbose' }

Write-Host ""
Write-Host ("Instance : {0}" -f $env:COVERITY_INSTANCE_NAME)
Write-Host ("Host     : {0}" -f $env:COVERITY_DB_HOST)
Write-Host ("Database : {0}" -f $env:COVERITY_DB_NAME)
Write-Host ("User     : {0}" -f $env:COVERITY_DB_USER)
Write-Host ("Output   : {0}" -f $Output)
Write-Host ("Days     : {0}" -f $Days)
Write-Host ("Workers  : {0}" -f $Workers)
Write-Host ("Binary   : {0}" -f $BinPath)
Write-Host ""
Write-Host ("Running: `"{0}`" {1}" -f $BinPath, ($argsList -join ' ')) -ForegroundColor Cyan
Write-Host ""

& $BinPath @argsList
if ($LASTEXITCODE -ne 0) {
    throw "coverity-metrics export failed with exit code $LASTEXITCODE"
}
