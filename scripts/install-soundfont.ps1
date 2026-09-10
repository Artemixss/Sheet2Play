<#
.SYNOPSIS
    Installs the piano SoundFont the built-in synthesiser plays.

.DESCRIPTION
    The app renders its own audio with MeltySynth, which needs a SoundFont2 (.sf2) file.
    That file is tens to hundreds of megabytes of third-party samples, so it is fetched
    and hash-verified here rather than committed - the same treatment the OMR model
    weights get.

    It installs into %LOCALAPPDATA%\Sheet2Play\soundfonts by default, deliberately: the
    release script wipes dist\ on every publish, so a soundfont living beside the
    executable would have to be reinstalled each time. The app checks the per-user folder
    first for exactly this reason.

    Default is FreePats' YDP Grand Piano - real Yamaha Disklavier Pro samples, CC BY 3.0,
    36 MB compressed and 118 MB on disk. Any .sf2 works; the app globs the folder and
    takes the newest, so dropping in your own overrides this without touching settings.

.PARAMETER Destination
    Where to install. Defaults to %LOCALAPPDATA%\Sheet2Play\soundfonts.

.PARAMETER ToAppFolder
    Install beside the executable (Visualization_engine\assets\soundfonts) instead, so the
    published build carries it. Note this is wiped by scripts\verify-release.ps1.

.PARAMETER Force
    Re-download even when the file is already present and its hash matches.
#>
[CmdletBinding()]
param(
    [string]$Destination,
    [switch]$ToAppFolder,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

# Pinned so an upstream change cannot silently swap the samples. Verified 2026-09-09.
$sourceUrl = 'https://freepats.zenvoid.org/Piano/YDP-GrandPiano/YDP-GrandPiano-SF2-20160804.tar.bz2'
$archiveSha256 = 'd243dc3e182a60df2a16e92828c1821cf3eb5748b45e2e2bdcfa9cf7af056026'
$soundFontName = 'YDP-GrandPiano-20160804.sf2'
$licenseName = 'YDP-GrandPiano-20160804.txt'

$repositoryRoot = Split-Path -Parent $PSScriptRoot

if (-not $Destination) {
    if ($ToAppFolder) {
        $Destination = Join-Path $repositoryRoot 'Visualization_engine\assets\soundfonts'
    }
    else {
        $Destination = Join-Path $env:LOCALAPPDATA 'Sheet2Play\soundfonts'
    }
}

New-Item -ItemType Directory -Force -Path $Destination | Out-Null
$installedPath = Join-Path $Destination $soundFontName

if ((Test-Path -LiteralPath $installedPath) -and -not $Force) {
    $size = [math]::Round((Get-Item -LiteralPath $installedPath).Length / 1MB, 1)
    Write-Output "Already installed: $installedPath ($size MB)"
    Write-Output 'Pass -Force to reinstall.'
    exit 0
}

$staging = Join-Path ([System.IO.Path]::GetTempPath()) ("sheet2play-soundfont-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $staging | Out-Null

try {
    $archivePath = Join-Path $staging 'soundfont.tar.bz2'
    Write-Output "Downloading $sourceUrl"
    Write-Output '  (36 MB compressed, 118 MB installed)'
    # Progress rendering makes Invoke-WebRequest an order of magnitude slower on large files.
    $previousProgress = $ProgressPreference
    $ProgressPreference = 'SilentlyContinue'
    try {
        Invoke-WebRequest -Uri $sourceUrl -OutFile $archivePath -UseBasicParsing
    }
    finally {
        $ProgressPreference = $previousProgress
    }

    $actual = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $archiveSha256) {
        throw @"
Hash mismatch - refusing to install.
  expected $archiveSha256
  actual   $actual
Either the download was corrupted or upstream republished the file. Do not bypass this;
verify the source before updating the pinned hash in this script.
"@
    }
    Write-Output "SHA-256 verified: $actual"

    # tar has shipped with Windows since build 17063 and handles bzip2.
    & tar -xjf $archivePath -C $staging
    if ($LASTEXITCODE -ne 0) {
        throw "tar failed to extract the archive (exit code $LASTEXITCODE)."
    }

    $extracted = Get-ChildItem -Path $staging -Recurse -Filter '*.sf2' | Select-Object -First 1
    if (-not $extracted) {
        throw 'The archive contained no .sf2 file.'
    }
    Copy-Item -LiteralPath $extracted.FullName -Destination $installedPath -Force

    # The licence requires attribution, so it travels with the samples.
    $extractedLicense = Get-ChildItem -Path $staging -Recurse -Filter '*.txt' | Select-Object -First 1
    if ($extractedLicense) {
        Copy-Item -LiteralPath $extractedLicense.FullName -Destination (Join-Path $Destination $licenseName) -Force
    }

    $size = [math]::Round((Get-Item -LiteralPath $installedPath).Length / 1MB, 1)
    Write-Output ''
    Write-Output "Installed: $installedPath ($size MB)"
    Write-Output 'YDP Grand Piano (Yamaha Disklavier Pro), FreePats, CC BY 3.0.'
    Write-Output 'Start Sheet2Play and pick "Built-in synth" under AUDIO OUTPUT.'
}
finally {
    Remove-Item -Recurse -Force -LiteralPath $staging -ErrorAction SilentlyContinue
}
