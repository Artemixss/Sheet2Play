<#
.SYNOPSIS
    Creates Desktop and Start Menu shortcuts for a published Sheet2Play.exe.

.PARAMETER ExePath
    Path to Sheet2Play.exe. Defaults to .\dist\Sheet2Play.exe.

.PARAMETER LibraryHome
    Optional value for SHEET2PLAY_HOME, baked into the shortcut. Only needed to point
    this shortcut at a different library; by default both source and published builds
    use %APPDATA%\Sheet2Play.

.PARAMETER StartMenuOnly
    Skip the Desktop shortcut.
#>
[CmdletBinding()]
param(
    [string]$ExePath,
    [string]$LibraryHome,
    [switch]$StartMenuOnly
)

$ErrorActionPreference = 'Stop'
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $ExePath) { $ExePath = Join-Path $scriptRoot '..\dist\Sheet2Play.exe' }

if (-not (Test-Path $ExePath)) {
    throw "Not found: $ExePath. Run .\scripts\publish.ps1 first."
}
$ExePath = (Resolve-Path $ExePath).Path
$workingDir = Split-Path $ExePath -Parent

# A .lnk cannot carry environment variables, so when a custom home is requested the
# shortcut launches cmd, which sets the variable and then starts the app.
$targets = @()
if (-not $StartMenuOnly) {
    $targets += Join-Path ([Environment]::GetFolderPath('Desktop')) 'Sheet2Play.lnk'
}
$targets += Join-Path ([Environment]::GetFolderPath('StartMenu')) 'Programs\Sheet2Play.lnk'

$shell = New-Object -ComObject WScript.Shell
foreach ($linkPath in $targets) {
    $parent = Split-Path $linkPath -Parent
    if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }

    $shortcut = $shell.CreateShortcut($linkPath)
    if ($LibraryHome) {
        $shortcut.TargetPath = "$env:ComSpec"
        $shortcut.Arguments = "/c set SHEET2PLAY_HOME=$LibraryHome&& start `"`" `"$ExePath`""
        $shortcut.IconLocation = "$ExePath,0"
    } else {
        $shortcut.TargetPath = $ExePath
        $shortcut.IconLocation = "$ExePath,0"
    }
    $shortcut.WorkingDirectory = $workingDir
    $shortcut.Description = 'Turn sheet music into synchronized piano playback'
    $shortcut.Save()

    Write-Host "Created $linkPath" -ForegroundColor Green
}

if ($LibraryHome) {
    Write-Host "Shortcuts set SHEET2PLAY_HOME=$LibraryHome" -ForegroundColor DarkGray
} else {
    Write-Host "Library location: $env:APPDATA\Sheet2Play" -ForegroundColor DarkGray
}
