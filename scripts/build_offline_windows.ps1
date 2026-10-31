param(
    [switch]$SkipModelPreparation,
    [switch]$SkipNodeInstall
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$BuildRoot = Join-Path $ProjectRoot ".build"
$RuntimeEnvironment = Join-Path $BuildRoot "runtime-venv"
$RuntimePython = Join-Path $RuntimeEnvironment "Scripts\python.exe"
$PythonCommand = Get-Command python -ErrorAction Stop
$BuildPython = $PythonCommand.Source

function Invoke-Checked {
    param([string]$Executable, [string[]]$Arguments)
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE : $Executable $($Arguments -join ' ')"
    }
}

New-Item -ItemType Directory -Force -Path $BuildRoot | Out-Null
$PythonVersion = & $BuildPython --version
Write-Host "Using $PythonVersion"

if (-not (Test-Path $RuntimePython)) {
    Invoke-Checked $BuildPython @("-m", "venv", $RuntimeEnvironment)
}

if (-not $SkipModelPreparation) {
    Invoke-Checked $BuildPython @((Join-Path $ProjectRoot "scripts\prepare_offline_model.py"))
    Invoke-Checked $BuildPython @((Join-Path $ProjectRoot "scripts\prepare_ocr_data.py"))
} else {
    Invoke-Checked $BuildPython @((Join-Path $ProjectRoot "scripts\prepare_offline_model.py"), "--verify-only")
    Invoke-Checked $BuildPython @((Join-Path $ProjectRoot "scripts\prepare_ocr_data.py"), "--verify-only")
}

$FrontendDirectory = Join-Path $ProjectRoot "frontend"
Push-Location $FrontendDirectory
try {
    if (-not $SkipNodeInstall) { Invoke-Checked "npm" @("ci") }
    Invoke-Checked "npm" @("run", "brand:build")
    Invoke-Checked "npm" @("run", "build:desktop")
    if (-not (Test-Path (Join-Path $FrontendDirectory ".next-desktop\index.html"))) {
        throw "The desktop frontend export was not created."
    }
} finally {
    Pop-Location
}

Invoke-Checked $RuntimePython @("-m", "pip", "install", "--upgrade", "pip")
Invoke-Checked $RuntimePython @("-m", "pip", "install", "-r", (Join-Path $ProjectRoot "requirements.txt"))
Invoke-Checked $RuntimePython @("-m", "pip", "install", "pyinstaller>=6.16,<7")

$BackendDist = Join-Path $BuildRoot "backend"
$BackendWork = Join-Path $BuildRoot "pyinstaller-work"
if (Test-Path $BackendDist) { Remove-Item -LiteralPath $BackendDist -Recurse -Force }
if (Test-Path $BackendWork) { Remove-Item -LiteralPath $BackendWork -Recurse -Force }
New-Item -ItemType Directory -Force -Path $BackendDist | Out-Null

$PyInstallerArgs = @(
    "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--console",
    "--name", "desktop_backend",
    "--distpath", $BackendDist,
    "--workpath", $BackendWork,
    "--specpath", $BuildRoot,
    "--paths", $ProjectRoot,
    "--collect-all", "fastapi",
    "--collect-all", "starlette",
    "--collect-all", "uvicorn",
    "--collect-all", "multipart",
    "--collect-binaries", "ctranslate2",
    "--collect-data", "ctranslate2",
    "--exclude-module", "ctranslate2.converters",
    "--exclude-module", "ctranslate2.specs",
    "--exclude-module", "transformers",
    "--exclude-module", "torch",
    "--copy-metadata", "ctranslate2",
    "--copy-metadata", "fastapi",
    "--copy-metadata", "starlette",
    "--copy-metadata", "uvicorn",
    (Join-Path $ProjectRoot "backend\main.py")
)
Invoke-Checked $RuntimePython $PyInstallerArgs

$DesktopDirectory = Join-Path $ProjectRoot "desktop"
Push-Location $DesktopDirectory
try {
    if (-not $SkipNodeInstall) { Invoke-Checked "npm" @("ci") }
    Invoke-Checked "npm" @("run", "build:windows")
} finally {
    Pop-Location
}

$Installer = Get-ChildItem (Join-Path $ProjectRoot "release") -Filter "BharatDocs-Setup-*.exe" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $Installer) { throw "electron-builder completed without producing the BharatDocs setup executable." }
$InstallerSize = [math]::Round($Installer.Length / 1GB, 2)
Write-Host ""
Write-Host "Offline installer created: $($Installer.FullName) ($InstallerSize GB)"
