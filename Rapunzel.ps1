Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogFile = Join-Path $RepoDir "rapunzel-launch.log"

Add-Content -Path $LogFile -Value ""
Add-Content -Path $LogFile -Value "===== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') Rapunzel.ps1 ====="

$VenvPython = Join-Path $RepoDir ".venv\Scripts\python.exe"
if (Test-Path $VenvPython) {
    $PythonCommand = $VenvPython
    $PythonArgs = @()
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $PythonCommand = (Get-Command python).Source
    $PythonArgs = @()
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $PythonCommand = (Get-Command py).Source
    $PythonArgs = @("-3")
} else {
    Add-Content -Path $LogFile -Value "Python 3 is required but was not found on PATH."
    Write-Error "Python 3 is required but was not found on PATH."
}

if (-not (Test-Path (Join-Path $RepoDir "webui\dist\app.js"))) {
    Add-Content -Path $LogFile -Value "Missing built frontend. Run .\install.ps1 first."
    Write-Error "Missing built frontend. Run .\install.ps1 first."
}

Set-Location $RepoDir
Add-Content -Path $LogFile -Value "repo=$RepoDir"
Add-Content -Path $LogFile -Value "python=$PythonCommand $($PythonArgs -join ' ')"
& $PythonCommand @PythonArgs (Join-Path $RepoDir "app.py") *>> $LogFile
