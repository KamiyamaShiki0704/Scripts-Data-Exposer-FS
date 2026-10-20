param(
    [Parameter(Mandatory=$true)][string]$Manifest,
    [string]$GameExe = 'F:\SteamLibrary\steamapps\common\ELDEN RING\Game\eldenring.exe',
    [switch]$Apply,
    [switch]$Restore
)
$ErrorActionPreference = 'Stop'
$transaction = Get-Content -LiteralPath $Manifest -Raw | ConvertFrom-Json
$expectedRoot = [IO.Path]::GetFullPath('F:\GoldenAge\_GoldenAge\GA\action\script')
if ([IO.Path]::GetFullPath($transaction.script_root) -ne $expectedRoot) { throw 'Unexpected script root' }
if (@(Get-Process -Name eldenring -ErrorAction SilentlyContinue).Count) { throw 'Exit Elden Ring first' }
if ((Get-FileHash -LiteralPath $GameExe -Algorithm SHA256).Hash -ne $transaction.game_sha256) { throw 'Unsupported executable identity' }
$allowed = @('c0000.hks','c9997.hks','Module/exposer/GameBasePointers.hks','Module/MovementControl.lua',
    'Module/LoadingScreens.hks','Module/LockTargetTeleport.lua','Module/EnemySummon.lua')
if (@($transaction.files).Count -ne 7) { throw 'Expected seven files' }
$seen = @{}
foreach ($entry in $transaction.files) {
    if ($entry.relative -notin $allowed -or $seen.ContainsKey($entry.relative)) { throw 'Unexpected or repeated file' }
    $seen[$entry.relative] = $true
    $target = [IO.Path]::GetFullPath((Join-Path $expectedRoot $entry.relative))
    if ($target -ne [IO.Path]::GetFullPath($entry.target)) { throw 'Target mismatch' }
    $cursor = Get-Item -LiteralPath $target
    while ($null -ne $cursor) {
        if ($cursor.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Linked target: $($cursor.FullName)" }
        $cursor = if ($cursor.PSIsContainer) { $cursor.Parent } else { $cursor.Directory }
    }
    $expectedCurrent = if ($Restore) { $entry.new_sha256 } else { $entry.old_sha256 }
    if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $expectedCurrent) { throw "Current file changed: $target" }
    if ((Get-FileHash -LiteralPath $entry.backup -Algorithm SHA256).Hash -ne $entry.old_sha256) { throw 'Backup changed' }
    if ((Get-FileHash -LiteralPath $entry.candidate -Algorithm SHA256).Hash -ne $entry.new_sha256) { throw 'Candidate changed' }
}
foreach ($property in $transaction.protected.PSObject.Properties) {
    $relative = $property.Name.Replace('\','/')
    if ($relative -in $allowed) { continue }
    $target = Join-Path $expectedRoot $property.Name
    if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $property.Value) { throw "Protected file changed: $target" }
}
if (!$Apply) { Write-Output 'PREFLIGHT PASS; dry run only'; exit 0 }
$completed = @()
try {
    foreach ($entry in $transaction.files) {
        $source = if ($Restore) { $entry.backup } else { $entry.candidate }
        $expected = if ($Restore) { $entry.old_sha256 } else { $entry.new_sha256 }
        $completed += $entry
        Copy-Item -LiteralPath $source -Destination $entry.target -Force
        if ((Get-FileHash -LiteralPath $entry.target -Algorithm SHA256).Hash -ne $expected) { throw "Readback mismatch: $($entry.target)" }
    }
    foreach ($property in $transaction.protected.PSObject.Properties) {
        if ($property.Name.Replace('\','/') -in $allowed) { continue }
        if ((Get-FileHash -LiteralPath (Join-Path $expectedRoot $property.Name) -Algorithm SHA256).Hash -ne $property.Value) { throw 'Protected readback failed' }
    }
} catch {
    foreach ($entry in $completed) {
        $source = if ($Restore) { $entry.candidate } else { $entry.backup }
        $expected = if ($Restore) { $entry.new_sha256 } else { $entry.old_sha256 }
        Copy-Item -LiteralPath $source -Destination $entry.target -Force
        if ((Get-FileHash -LiteralPath $entry.target -Algorithm SHA256).Hash -ne $expected) { throw 'Rollback readback failed' }
    }
    throw
}
$transaction.status = if ($Restore) { 'RESTORED_VERIFIED' } else { 'INSTALLED_VERIFIED' }
$transaction | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $Manifest -Encoding UTF8
Write-Output "$($transaction.status): seven scripts; all other script files unchanged"
