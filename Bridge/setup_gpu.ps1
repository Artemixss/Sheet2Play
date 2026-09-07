[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$bridgeDirectory = Split-Path -Parent $PSCommandPath
$environmentDirectory = Join-Path $bridgeDirectory ".venv-homr-gpu"
$pythonExecutable = Join-Path $environmentDirectory "Scripts\python.exe"
$gpuLauncher = Join-Path $bridgeDirectory "homr_gpu.py"
$uvCommand = Get-Command "uv" -ErrorAction Stop

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Executable,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,

        # For steps whose failure is expected and harmless, such as uninstalling a package
        # that a fresh environment never had.
        [switch]$AllowFailure
    )

    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0 -and -not $AllowFailure) {
        throw "Command failed with exit code ${LASTEXITCODE}: $Executable $($Arguments -join ' ')"
    }
}

if (-not (Test-Path -LiteralPath $pythonExecutable -PathType Leaf)) {
    Invoke-CheckedCommand -Executable $uvCommand.Source -Arguments @(
        "venv",
        $environmentDirectory,
        "--python",
        "3.11"
    )
}

Invoke-CheckedCommand -Executable $uvCommand.Source -Arguments @(
    "pip",
    "install",
    "--python",
    $pythonExecutable,
    "homr @ git+https://github.com/liebharc/homr.git@457e7c6518a10ba755db2e60883419e56c4d7369",
    "pymupdf==1.26.3",
    "music21==10.5.0"
)

# Installed from git rather than PyPI, pinned to an exact commit. The 0.7.0 release predates
# aa5c8ce, which fixes a crash where a rest merged into a chord produces a zero-duration
# element and homr exits non-zero (upstream issue #136). Upstream releases infrequently and
# has not packaged it. Measured against 0.7.0 on the 100-sample OLiMPiC canary: onset F1
# 0.579 -> 0.585, timeline-too-long 53% -> 47%, pitch F1 unchanged within noise.
#
# Moved from 2d0c0a6 to 457e7c6 for 5a5a8ee (upstream PR #141), which recovers ties from
# same-pitch slurs. homr has no tie token and deliberately trains slurs and ties as one
# class, so that is how a tie is read back out at all - and without one, an onset falling
# inside a sustained note cannot be placed. Upstream measures its recall at 0.93-1.00 on
# engraved input against 0.04-0.12 on scans, which suits this app's PDF library.

# Upstream PR #146, which its author closed after concluding the problem was harder than
# expected and seeing no movement in homr's OMR-NED benchmark. OMR-NED does not measure
# onset placement. Scored on onsets it is the largest single win available: on the OLiMPiC
# canary onset F1 0.583 -> 0.661 and scores running long 52% -> 34%, and on this app's own
# library 0.214 -> 0.294. It replays each staff on its own cursor and shrinks measures that
# overflow the expected duration.
#
# Applied as a patch because it exists only as a closed pull request, so there is no commit
# to pin. It regresses 18 of 100 canary systems, all already correct beforehand; the cause
# is recorded in Research/omr/reports/diagnosis/FINDINGS.md and is not the measure-length
# estimator, which was tested and ruled out.
$patchFile = Join-Path $PSScriptRoot "patches/homr-pr146-retiming.patch"
$homrRoot = & $pythonExecutable -c "import homr, pathlib; print(pathlib.Path(homr.__file__).parent.parent)"
if (-not (Test-Path $patchFile)) { throw "Missing $patchFile" }
Invoke-CheckedCommand -Executable "git" -Arguments @(
    "apply", "--check", "--unsafe-paths", "-p1", "--directory=$homrRoot", $patchFile
) -AllowFailure
if ($LASTEXITCODE -eq 0) {
    Invoke-CheckedCommand -Executable "git" -Arguments @(
        "apply", "--unsafe-paths", "-p1", "--directory=$homrRoot", $patchFile
    )
    Write-Host "Applied homr re-timing patch (upstream PR #146)"
} else {
    Write-Host "homr re-timing patch already applied, or does not apply - check manually"
}

# Exactly one OpenCV distribution may be installed. homr declares
# opencv-python-headless <5, but the transitive graph can also pull opencv-python 5.x, and
# with both present the two overwrite each other's files - cv2 then imports but is missing
# attributes, and every homr run dies with 'module cv2 has no attribute
# gapi_wip_gst_GStreamerPipeline'. Remove the CPU distribution before pinning headless.
Invoke-CheckedCommand -Executable $uvCommand.Source -Arguments @(
    "pip",
    "uninstall",
    "--python",
    $pythonExecutable,
    "opencv-python"
) -AllowFailure

Invoke-CheckedCommand -Executable $uvCommand.Source -Arguments @(
    "pip",
    "install",
    "--python",
    $pythonExecutable,
    "--reinstall",
    "opencv-python-headless>=4.13.0.92,<5"
)

# homr's wheel requires the CPU distribution by package name. Reinstalling the
# GPU wheel last ensures its shared onnxruntime module and CUDA providers win.
Invoke-CheckedCommand -Executable $uvCommand.Source -Arguments @(
    "pip",
    "install",
    "--python",
    $pythonExecutable,
    "--reinstall",
    "onnxruntime-gpu[cuda,cudnn]==1.24.1"
)

Invoke-CheckedCommand -Executable $pythonExecutable -Arguments @(
    "-c",
    "import onnxruntime as ort; ort.preload_dlls(directory=''); providers=ort.get_available_providers(); print(f'ONNX Runtime {ort.__version__}: {providers}'); assert 'CUDAExecutionProvider' in providers"
)

Invoke-CheckedCommand -Executable $pythonExecutable -Arguments @(
    $gpuLauncher,
    "--init"
)

Write-Output "homr GPU environment is ready: $environmentDirectory"
