<#
.SYNOPSIS
    The definition of done for Sheet2Play: publish, then prove the published app works.

.DESCRIPTION
    Building is not shipping. The app the user launches is dist\Sheet2Play.exe, and a
    change that only exists in bin\Release has not reached them. This script closes that
    gap end to end:

      1. stops a running Sheet2Play so the exe is not locked
      2. runs the xunit suite and aborts if anything fails
      3. wipes dist\ and republishes into it, so nothing stale survives
      4. checks the published folder against a manifest generated from the source tree
      5. launches the published exe, waits for its window, screenshots it, and closes it

    Step 4 matters most. Fonts and the Python bridge load from disk at runtime, so a
    missing one compiles clean and either degrades silently or fails only when the user
    hits that feature. The manifest is derived from the csproj Content rules and
    cross-checked against filenames referenced in the C# sources, so adding an asset
    cannot silently escape the check the way a hardcoded list would.

    Exits 0 only if every step passes. Any failure exits 1 with a per-step summary.

.PARAMETER OutputPath
    Where to publish. Defaults to .\dist - the path the shortcuts point at.

.PARAMETER SkipTests
    Skip the test suite. For iterating on packaging only; never for a real release.

.PARAMETER NoLaunch
    Publish and check the manifest but do not launch the app. Use on a machine with no
    interactive desktop session.

.PARAMETER LaunchSeconds
    How long to wait for the app window to appear before calling it a failure.
#>
[CmdletBinding()]
param(
    [string]$OutputPath,
    [switch]$SkipTests,
    [switch]$NoLaunch,
    [int]$LaunchSeconds = 20
)

$ErrorActionPreference = 'Stop'

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptRoot '..')).Path
if (-not $OutputPath) { $OutputPath = Join-Path $repoRoot 'dist' }

$projectDir = Join-Path $repoRoot 'Visualization_engine'
$project = Join-Path $projectDir 'SynthesiaClone.csproj'
$testProject = Join-Path $repoRoot 'Visualization_engine.Tests\Visualization_engine.Tests.csproj'
$exe = Join-Path $OutputPath 'Sheet2Play.exe'
$evidenceDir = Join-Path $OutputPath '_verify'

$steps = [System.Collections.Generic.List[object]]::new()
function Add-Step {
    param([string]$Name, [bool]$Passed, [string]$Detail = '')
    $steps.Add([pscustomobject]@{ Name = $Name; Passed = $Passed; Detail = $Detail })
    $tag = if ($Passed) { 'PASS' } else { 'FAIL' }
    $color = if ($Passed) { 'Green' } else { 'Red' }
    Write-Host ("[{0}] {1}" -f $tag, $Name) -ForegroundColor $color
    if ($Detail) { Write-Host ("       " + ($Detail -replace "`n", "`n       ")) -ForegroundColor DarkGray }
}

function Stop-Verification {
    param([string]$Because)
    Write-Host ""
    Write-Host "Stopped early: $Because" -ForegroundColor Red
    Write-Summary
    exit 1
}

function Write-Summary {
    Write-Host ""
    Write-Host "--- verify-release summary ---" -ForegroundColor Cyan
    foreach ($s in $steps) {
        $tag = if ($s.Passed) { 'PASS' } else { 'FAIL' }
        $color = if ($s.Passed) { 'Green' } else { 'Red' }
        Write-Host ("  {0}  {1}" -f $tag, $s.Name) -ForegroundColor $color
    }
}

Write-Host "Verifying Sheet2Play release into $OutputPath" -ForegroundColor Cyan
Write-Host ""

# --- 1. release the file lock -------------------------------------------------
# A running app pins Sheet2Play.exe and makes publish fail with a confusing IO error.
# Closing it loses nothing: the song library and settings live in %LOCALAPPDATA%\Sheet2Play.
$running = @(Get-Process -Name 'Sheet2Play' -ErrorAction SilentlyContinue)
if ($running.Count -gt 0) {
    Write-Host "Sheet2Play is running (PID $($running.Id -join ', ')). Closing it so the exe can be replaced." -ForegroundColor Yellow
    Write-Host "Your library and settings are in %LOCALAPPDATA%\Sheet2Play and are not affected." -ForegroundColor DarkGray
    $running | Stop-Process -Force
    Start-Sleep -Milliseconds 800
}
Add-Step 'App not holding a lock on the exe' $true

# --- 2. tests -----------------------------------------------------------------
if ($SkipTests) {
    Add-Step 'Test suite' $true '-SkipTests was passed; the suite did NOT run.'
} else {
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $testOutput = & dotnet test $testProject --nologo --verbosity quiet 2>&1
    $testCode = $LASTEXITCODE
    $ErrorActionPreference = $prev

    $summary = ($testOutput | ForEach-Object { $_.ToString() } |
        Where-Object { $_ -match 'Passed!|Failed!|error|Test summary|failed' } |
        Select-Object -Last 8) -join "`n"

    if ($testCode -ne 0) {
        Add-Step 'Test suite' $false $summary
        Stop-Verification 'tests failed'
    }
    Add-Step 'Test suite' $true $summary
}

# --- 3. clean publish ---------------------------------------------------------
# Republishing over a dirty dist can leave a deleted asset behind and hide a packaging
# regression, so the folder is emptied first. Everything in it is regenerable output.
if (Test-Path $OutputPath) {
    $existing = @(Get-ChildItem -LiteralPath $OutputPath -Force)
    Write-Host "Clearing $($existing.Count) item(s) from $OutputPath before publishing." -ForegroundColor DarkGray
    Remove-Item -LiteralPath (Join-Path $OutputPath '*') -Recurse -Force -ErrorAction Stop
}

$publishScript = Join-Path $scriptRoot 'publish.ps1'
$prev = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
$publishOutput = & $publishScript -OutputPath $OutputPath 2>&1
$publishCode = $LASTEXITCODE
$ErrorActionPreference = $prev

if (-not (Test-Path $exe)) {
    Add-Step 'Clean publish' $false (($publishOutput | ForEach-Object { $_.ToString() } | Select-Object -Last 15) -join "`n")
    Stop-Verification 'publish did not produce Sheet2Play.exe'
}
$sizeMb = [math]::Round((Get-Item $exe).Length / 1MB, 1)
Add-Step 'Clean publish' $true "$exe ($sizeMb MB)"

# --- 4. asset manifest --------------------------------------------------------
# Generated from the csproj Content rules rather than hardcoded, so an asset added to the
# project is covered automatically.
function Get-ExpectedContent {
    param([string]$CsprojPath, [string]$ProjectDir)

    [xml]$xml = Get-Content -LiteralPath $CsprojPath -Raw
    $expected = [System.Collections.Generic.List[string]]::new()

    foreach ($item in $xml.Project.ItemGroup.Content) {
        if (-not $item -or -not $item.Include) { continue }
        if ($item.CopyToPublishDirectory -eq 'Never') { continue }

        $include = $item.Include
        $link = $item.Link

        # Split the glob at the recursive wildcard so %(RecursiveDir) can be recovered.
        $recursive = $include -match '\*\*'
        $basePattern = $include -replace '\*\*[\\/]?', ''
        $baseDir = Join-Path $ProjectDir (Split-Path $basePattern -Parent)
        $leaf = Split-Path $basePattern -Leaf
        if ([string]::IsNullOrWhiteSpace($leaf)) { $leaf = '*' }
        if (-not (Test-Path $baseDir)) { continue }
        $baseFull = (Resolve-Path $baseDir).Path

        $files = Get-ChildItem -LiteralPath $baseFull -Filter $leaf -File -Recurse:$recursive -ErrorAction SilentlyContinue
        foreach ($f in $files) {
            if ($f.FullName -match '\\__pycache__\\') { continue }

            if ($link) {
                $recursiveDir = ''
                if ($recursive) {
                    $rel = $f.DirectoryName.Substring($baseFull.Length).TrimStart('\')
                    if ($rel) { $recursiveDir = "$rel\" }
                }
                $target = $link `
                    -replace '%\(RecursiveDir\)', $recursiveDir `
                    -replace '%\(Filename\)', $f.BaseName `
                    -replace '%\(Extension\)', $f.Extension
            } else {
                $target = $f.Name
            }
            $expected.Add($target.Replace('/', '\')) | Out-Null
        }
    }
    return $expected | Sort-Object -Unique
}

$expected = Get-ExpectedContent -CsprojPath $project -ProjectDir $projectDir
$missing = @()
foreach ($rel in $expected) {
    if (-not (Test-Path (Join-Path $OutputPath $rel))) { $missing += $rel }
}

if ($expected.Count -eq 0) {
    Add-Step 'Asset manifest (from csproj)' $false 'Derived an empty manifest - the csproj parser needs fixing, this check is not meaningful.'
} elseif ($missing.Count -gt 0) {
    Add-Step 'Asset manifest (from csproj)' $false ("Missing from the published folder:`n  " + ($missing -join "`n  "))
} else {
    Add-Step 'Asset manifest (from csproj)' $true "All $($expected.Count) declared content file(s) present."
}

# Cross-check: a runtime asset referenced in C# but never declared as Content would pass
# the check above, because the manifest and the gap share a cause.
$referenced = [System.Collections.Generic.List[string]]::new()
foreach ($cs in Get-ChildItem -LiteralPath $projectDir -Filter *.cs -Recurse -File) {
    foreach ($m in [regex]::Matches((Get-Content -LiteralPath $cs.FullName -Raw), '"([A-Za-z0-9_\-.]+\.(?:ttf|otf|py|ico|ps1))"')) {
        $referenced.Add($m.Groups[1].Value) | Out-Null
    }
}
$referenced = $referenced | Sort-Object -Unique
$published = @(Get-ChildItem -LiteralPath $OutputPath -Recurse -File | Select-Object -ExpandProperty Name)
$unshipped = @($referenced | Where-Object { $published -notcontains $_ })

if ($unshipped.Count -gt 0) {
    Add-Step 'Runtime assets referenced in C# are shipped' $false ("Referenced in source but absent from the published folder:`n  " + ($unshipped -join "`n  "))
} else {
    Add-Step 'Runtime assets referenced in C# are shipped' $true "All $($referenced.Count) referenced asset filename(s) present."
}

# --- 5. launch the published exe ---------------------------------------------
if ($NoLaunch) {
    Add-Step 'Published app launches' $true '-NoLaunch was passed; the app was NOT started.'
} else {
    New-Item -ItemType Directory -Force $evidenceDir | Out-Null
    $stdout = Join-Path $evidenceDir 'stdout.log'
    $stderr = Join-Path $evidenceDir 'stderr.log'
    $shot = Join-Path $evidenceDir 'launch.png'

    $proc = Start-Process -FilePath $exe -WorkingDirectory $OutputPath -PassThru `
        -RedirectStandardOutput $stdout -RedirectStandardError $stderr

    $deadline = (Get-Date).AddSeconds($LaunchSeconds)
    $handle = [IntPtr]::Zero
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 500
        if ($proc.HasExited) { break }
        $proc.Refresh()
        if ($proc.MainWindowHandle -ne [IntPtr]::Zero) {
            $handle = $proc.MainWindowHandle
            break
        }
    }

    if ($proc.HasExited) {
        $tail = ''
        foreach ($log in @($stderr, $stdout)) {
            if ((Test-Path $log) -and (Get-Item $log).Length -gt 0) {
                $tail += "`n$(Split-Path $log -Leaf):`n" + ((Get-Content $log -Tail 20) -join "`n")
            }
        }
        Add-Step 'Published app launches' $false "Exited with code $($proc.ExitCode) before showing a window.$tail"
    } elseif ($handle -eq [IntPtr]::Zero) {
        $proc | Stop-Process -Force
        Add-Step 'Published app launches' $false "Still running after $LaunchSeconds s but never showed a window."
    } else {
        # Give the first frame time to render before grabbing the screen.
        Start-Sleep -Seconds 2

        # CopyFromScreen grabs whatever pixels sit at those coordinates, not the window
        # itself. Windows refuses SetForegroundWindow to a process that is not already in
        # the foreground, so a naive capture happily returns a screenshot of whatever the
        # user had on top and the step passes on evidence of the wrong window. Raise the
        # window properly, then confirm it really is the one on screen before believing
        # the image.
        if (-not ([System.Management.Automation.PSTypeName]'S2P.Cap').Type) {
            Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
namespace S2P {
  public struct RECT { public int Left, Top, Right, Bottom; }
  public struct POINT { public int X, Y; }
  public static class Cap {
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr h);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int n);
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] public static extern IntPtr WindowFromPoint(POINT p);
    [DllImport("user32.dll")] public static extern IntPtr GetAncestor(IntPtr h, uint f);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, IntPtr pid);
    [DllImport("user32.dll")] public static extern bool AttachThreadInput(uint a, uint b, bool attach);
    [DllImport("kernel32.dll")] public static extern uint GetCurrentThreadId();
    [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint flags);

    static readonly IntPtr HWND_TOPMOST = new IntPtr(-1);
    static readonly IntPtr HWND_NOTOPMOST = new IntPtr(-2);
    const uint SWP_NOMOVE = 0x0002, SWP_NOSIZE = 0x0001, SWP_SHOWWINDOW = 0x0040, SWP_NOACTIVATE = 0x0010;

    // Windows refuses SetForegroundWindow to a process that is not already in the
    // foreground, and this script runs from a background shell. Marking the window
    // topmost raises it above everything else without needing foreground rights, which
    // is all a screenshot requires. The foreground attempt is kept as a best effort.
    public static void Raise(IntPtr h) {
      ShowWindow(h, 5);
      SetWindowPos(h, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW | SWP_NOACTIVATE);
      BringWindowToTop(h);
      uint us = GetCurrentThreadId();
      uint them = GetWindowThreadProcessId(GetForegroundWindow(), IntPtr.Zero);
      if (us != them) AttachThreadInput(us, them, true);
      SetForegroundWindow(h);
      if (us != them) AttachThreadInput(us, them, false);
    }

    public static void Unraise(IntPtr h) {
      SetWindowPos(h, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE);
    }

    // True when the window actually owning the pixels at this point is our window.
    public static bool OwnsPoint(IntPtr h, int x, int y) {
      POINT p; p.X = x; p.Y = y;
      IntPtr top = WindowFromPoint(p);
      if (top == IntPtr.Zero) return false;
      return GetAncestor(top, 2) == h;   // GA_ROOT
    }
  }
}
'@
        }
        Add-Type -AssemblyName System.Drawing

        $rect = New-Object S2P.RECT
        $captured = $false
        $captureNote = 'no window rect'
        $occluded = @()

        if ([S2P.Cap]::GetWindowRect($handle, [ref]$rect)) {
            $w = $rect.Right - $rect.Left
            $h = $rect.Bottom - $rect.Top
            if ($w -gt 0 -and $h -gt 0) {
                # Sample the centre and the four quarter points; if another window owns
                # any of them the capture would be of that window, not ours.
                $points = @(
                    @(0.5, 0.5), @(0.25, 0.25), @(0.75, 0.25), @(0.25, 0.75), @(0.75, 0.75)
                )
                for ($attempt = 1; $attempt -le 3; $attempt++) {
                    [S2P.Cap]::Raise($handle)
                    Start-Sleep -Milliseconds 900
                    $occluded = @($points | Where-Object {
                        -not [S2P.Cap]::OwnsPoint($handle,
                            [int]($rect.Left + $w * $_[0]),
                            [int]($rect.Top + $h * $_[1]))
                    })
                    if ($occluded.Count -eq 0) { break }
                }

                if ($occluded.Count -gt 0) {
                    $fg = [S2P.Cap]::GetForegroundWindow()
                    $captureNote = "the Sheet2Play window could not be brought to the front ($($occluded.Count)/5 sample points are covered by another window, foreground handle $fg). A screenshot here would show the wrong window, so none was taken."
                } else {
                    $bmp = New-Object System.Drawing.Bitmap $w, $h
                    $g = [System.Drawing.Graphics]::FromImage($bmp)
                    $g.CopyFromScreen($rect.Left, $rect.Top, 0, 0, (New-Object System.Drawing.Size $w, $h))
                    $g.Dispose()

                    # A uniform image means the window never rendered a frame.
                    $probe = @(
                        $bmp.GetPixel([int]($w * 0.1), [int]($h * 0.1)),
                        $bmp.GetPixel([int]($w * 0.5), [int]($h * 0.5)),
                        $bmp.GetPixel([int]($w * 0.9), [int]($h * 0.9)),
                        $bmp.GetPixel([int]($w * 0.5), [int]($h * 0.15))
                    )
                    $distinct = ($probe | ForEach-Object { $_.ToArgb() } | Sort-Object -Unique).Count

                    if ($distinct -le 1) {
                        $captureNote = 'the window is a single flat colour - it never rendered a frame.'
                        $bmp.Save($shot, [System.Drawing.Imaging.ImageFormat]::Png)
                    } else {
                        $bmp.Save($shot, [System.Drawing.Imaging.ImageFormat]::Png)
                        $captured = $true
                    }
                    $bmp.Dispose()
                }
            }
        }

        [S2P.Cap]::Unraise($handle)

        $proc.Refresh()
        $stillUp = -not $proc.HasExited
        if ($stillUp) { $proc | Stop-Process -Force }

        if (-not $stillUp) {
            Add-Step 'Published app launches' $false "Window appeared but the app exited during capture (code $($proc.ExitCode))."
        } elseif (-not $captured) {
            # No trustworthy image means no evidence, and no evidence is a failure.
            Add-Step 'Published app launches' $false "The app started and kept its window open, but visual evidence could not be captured: $captureNote"
        } else {
            Add-Step 'Published app launches' $true "Window appeared, rendered, and survived the wait. Screenshot: $shot"
        }
    }
}

# --- report -------------------------------------------------------------------
Write-Summary
$failed = @($steps | Where-Object { -not $_.Passed })
Write-Host ""
if ($failed.Count -gt 0) {
    Write-Host "verify-release FAILED ($($failed.Count) of $($steps.Count) step(s))." -ForegroundColor Red
    Write-Host "The published app is not ready. Do not report this change as done." -ForegroundColor Red
    exit 1
}
Write-Host "verify-release PASSED. Verified artifact: $exe" -ForegroundColor Green
Write-Host "Relaunch with the Desktop shortcut, or: $exe" -ForegroundColor DarkGray
exit 0
