param(
    [string]$OrbitaSource = "$HOME\Downloads\Gologin\All-Browsers\orbita-browser-145"
)

$ErrorActionPreference = "Stop"
$Base = Split-Path -Parent $MyInvocation.MyCommand.Path
$InstallerDir = Join-Path $Base "installer"
$DistDir = Join-Path $InstallerDir "dist-package"
$ChromeExe = Join-Path $OrbitaSource "chrome.exe"

if (-not (Test-Path $ChromeExe)) {
    throw "Orbita chrome.exe not found: $ChromeExe"
}

$IsccCandidates = @(
    "$env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
)
$Iscc = $IsccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Iscc) {
    throw "Inno Setup 6 is required. Install it, then run this script again."
}

Push-Location $Base
try {
    # Bước 1: Build app chính
    python -m PyInstaller `
        --noconfirm `
        --clean `
        --distpath $DistDir `
        --workpath (Join-Path $InstallerDir "build-package") `
        ValorantChecker.spec

    # Bước 2: Build installer
    & $Iscc "/DOrbitaSource=$OrbitaSource" (Join-Path $InstallerDir "ValorantChecker.iss")
} finally {
    Pop-Location
}

Write-Host "Installer created in: $InstallerDir\output" -ForegroundColor Green
