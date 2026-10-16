[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$EvidenceDirectory,
    [switch]$Apply
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$taskRegistryPath = 'SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management'
$taskExpectedValue = 'C:\pagefile.sys 16384 32768'
$taskDesiredValue = 'C:\pagefile.sys 0 0'

function Write-Evidence([string]$Path, [object]$Data) {
    $taskStream = [IO.File]::Open($Path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write)
    try {
        $taskWriter = [IO.StreamWriter]::new($taskStream, [Text.UTF8Encoding]::new($false))
        try {
            $taskWriter.WriteLine(($Data | ConvertTo-Json -Depth 6))
            $taskWriter.Flush()
            $taskStream.Flush($true)
        }
        finally { $taskWriter.Dispose() }
    }
    finally { $taskStream.Dispose() }
}

function Read-PagefileState {
    $taskKey = [Microsoft.Win32.Registry]::LocalMachine.OpenSubKey($taskRegistryPath, $false)
    if ($null -eq $taskKey) { throw 'Memory Management key is unavailable.' }
    try {
        if ($taskKey.GetValueKind('PagingFiles') -ne [Microsoft.Win32.RegistryValueKind]::MultiString) {
            throw 'PagingFiles has an unexpected registry type.'
        }
        $taskEntries = @($taskKey.GetValue('PagingFiles'))
    }
    finally { $taskKey.Dispose() }
    $taskComputer = Get-CimInstance -ClassName Win32_ComputerSystem -OperationTimeoutSec 10
    [pscustomobject]@{
        CapturedAt = (Get-Date).ToString('o')
        PagingFiles = $taskEntries
        AutomaticManagedPagefile = $taskComputer.AutomaticManagedPagefile
        Settings = @(Get-CimInstance -ClassName Win32_PageFileSetting -OperationTimeoutSec 10 |
            Select-Object Name, InitialSize, MaximumSize)
        RuntimeUsage = @(Get-CimInstance -ClassName Win32_PageFileUsage -OperationTimeoutSec 10 |
            Select-Object Name, AllocatedBaseSize, CurrentUsage, PeakUsage)
    }
}

function Restore-OriginalPagefile([Microsoft.Win32.RegistryKey]$Key, [System.Collections.IDictionary]$Result) {
    try {
        $Key.SetValue('PagingFiles', [string[]]@($taskExpectedValue), [Microsoft.Win32.RegistryValueKind]::MultiString)
        $Key.Flush()
        $Result['RollbackVerified'] = ((@($Key.GetValue('PagingFiles')) -join '|') -ieq $taskExpectedValue)
    }
    catch { $Result['RollbackError'] = $_.Exception.Message }
}

$taskOutput = [IO.Path]::GetFullPath($EvidenceDirectory)
$taskAllowedPrefix = [IO.Path]::GetFullPath($PSScriptRoot) + [IO.Path]::DirectorySeparatorChar
if (-not $taskOutput.StartsWith($taskAllowedPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Evidence must be in a new directory underneath this script directory.'
}
if (Test-Path -LiteralPath $taskOutput) { throw 'Refusing to overwrite existing evidence.' }
[IO.Directory]::CreateDirectory($taskOutput) | Out-Null
$taskResult = [ordered]@{ Status = 'blocked'; Apply = [bool]$Apply; RebootPerformed = $false }
$taskMutated = $false
$taskKey = $null
try {
    $taskBefore = Read-PagefileState
    Write-Evidence (Join-Path $taskOutput 'before.json') $taskBefore
    if ($taskBefore.AutomaticManagedPagefile -or $taskBefore.PagingFiles.Count -ne 1 -or
        $taskBefore.PagingFiles[0] -ine $taskExpectedValue) {
        throw 'Paging policy differs from the approved single C: custom setting; review before applying.'
    }
    $taskDrive = Get-CimInstance -ClassName Win32_LogicalDisk -Filter "DeviceID='C:'" -OperationTimeoutSec 10
    if ($null -eq $taskDrive -or $taskDrive.FreeSpace -lt 64GB) {
        throw 'C: must have at least 64 GiB free for the reviewed paging proposal.'
    }
    $taskResult.DesiredPagingFiles = @($taskDesiredValue)
    $taskResult.OriginalPagingFiles = @($taskBefore.PagingFiles)
    if ($Apply) {
        $taskIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
        $taskPrincipal = [Security.Principal.WindowsPrincipal]::new($taskIdentity)
        if (-not $taskPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
            throw 'Administrator elevation is required; no paging policy was changed.'
        }
        $taskKey = [Microsoft.Win32.Registry]::LocalMachine.OpenSubKey($taskRegistryPath, $true)
        if ($null -eq $taskKey) { throw 'Cannot open paging configuration for the approved change.' }
        $taskCurrent = @($taskKey.GetValue('PagingFiles'))
        if ($taskCurrent.Count -ne 1 -or $taskCurrent[0] -ine $taskExpectedValue) {
            throw 'PagingFiles changed after the snapshot; refusing the mutation.'
        }
        # Microsoft Windows Support documents C:\pagefile.sys 0 0 as C-only system-managed size.
        $taskKey.SetValue('PagingFiles', [string[]]@($taskDesiredValue), [Microsoft.Win32.RegistryValueKind]::MultiString)
        $taskMutated = $true
        $taskKey.Flush()
        $taskAfter = Read-PagefileState
        Write-Evidence (Join-Path $taskOutput 'after.json') $taskAfter
        if ($taskAfter.AutomaticManagedPagefile -or $taskAfter.PagingFiles.Count -ne 1 -or
            $taskAfter.PagingFiles[0] -ine $taskDesiredValue) {
            throw 'Post-change paging configuration verification failed.'
        }
        $taskResult.Status = 'configured_pending_reboot'
        $taskResult.RuntimeCapacityVerifiedAfterReboot = $false
    }
    else { $taskResult.Status = 'preview_validated_no_change' }
}
catch {
    $taskResult.Error = $_.Exception.Message
    if ($taskMutated -and $null -ne $taskKey) {
        Restore-OriginalPagefile $taskKey $taskResult
    }
}
finally {
    try { Write-Evidence (Join-Path $taskOutput 'result.json') $taskResult }
    catch {
        $taskResult.Status = 'blocked'
        $taskResult.ResultPersistenceError = $_.Exception.Message
        if ($taskMutated -and $null -ne $taskKey) {
            Restore-OriginalPagefile $taskKey $taskResult
        }
        [Console]::Error.WriteLine('Final evidence could not be saved; inspect the emitted rollback result before proceeding.')
    }
    finally { if ($null -ne $taskKey) { $taskKey.Dispose() } }
}
$taskResult | ConvertTo-Json -Depth 4
if ($taskResult.Status -eq 'blocked') { exit 2 }
