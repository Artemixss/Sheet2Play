<#
.SYNOPSIS
    Publishes Sheet2Play as a single self-contained Sheet2Play.exe.

.DESCRIPTION
    Produces one double-clickable executable that needs no .NET install. Fonts and the
    Python bridge are copied beside it by the csproj <Content> rules.

    A published build cannot find SynthesiaClone.csproj, so it stores songs and caches in
    %APPDATA%\Sheet2Play instead of beside the .exe. This script seeds that folder from
    the repo's songs/ directory on first publish, since only the build machine knows
    where the development library lives.

.PARAMETER OutputPath
    Where to place the published app. Defaults to .\dist.

.PARAMETER SkipLibrarySeed
    Do not copy songs/ into %APPDATA%\Sheet2Play.
#>
[CmdletBinding()]
param(
    [string]$OutputPath,
    [switch]$SkipLibrarySeed
)

$ErrorActionPreference = 'Stop'
# $PSScriptRoot is not reliably populated in param defaults, so resolve paths here.
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptRoot '..')).Path
if (-not $OutputPath) { $OutputPath = Join-Path $repoRoot 'dist' }
$project = Join-Path $repoRoot 'Visualization_engine\SynthesiaClone.csproj'

Write-Host "Publishing Sheet2Play..." -ForegroundColor Cyan

# IncludeNativeLibrariesForSelfExtract is required: Raylib ships native DLLs that will
# not load from inside a single-file bundle without it.
dotnet publish $project `
    -c Release `
    -r win-x64 `
    --self-contained true `
    -p:PublishSingleFile=true `
    -p:IncludeNativeLibrariesForSelfExtract=true `
    -o $OutputPath

if ($LASTEXITCODE -ne 0) { throw "dotnet publish failed with exit code $LASTEXITCODE" }

$exe = Join-Path $OutputPath 'Sheet2Play.exe'
if (-not (Test-Path $exe)) { throw "Publish finished but $exe is missing." }

# Sanity-check the parts that only fail at runtime, not at build time.
foreach ($required in @('assets\fonts\Inter-Regular.ttf', 'Bridge\bridge.py')) {
    $path = Join-Path $OutputPath $required
    if (Test-Path $path) {
        Write-Host "  ok  $required" -ForegroundColor DarkGray
    } else {
        Write-Warning "  MISSING  $required - the published app will fall back or fail at runtime."
    }
}

if (-not $SkipLibrarySeed) {
    $libraryHome = Join-Path $env:APPDATA 'Sheet2Play'
    $songsSource = Join-Path $repoRoot 'Visualization_engine\songs'
    $songsTarget = Join-Path $libraryHome 'songs'
    if ((Test-Path $songsSource) -and -not (Test-Path $songsTarget)) {
        Write-Host "Seeding library into $songsTarget ..." -ForegroundColor Cyan
        New-Item -ItemType Directory -Force -Path $libraryHome | Out-Null
        Copy-Item -Recurse -Force -Path $songsSource -Destination $songsTarget
        Write-Host "  copied songs/ (first publish only)" -ForegroundColor DarkGray
    } else {
        Write-Host "Library already present at $songsTarget - left untouched." -ForegroundColor DarkGray
    }
}

$sizeMb = [math]::Round((Get-Item $exe).Length / 1MB, 1)
Write-Host ""
Write-Host "Published: $exe ($sizeMb MB)" -ForegroundColor Green
Write-Host "Create a shortcut with: .\scripts\install-shortcut.ps1" -ForegroundColor DarkGray
