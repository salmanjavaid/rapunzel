Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RepoDir

if (Get-Command python -ErrorAction SilentlyContinue) {
    $PythonCommand = "python"
    $PythonArgs = @()
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $PythonCommand = "py"
    $PythonArgs = @("-3")
} else {
    Write-Error "Python 3 is required but was not found on PATH."
}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Error "npm is required but was not found on PATH."
}

if (-not (Test-Path ".venv")) {
    & $PythonCommand @PythonArgs -m venv .venv
}

$VenvPython = Join-Path $RepoDir ".venv\Scripts\python.exe"
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r requirements.txt
npm install
npm run build:webui

Write-Host ""
Write-Host "Rapunzel is ready."
Write-Host "Launch with: .\Rapunzel.ps1"
