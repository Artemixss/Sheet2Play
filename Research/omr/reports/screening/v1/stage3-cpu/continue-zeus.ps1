$ErrorActionPreference = 'Stop'
$screenRoot = 'Research/omr/reports/screening/v1/stage3-cpu'
foreach ($screenIndex in @(6, 11, 16, 21, 26, 31, 36, 41, 46, 51, 56)) {
    $chunkOutput = & Research/omr/.venv/Scripts/python.exe -B Research/omr/screening_cpu_profile.py -- Research/omr/screening_cpu_run.py --manifest Research/omr/reports/screening/v1/manifest-v5-607ff64134da.json --candidate zeus_page --admission Research/omr/reports/screening/v1/2c98d5638c36/admissions/zeus_page/81f73b31179a/admission-7f0f26183984.json --session-id stage3-zeus-screen-01 --start-index $screenIndex --max-items 5 2>&1
    $chunkExit = $LASTEXITCODE
    $chunkOutput | Tee-Object -FilePath "$screenRoot/zeus-infer.log" -Append
    if ($chunkExit -ne 0 -or ($chunkOutput -match '"status": "pending"')) {
        throw "Zeus chunk starting at $screenIndex stopped; preserve evidence and inspect before resuming (exit $chunkExit)."
    }
}
