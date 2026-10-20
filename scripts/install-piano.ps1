<#
.SYNOPSIS
    Installs the Salamander Grand Piano for the built-in SFZ piano (PIANO > Salamander).

.DESCRIPTION
    Salamander Grand Piano V3 (Yamaha C5, 48 kHz/24-bit, CC BY 3.0 by Alexander Holm) is 1.9 GB of
    third-party samples, so it is fetched and hash-verified here rather than committed - the same
    treatment install-soundfont.ps1 gives the YDP SoundFont.

    The samples are then converted once into a single 16-bit bank (about 1.3 GB) that the app maps
    into memory, by the published app itself (Sheet2Play.exe --build-piano-bank). Only the bank, the
    instrument (.sfz), the README with the licence, and piano.json are kept; the original samples are
    not needed after conversion.

    It installs into %LOCALAPPDATA%\Sheet2Play\pianos by default (SHEET2PLAY_HOME\pianos when that is
    set), deliberately outside dist\, which every publish wipes.

    The pin is a hash of the extracted files rather than of the archive, so an existing copy of the
    same release (-Source with a folder) verifies exactly like a fresh download.

.PARAMETER Source
    A folder holding an extracted SalamanderGrandPianoV3_48khz24bit release, or the downloaded
    .tar.xz. Without it, the archive is downloaded from FreePats (1.26 GB).

.PARAMETER Destination
    Where to install. Defaults to %LOCALAPPDATA%\Sheet2Play\pianos\salamander-v3.

.PARAMETER App
    The Sheet2Play.exe that builds the bank. Defaults to the published dist\Sheet2Play.exe.

.PARAMETER Force
    Reinstall even when the piano is already installed.
#>
[CmdletBinding()]
param(
    [string]$Source,
    [string]$Destination,
    [string]$App,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

# Pinned so an upstream change cannot silently swap the samples. The hash covers every file of the
# release (README, both .sfz files and the 641 samples); see Get-TreeHash. Verified 2026-10-20
# against the copy the Phase 4a spike measured.
$sourceUrl = 'https://freepats.zenvoid.org/Piano/SalamanderGrandPiano/SalamanderGrandPianoV3+20161209_48khz24bit.tar.xz'
$treeSha256 = '696d8ac68492f27fde8edacc79cd786d18bf1437fafc9452d6545d1f5949c72d'
$releaseFolder = 'SalamanderGrandPianoV3_48khz24bit'
$instrumentName = 'SalamanderGrandPianoV3.sfz'

$repositoryRoot = Split-Path -Parent $PSScriptRoot

function Get-TreeHash([string]$root) {
    # One line per file, "relative/path sha256", sorted ordinally, hashed as UTF-8.
    $rootPath = (Resolve-Path -LiteralPath $root).Path.TrimEnd('\')
    $lines = Get-ChildItem -LiteralPath $rootPath -Recurse -File |
        ForEach-Object {
            $relative = $_.FullName.Substring($rootPath.Length + 1).Replace('\', '/')
            $hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
            "$relative $hash"
        }
    $sorted = [System.Collections.Generic.List[string]]::new([string[]]$lines)
    $sorted.Sort([System.StringComparer]::Ordinal)
    $bytes = [System.Text.Encoding]::UTF8.GetBytes(($sorted -join "`n") + "`n")
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        return ([System.BitConverter]::ToString($sha.ComputeHash($bytes)) -replace '-', '').ToLowerInvariant()
    }
    finally {
        $sha.Dispose()
    }
}

if (-not $Destination) {
    $appHome = if ($env:SHEET2PLAY_HOME) {
        [Environment]::ExpandEnvironmentVariables($env:SHEET2PLAY_HOME.Trim())
    }
    else {
        Join-Path $env:LOCALAPPDATA 'Sheet2Play'
    }
    $Destination = Join-Path $appHome 'pianos\salamander-v3'
}
if (-not $App) {
    $App = Join-Path $repositoryRoot 'dist\Sheet2Play.exe'
}

$installed = @('piano.json', 'index.json', 'bank.s16', $instrumentName) |
    ForEach-Object { Test-Path -LiteralPath (Join-Path $Destination $_) }
if (($installed -notcontains $false) -and -not $Force) {
    $size = [math]::Round((Get-Item -LiteralPath (Join-Path $Destination 'bank.s16')).Length / 1MB)
    Write-Output "Already installed: $Destination ($size MB bank)"
    Write-Output 'Pass -Force to reinstall.'
    exit 0
}
if (-not (Test-Path -LiteralPath $App)) {
    throw "The bank is built by the published app, and $App does not exist. Publish it first (scripts\publish.ps1), or pass -App."
}

$staging = Join-Path ([System.IO.Path]::GetTempPath()) ("sheet2play-piano-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $staging | Out-Null

try {
    if ($Source -and (Test-Path -LiteralPath $Source -PathType Container)) {
        $release = (Resolve-Path -LiteralPath $Source).Path
    }
    else {
        if ($Source) {
            $archivePath = (Resolve-Path -LiteralPath $Source).Path
        }
        else {
            $archivePath = Join-Path $staging 'salamander.tar.xz'
            Write-Output "Downloading $sourceUrl"
            Write-Output '  (1.26 GB compressed, 1.9 GB extracted, 1.3 GB installed)'
            # Progress rendering makes Invoke-WebRequest an order of magnitude slower on large files.
            $previousProgress = $ProgressPreference
            $ProgressPreference = 'SilentlyContinue'
            try {
                Invoke-WebRequest -Uri $sourceUrl -OutFile $archivePath -UseBasicParsing
            }
            finally {
                $ProgressPreference = $previousProgress
            }
        }
        Write-Output 'Extracting...'
        # tar has shipped with Windows since build 17063; .xz needs a build whose libarchive has liblzma.
        & tar -xJf $archivePath -C $staging
        if ($LASTEXITCODE -ne 0) {
            throw "tar failed to extract the archive (exit code $LASTEXITCODE). If it cannot read .xz, extract it with 7-Zip and pass the folder as -Source."
        }
        $release = Join-Path $staging $releaseFolder
        if (-not (Test-Path -LiteralPath $release)) {
            throw "The archive did not contain $releaseFolder."
        }
    }

    Write-Output 'Verifying the samples (1.9 GB)...'
    $actual = Get-TreeHash $release
    if ($actual -ne $treeSha256) {
        throw @"
Hash mismatch - refusing to install.
  expected $treeSha256
  actual   $actual
Either the files are not the SalamanderGrandPianoV3+20161209 48 kHz/24-bit release, or a file
was changed or is missing. Do not bypass this; verify the source before updating the pinned hash.
"@
    }
    Write-Output "SHA-256 verified: $actual"

    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    Copy-Item -LiteralPath (Join-Path $release $instrumentName) -Destination $Destination -Force
    # The licence requires attribution, so it travels with the samples.
    Copy-Item -LiteralPath (Join-Path $release 'README') -Destination (Join-Path $Destination 'README.txt') -Force

    Write-Output 'Building the sample bank...'
    & $App --build-piano-bank (Join-Path $release $instrumentName) $Destination
    if ($LASTEXITCODE -ne 0) {
        throw "Building the bank failed (exit code $LASTEXITCODE)."
    }

    # Written last: the app only offers a piano whose piano.json exists.
    $description = [ordered]@{
        name        = 'Salamander Grand Piano V3'
        short_name  = 'Salamander'
        sfz         = $instrumentName
        attribution = 'Salamander Grand Piano V3 by Alexander Holm, CC BY 3.0'
    }
    $description | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Destination 'piano.json') -Encoding utf8

    $size = [math]::Round((Get-Item -LiteralPath (Join-Path $Destination 'bank.s16')).Length / 1MB)
    Write-Output ''
    Write-Output "Installed: $Destination ($size MB bank)"
    Write-Output 'Salamander Grand Piano V3 (Yamaha C5) by Alexander Holm, CC BY 3.0.'
    Write-Output 'Start Sheet2Play and pick "Salamander" under PIANO.'
}
finally {
    Remove-Item -Recurse -Force -LiteralPath $staging -ErrorAction SilentlyContinue
}
