# Installation script for Coverity Metrics Analyzer
# This script builds and installs the package in the current Python environment

param(
    [switch]$Dev,           # Install in development mode (-e)
    [switch]$Upgrade,       # Upgrade if already installed
    [switch]$Clean,         # Clean build artifacts before installing
    [switch]$Help           # Show help message
)

# Color functions
function Write-Success { param($Message) Write-Host $Message -ForegroundColor Green }
function Write-Info { param($Message) Write-Host $Message -ForegroundColor Cyan }
function Write-Warning { param($Message) Write-Host $Message -ForegroundColor Yellow }
function Write-Error { param($Message) Write-Host $Message -ForegroundColor Red }

# Help message
if ($Help) {
    Write-Host ""
    Write-Info "Coverity Metrics Analyzer - Installation Script"
    Write-Host ""
    Write-Host "Usage: .\install.ps1 [options]"
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  -Dev        Install in development/editable mode (pip install -e .)"
    Write-Host "  -Upgrade    Upgrade if already installed (pip install --upgrade)"
    Write-Host "  -Clean      Remove build artifacts before installation"
    Write-Host "  -Help       Show this help message"
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  .\install.ps1              # Normal installation"
    Write-Host "  .\install.ps1 -Dev         # Development installation"
    Write-Host "  .\install.ps1 -Upgrade     # Upgrade existing installation"
    Write-Host "  .\install.ps1 -Clean       # Clean install"
    Write-Host "  .\install.ps1 -Dev -Clean  # Clean development install"
    Write-Host ""
    exit 0
}

Write-Host ""
Write-Info "==================================================================="
Write-Info "  Coverity Metrics Analyzer - Installation Script"
Write-Info "==================================================================="
Write-Host ""

# Check if Python is available
Write-Info "Checking Python installation..."
try {
    $pythonVersion = python --version 2>&1
    Write-Success "[OK] $pythonVersion"
} catch {
    Write-Error "[ERROR] Python not found. Please install Python 3.10+ and add it to PATH."
    exit 1
}

# Check Python version
$versionMatch = $pythonVersion -match "Python (\d+)\.(\d+)"
if ($versionMatch) {
    $major = [int]$matches[1]
    $minor = [int]$matches[2]
    if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 10)) {
        Write-Error "[ERROR] Python 3.10+ is required (pandas>=3.0 and matplotlib>=3.10 need it). Found Python $major.$minor"
        exit 1
    }
}

# Check if pip is available
Write-Info "Checking pip installation..."
try {
    $pipVersion = pip --version 2>&1
    Write-Success "[OK] pip is available"
} catch {
    Write-Error "[ERROR] pip not found. Please install pip."
    exit 1
}

# Clean build artifacts if requested
if ($Clean) {
    Write-Info "Cleaning build artifacts..."
    $cleanDirs = @(
        "build",
        "dist",
        "*.egg-info",
        "coverity_metrics.egg-info",
        "__pycache__",
        "coverity_metrics/__pycache__"
    )
    foreach ($dir in $cleanDirs) {
        if (Test-Path $dir) {
            Write-Host "  Removing $dir"
            Remove-Item -Recurse -Force $dir -ErrorAction SilentlyContinue
        }
    }
    Write-Success "[OK] Cleanup complete"
}

# Build installation command
$installCmd = "pip install"
if ($Upgrade) {
    $installCmd += " --upgrade"
}
if ($Dev) {
    $installCmd += " -e ."
    Write-Info "Installing in development mode..."
} else {
    $installCmd += " ."
    Write-Info "Installing package..."
}
Write-Host "  Command: $installCmd"
Write-Host ""
# Run installation
try {
    Invoke-Expression $installCmd
    if ($LASTEXITCODE -ne 0) {
        throw "Installation failed with exit code $LASTEXITCODE"
    }
} catch {
    Write-Host ""
    Write-Error "[ERROR] Installation failed: $_"
    exit 1
}

Write-Host ""
Write-Success "==================================================================="
Write-Success "  Installation completed successfully!"
Write-Success "==================================================================="
Write-Host ""

# Verify installation
Write-Info "Verifying installation..."
try {
    $covmetricsVersion = coverity-metrics --version 2>&1
    Write-Success "[OK] coverity-metrics command is available"
    Write-Host "  $covmetricsVersion"
} catch {
    Write-Warning "[WARNING] Could not verify coverity-metrics command. You may need to restart your terminal."
}

Write-Host ""
Write-Info "Quick Start:"
Write-Host "  coverity-metrics <path-to-zip-file>"
Write-Host "  coverity-metrics --help"
Write-Host ""

if ($Dev) {
    Write-Info "Development Mode:"
    Write-Host "  Changes to the source code will be immediately reflected."
    Write-Host "  No need to reinstall after making changes."
    Write-Host ""
}

Write-Info "For more information, see README.md"
Write-Host ""
