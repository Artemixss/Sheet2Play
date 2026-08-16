param(
    [ValidateSet('Inference', 'Training')]
    [string]$Profile = 'Inference',
    [switch]$SkipCudaSmoke
)

$ErrorActionPreference = 'Stop'
$projectRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$runtimeRoot = Join-Path $projectRoot '.runtime'
$sourcePath = Join-Path $runtimeRoot 'transcoda'
$environmentPath = Join-Path $projectRoot '.venv'
$pythonPath = Join-Path $environmentPath 'Scripts\python.exe'
$assetLockPath = Join-Path $projectRoot 'assets.lock.json'
$inferenceRequirements = Join-Path $projectRoot 'requirements-inference.lock.txt'
$trainingRequirements = Join-Path $projectRoot 'requirements-training.lock.txt'
$setupStatePath = Join-Path $runtimeRoot 'setup-state.json'
$minimumFreeBytes = 14GB
$torchVersion = '2.9.1'
$torchvisionVersion = '0.24.1'
$torchaoVersion = '0.15.0'
$torchtuneVersion = '0.6.1'
$pytorchIndex = 'https://download.pytorch.org/whl/cu130'
$completedStages = [System.Collections.Generic.List[string]]::new()

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)][string]$Description,
        [Parameter(Mandatory = $true)][string]$Command,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Description failed with exit code $LASTEXITCODE."
    }
}

function Write-SetupState {
    param([Parameter(Mandatory = $true)][string]$Stage)

    if (-not $completedStages.Contains($Stage)) {
        $completedStages.Add($Stage)
    }
    $payload = [ordered]@{
        schema_version = 1
        profile = $Profile.ToLowerInvariant()
        source_revision = [string]$assetLock.source.revision
        model_revision = [string]$assetLock.model.revision
        base_model_revision = [string]$assetLock.base_model.revision
        torch = $torchVersion
        torchvision = $torchvisionVersion
        torchao = $torchaoVersion
        torchtune = $torchtuneVersion
        completed_stages = @($completedStages)
        updated_at_utc = [DateTime]::UtcNow.ToString('o')
    } | ConvertTo-Json -Depth 4
    $temporaryStatePath = "$setupStatePath.tmp"
    [System.IO.File]::WriteAllText($temporaryStatePath, $payload, [System.Text.UTF8Encoding]::new($false))
    Move-Item -LiteralPath $temporaryStatePath -Destination $setupStatePath -Force
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw 'uv is required. Install uv, then rerun setup_research.ps1.'
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw 'git is required. Install Git, then rerun setup_research.ps1.'
}
if (-not (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) {
    throw 'nvidia-smi is required to verify the CUDA device before installation.'
}
foreach ($requiredFile in @($assetLockPath, $inferenceRequirements, $trainingRequirements)) {
    if (-not (Test-Path -LiteralPath $requiredFile -PathType Leaf)) {
        throw "Required setup file is missing: $requiredFile"
    }
}

try {
    $assetLock = Get-Content -LiteralPath $assetLockPath -Raw | ConvertFrom-Json
} catch {
    throw "Cannot parse the asset lock: $($_.Exception.Message)"
}
$sourceRevision = [string]$assetLock.source.revision
$sourceRepository = [string]$assetLock.source.repository
if ($sourceRevision -notmatch '^[0-9a-f]{40}$' -or $assetLock.source.revision_algorithm -ne 'git-sha1') {
    throw 'The asset lock must contain a full Git SHA-1 Transcoda revision.'
}
foreach ($snapshot in @($assetLock.model, $assetLock.base_model)) {
    if ([string]$snapshot.revision -notmatch '^[0-9a-f]{40}$') {
        throw "Model snapshot revision must be a full 40-character hash: $($snapshot.repository)"
    }
}

$driveRoot = [System.IO.Path]::GetPathRoot($projectRoot)
$freeBytes = ([System.IO.DriveInfo]::new($driveRoot)).AvailableFreeSpace
if ($freeBytes -lt $minimumFreeBytes) {
    throw ('At least 14 GiB free is required for setup; {0:N2} GiB is available on {1}.' -f ($freeBytes / 1GB), $driveRoot)
}

$cudaInfo = (& nvidia-smi '--query-gpu=name,driver_version,memory.total' '--format=csv,noheader,nounits' '--id=0').Trim()
if ($LASTEXITCODE -ne 0) { throw 'nvidia-smi could not inspect GPU 0.' }
if ($cudaInfo -notmatch 'RTX 4050') { throw "Expected an RTX 4050 on GPU 0; found: $cudaInfo" }

New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
$completedStages.Add('preflight')
Write-SetupState -Stage 'preflight'

$sourceCandidatePath = "$sourcePath.partial"
if (-not (Test-Path -LiteralPath $sourcePath -PathType Container)) {
    if (-not (Test-Path -LiteralPath $sourceCandidatePath -PathType Container)) {
        Invoke-CheckedCommand -Description 'Transcoda clone' -Command 'git' -Arguments @(
            'clone', '--filter=blob:none', '--no-checkout', $sourceRepository, $sourceCandidatePath
        )
    }
    $candidateRemote = (& git -C $sourceCandidatePath remote get-url origin).Trim()
    if ($LASTEXITCODE -ne 0 -or $candidateRemote -ne $sourceRepository) {
        throw "Unexpected partial Transcoda checkout at $sourceCandidatePath. Inspect it before retrying."
    }
    Invoke-CheckedCommand -Description 'Pinned Transcoda fetch' -Command 'git' -Arguments @(
        '-C', $sourceCandidatePath, 'fetch', '--depth', '1', 'origin', $sourceRevision
    )
    Invoke-CheckedCommand -Description 'Pinned Transcoda checkout' -Command 'git' -Arguments @(
        '-C', $sourceCandidatePath, 'checkout', '--detach', $sourceRevision
    )
    Move-Item -LiteralPath $sourceCandidatePath -Destination $sourcePath
}
$actualRemote = (git -C $sourcePath remote get-url origin).Trim()
if ($LASTEXITCODE -ne 0 -or $actualRemote -ne $sourceRepository) {
    throw "Unexpected Transcoda checkout at $sourcePath. Remove it manually after inspection."
}
Invoke-CheckedCommand -Description 'Pinned Transcoda fetch' -Command 'git' -Arguments @(
    '-C', $sourcePath, 'fetch', '--depth', '1', 'origin', $sourceRevision
)
Invoke-CheckedCommand -Description 'Pinned Transcoda checkout' -Command 'git' -Arguments @(
    '-C', $sourcePath, 'checkout', '--detach', $sourceRevision
)
$actualRevision = (git -C $sourcePath rev-parse --verify 'HEAD^{commit}').Trim()
if ($actualRevision -ne $sourceRevision) { throw "Source revision mismatch: $actualRevision" }
$trackedChanges = @(git -C $sourcePath status --porcelain --untracked-files=no)
if ($LASTEXITCODE -ne 0 -or $trackedChanges.Count -ne 0) {
    throw 'The Transcoda checkout contains tracked modifications.'
}
$unsafeUntracked = @(git -C $sourcePath ls-files --others --exclude-standard | Where-Object {
    $_ -match '\.(bin|gbnf|json|onnx|pt|pth|py|safetensors)$'
})
if ($LASTEXITCODE -ne 0 -or $unsafeUntracked.Count -ne 0) {
    throw "The Transcoda checkout contains unlocked executable files: $($unsafeUntracked -join ', ')"
}
Invoke-CheckedCommand -Description 'Transcoda Git object verification' -Command 'git' -Arguments @(
    '-C', $sourcePath, 'fsck', '--no-progress', '--connectivity-only', 'HEAD'
)
Write-SetupState -Stage 'source_verified'

if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    Invoke-CheckedCommand -Description 'Python 3.11 environment creation' -Command 'uv' -Arguments @(
        'venv', '--python', '3.11', $environmentPath
    )
}
$pythonVersionCheck = 'import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 11) else 3)'
& $pythonPath -c $pythonVersionCheck
if ($LASTEXITCODE -ne 0) {
    throw 'Research environment must use Python 3.11.'
}
Write-SetupState -Stage 'environment_ready'

Invoke-CheckedCommand -Description 'CUDA PyTorch installation' -Command 'uv' -Arguments @(
    'pip', 'install', '--python', $pythonPath, '--index-url', $pytorchIndex,
    "torch==$torchVersion", "torchvision==$torchvisionVersion"
)
Invoke-CheckedCommand -Description 'Locked inference dependency installation' -Command 'uv' -Arguments @(
    'pip', 'install', '--python', $pythonPath, '--requirement', $inferenceRequirements
)
if ($Profile -eq 'Training') {
    Invoke-CheckedCommand -Description 'Locked training dependency installation' -Command 'uv' -Arguments @(
        'pip', 'install', '--python', $pythonPath, '--requirement', $trainingRequirements
    )
}
Invoke-CheckedCommand -Description 'Research CLI installation' -Command 'uv' -Arguments @(
    'pip', 'install', '--python', $pythonPath, '--no-deps', '--editable', $projectRoot
)
Write-SetupState -Stage 'dependencies_installed'

$env:HF_HOME = Join-Path $runtimeRoot 'hf-cache'
$env:HF_HUB_DISABLE_TELEMETRY = '1'
$env:HF_HUB_OFFLINE = '0'
$env:TRANSFORMERS_OFFLINE = '0'
Invoke-CheckedCommand -Description 'Pinned model download and hash verification' -Command $pythonPath -Arguments @(
    (Join-Path $projectRoot 'download_assets.py'), '--project-root', $projectRoot
)
Write-SetupState -Stage 'assets_verified'

$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
if ($SkipCudaSmoke) {
    Invoke-CheckedCommand -Description 'Offline runtime verification' -Command $pythonPath -Arguments @(
        '-m', 'sheet2play_omr', 'verify-runtime'
    )
} else {
    Invoke-CheckedCommand -Description 'Offline CUDA runtime verification' -Command $pythonPath -Arguments @(
        '-m', 'sheet2play_omr', 'verify-runtime', '--cuda-smoke'
    )
}
Write-SetupState -Stage 'offline_runtime_verified'

Write-Output "Transcoda $Profile profile is pinned, hash-verified, offline-ready, and CUDA-verified."
