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
    "homr @ git+https://github.com/liebharc/homr.git@2d0c0a66b6ebc9a8b3e3e61b3a6be4b0e1701d97",
    "pymupdf==1.26.3",
    "music21==10.5.0"
)

# Installed from git rather than PyPI, pinned to an exact commit. The 0.7.0 release predates
# aa5c8ce, which fixes a crash where a rest merged into a chord produces a zero-duration
# element and homr exits non-zero (upstream issue #136). Upstream releases infrequently and
# has not packaged it. Measured against 0.7.0 on the 100-sample OLiMPiC canary: onset F1
# 0.579 -> 0.585, timeline-too-long 53% -> 47%, pitch F1 unchanged within noise.

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
