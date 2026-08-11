<#
.SYNOPSIS
  Build the standalone coverity-metrics.exe on Windows using PyInstaller.

.DESCRIPTION
  Runs PyInstaller against packaging/coverity-metrics.spec and produces
  dist/coverity-metrics.exe. Assumes the current Python environment has the
  project installed with the `build` extra: `pip install -e .[build]`.
#>

[CmdletBinding()]
param(
    [switch]$Clean = $true,
    [string]$Python = 'python'
)

$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot  = Split-Path -Parent $scriptDir
Set-Location $repoRoot

Write-Host "Building coverity-metrics binary..." -ForegroundColor Cyan
Write-Host "  repo root : $repoRoot"
Write-Host "  python    : $Python"

$pyiArgs = @('-m', 'PyInstaller', 'packaging/coverity-metrics.spec', '--noconfirm')
if ($Clean) { $pyiArgs += '--clean' }

& $Python @pyiArgs
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }

$exe = Join-Path $repoRoot 'dist/coverity-metrics.exe'
if (-not (Test-Path $exe)) { throw "Expected binary not found: $exe" }

Write-Host ""
Write-Host "Smoke test: $exe dashboard --version" -ForegroundColor Cyan
& $exe dashboard --version
if ($LASTEXITCODE -ne 0) { Write-Warning "Binary exited with code $LASTEXITCODE on smoke test" }

$size = [math]::Round((Get-Item $exe).Length / 1MB, 1)
Write-Host ""
Write-Host "Built: $exe ($size MB)" -ForegroundColor Green
