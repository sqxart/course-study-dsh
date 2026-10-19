# Install course-study-dsh into the DeepSeek Harness skill root.
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\install.ps1
#   powershell -ExecutionPolicy Bypass -File .\install.ps1 -Target C:\path\to\skills\course-study-dsh

param(
    [string]$Target = (Join-Path $env:USERPROFILE '.agents\skills\course-study-dsh'),
    [switch]$IncludeLocal
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { throw 'python was not found on PATH; install Python 3.10+ first' }

$cliArgs = @((Join-Path $root 'scripts\package_skill.py'), 'install', '--target', $Target)
if ($IncludeLocal) { $cliArgs += '--include-local' }

& $python.Source @cliArgs
if ($LASTEXITCODE -ne 0) { throw "package_skill.py install failed with exit code $LASTEXITCODE" }

Write-Host ''
Write-Host "installed: $Target" -ForegroundColor Green
Write-Host 'verify with:'
Write-Host "  python `"$Target\scripts\dsh_probe.py`" --name course-study-dsh"
Write-Host 'then restart the DeepSeek Harness session so the skill catalog refreshes.'
