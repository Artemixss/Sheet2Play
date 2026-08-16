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
        [string[]]$Arguments
    )

    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
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
    "homr==0.7.0",
    "pymupdf==1.26.3",
    "music21==10.5.0"
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
