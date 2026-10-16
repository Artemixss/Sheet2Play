param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('development', 'comparison')]
    [string]$Mode
)
$ErrorActionPreference = 'Stop'
$researchRoot465 = $PSScriptRoot
$workspaceRoot465 = (Resolve-Path (Join-Path $researchRoot465 '..\..')).Path
Set-Location -LiteralPath $workspaceRoot465
$evidenceRoot465 = Join-Path $researchRoot465 'reports\homr-timing-465\phase2'
$env:PYTHONPATH = "$evidenceRoot465\gate;$researchRoot465;$researchRoot465\src"
$inputs465 = Join-Path $evidenceRoot465 "$Mode-inputs.json"
$rows465 = Get-Content -LiteralPath $inputs465 -Raw | ConvertFrom-Json
$sequence465 = Join-Path $evidenceRoot465 "$Mode-sequence.jsonl"
$sessionClock465 = [System.Diagnostics.Stopwatch]::StartNew()
if ($Mode -eq 'comparison' -and -not (Test-Path (Join-Path $evidenceRoot465 'comparison-freeze.json'))) {
    throw 'Comparison requires a completed development review and freeze.'
}
for ($index465 = 0; $index465 -lt $rows465.Count; $index465++) {
    $row465 = $rows465[$index465]
    $profiles465 = @('candidate')
    if ($Mode -eq 'comparison') {
        $profiles465 = if ($index465 % 2 -eq 0) { @('candidate', 'control') } else { @('control', 'candidate') }
    }
    foreach ($profile465 in $profiles465) {
        $configuration465 = Join-Path $evidenceRoot465 "$profile465-configuration.json"
        $configurationData465 = Get-Content -LiteralPath $configuration465 -Raw | ConvertFrom-Json
        $destination465 = if ($Mode -eq 'development') { Join-Path $evidenceRoot465 "development\$($row465.item_id)" } else { Join-Path $evidenceRoot465 "comparison\$profile465\$($row465.item_id)" }
        $receipt465 = Join-Path $destination465 'result.json'
        if (Test-Path -LiteralPath $receipt465) {
            $existing465 = Get-Content -LiteralPath $receipt465 -Raw | ConvertFrom-Json
            if ($existing465.configuration_identity -ne $configurationData465.identity_sha256 -or $existing465.status -eq 'resource_stopped') {
                throw 'Existing identity/resource failure requires review; no implicit retry.'
            }
            continue
        }
        if ($sessionClock465.Elapsed.TotalSeconds -ge 13740) { throw 'Four-hour session boundary: stop before another worker.' }
        $job465 = Join-Path $evidenceRoot465 "jobs\$Mode-$profile465-$($row465.item_id)"
        if (Test-Path -LiteralPath $job465) { throw 'An existing interrupted attempt requires review; no automatic retry.' }
        $command465 = @('-B', "$researchRoot465\guarded_execution.py", '--output', $job465, '--max-seconds', '600', '--', $configurationData465.python.path, '-B', "$researchRoot465\homr_465_capture.py", '--configuration', $configuration465, '--inputs', $inputs465, '--item', $row465.item_id, '--output', $destination465)
        @{ item = $row465.item_id; profile = $profile465; status = 'starting'; utc = [DateTime]::UtcNow.ToString('o'); command = $command465 } | ConvertTo-Json -Compress | Add-Content -LiteralPath $sequence465
        & "$researchRoot465\.venv\Scripts\python.exe" @command465
        $exit465 = $LASTEXITCODE
        $outcome465 = Get-Content -LiteralPath (Join-Path $job465 'result.json') -Raw | ConvertFrom-Json
        $capture465 = if (Test-Path -LiteralPath $receipt465) { Get-Content -LiteralPath $receipt465 -Raw | ConvertFrom-Json } else { $null }
        @{ item = $row465.item_id; profile = $profile465; status = $outcome465.status; capture_status = $capture465.status; utc = [DateTime]::UtcNow.ToString('o'); exit = $exit465; elapsed_seconds = $outcome465.elapsed_seconds } | ConvertTo-Json -Compress | Add-Content -LiteralPath $sequence465
        if ($outcome465.status -eq 'blocked' -or $null -eq $capture465 -or $capture465.status -eq 'resource_stopped' -or ($exit465 -ne 0 -and $capture465.status -ne 'failed')) {
            throw "Execution stopped at $($row465.item_id) / $profile465; preserve receipts and inspect before further work."
        }
        Write-Output "$Mode $($index465 + 1)/$($rows465.Count) $profile465 $($capture465.status)"
    }
}
