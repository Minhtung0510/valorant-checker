$ErrorActionPreference = "Stop"
$Base = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Base

$PrivateKey = Join-Path $Base "license_private_key.pem"
$PublicKey = Join-Path $Base "license_public_key.pem"

if (-not (Test-Path $PrivateKey) -and -not (Test-Path $PublicKey)) {
    python generate_license_keypair.py
}

if (-not (Test-Path $PrivateKey)) {
    throw "Missing license_private_key.pem. The admin private key is required to build Key Manager."
}

if (-not (Test-Path $PublicKey)) {
    throw "Missing license_public_key.pem. The client cannot validate license keys without it."
}

python -m PyInstaller --noconfirm --clean --distpath dist --workpath build ValorantChecker.spec
python -m PyInstaller --noconfirm --clean --distpath dist --workpath build ValorantKeyManager.spec

$ClientDir = Join-Path $Base "dist\ValorantChecker"
$AdminDir = Join-Path $Base "dist\ValorantKeyManager"

Copy-Item $PrivateKey (Join-Path $AdminDir "license_private_key.pem") -Force

@"
# Mỗi dòng: username:password
# Có thể thêm region ở cột thứ ba: username:password:ap
"@ | Set-Content (Join-Path $ClientDir "accounts.example.txt") -Encoding UTF8

@"
# Mỗi dòng: ip:port:user:password
# Hoặc: ip:port
"@ | Set-Content (Join-Path $ClientDir "proxies.example.txt") -Encoding UTF8

Write-Host ""
Write-Host "Build completed:" -ForegroundColor Green
Write-Host "  Client: $ClientDir\ValorantChecker.exe"
Write-Host "  Admin:  $AdminDir\ValorantKeyManager.exe"
Write-Host ""
Write-Host "Do not send the ValorantKeyManager folder or private key to customers." -ForegroundColor Yellow

