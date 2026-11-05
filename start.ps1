# Launch FloChat using the project's own virtual environment (Windows).
#
# This script never installs anything and never modifies the environment. If the
# environment is missing or broken it says so and points at install.ps1.

$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Venv = Join-Path $Root '.venv'
$VenvPython = Join-Path $Venv 'Scripts\python.exe'

if (-not (Test-Path $Venv)) {
    Write-Host 'FloChat is not installed in this directory.' -ForegroundColor Red
    Write-Host "  Next:  cd `"$Root`" ; .\install.ps1"
    exit 2
}

if (-not (Test-Path $VenvPython)) {
    Write-Host "The environment at $Venv is incomplete (no Scripts\python.exe)." -ForegroundColor Red
    Write-Host '  Why:   a previous install was interrupted or the folder was moved.'
    Write-Host "  Next:  Remove-Item -Recurse -Force '$Venv' ; .\install.ps1"
    exit 2
}

$importCheck = & $VenvPython -c 'import flochat.cli' 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "FloChat is installed but cannot be imported in $Venv." -ForegroundColor Red
    Write-Host "  Why:   $($importCheck -join ' ')"
    Write-Host '  Next:  .\install.ps1   (it will repair the environment)'
    exit 1
}

if ($args.Count -eq 0) {
    & $VenvPython -m flochat.cli --help
} else {
    & $VenvPython -m flochat.cli @args
}
exit $LASTEXITCODE
