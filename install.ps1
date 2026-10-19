# Install course-study-dsh into the DeepSeek Harness skill root.
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\install.ps1
#   powershell -ExecutionPolicy Bypass -File .\install.ps1 -Target C:\path\to\skills\course-study-dsh
#   powershell -ExecutionPolicy Bypass -File .\install.ps1 -Force    # reinstall, keep local/ data

param(
    [string]$Target = '',
    [switch]$Force,
    [switch]$IncludeLocal
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { throw 'python was not found on PATH; install Python 3.10+ first' }

$version = & $python.Source -c "import sys; print('%d.%d' % sys.version_info[:2])"
if ([version]$version -lt [version]'3.10') { throw "Python $version is too old; this skill needs 3.10+" }

if (-not $Target) {
    $Target = if ($env:DSH_AGENTS_HOME) {
        Join-Path $env:DSH_AGENTS_HOME 'skills\course-study-dsh'
    } else {
        Join-Path $env:USERPROFILE '.agents\skills\course-study-dsh'
    }
}

$cliArgs = @((Join-Path $root 'scripts\package_skill.py'), 'install', '--target', $Target)
if ($IncludeLocal) { $cliArgs += '--include-local' }
if ($Force) { $cliArgs += '--force' }

& $python.Source @cliArgs
if ($LASTEXITCODE -ne 0) { throw "package_skill.py install failed with exit code $LASTEXITCODE" }

Write-Host ''
Write-Host "installed: $Target" -ForegroundColor Green
$configPath = Join-Path $Target 'local\private.toml'
if (Test-Path $configPath) {
    $configText = Get-Content $configPath -Raw
    $mode = if ($configText -match '(?m)^\s*mode\s*=\s*"([^"]+)"') { $Matches[1] } else { '?' }
    $submit = if ($configText -match '(?m)^\s*submit\s*=\s*(true|false)') { $Matches[1] } else { '?' }
    Write-Host "config:    $configPath (mode=$mode, submit=$submit)"
} else {
    Write-Host "config:    $configPath (missing; public default evidence/no-submit)"
}
Write-Host 'verify with (run from the source repo; needs a tools.json):'
Write-Host "  python `"$PSScriptRoot\scripts\dsh_probe.py`" --tools tools.json --require-discovered"
Write-Host 'then restart the DeepSeek Harness session so the skill catalog refreshes.'
