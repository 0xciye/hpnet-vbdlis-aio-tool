param([Parameter(Mandatory=$true)][string]$ReleaseFolder)
# Restore only binary dependencies. Never copy user config, login data or logs.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$releasePath = (Resolve-Path -LiteralPath $ReleaseFolder).Path
$sourceRoot = Join-Path $releasePath '_internal\nodes_tools'
$targetRoot = Join-Path $projectRoot 'src\nodes_tools'
$tools = @(
    @{ Folder='Downloader\HPNet PDF Downloader - VNEID APP'; Exe='HPNet PDF Downloader.exe' },
    @{ Folder='Upload\HPNet Upload VB Du Thao - VNEID APP'; Exe='HPNet Upload VB Du Thao.exe' },
    @{ Folder='Duyet\HPNet Duyet VB Du Thao - VNEID APP'; Exe='HPNet Duyet VB Du Thao.exe' }
)
function Assert-NoLinks([string]$candidate) {
    $cursor = [IO.Path]::GetFullPath($candidate)
    while ($cursor) {
        if ((Test-Path -LiteralPath $cursor) -and ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw "Refusing linked path: $cursor"
        }
        $cursor = Split-Path -Parent $cursor
    }
}
$copies = @()
$sharedOrigin = Join-Path $sourceRoot 'runtime'
if (-not ((Test-Path -LiteralPath (Join-Path $sharedOrigin 'node.exe') -PathType Leaf) -and
          (Test-Path -LiteralPath (Join-Path $sharedOrigin 'node_modules\playwright\package.json') -PathType Leaf))) {
    # Releases before the shared-runtime layout kept an identical runtime in
    # every HPNet tool. Use Downloader as the verified migration source.
    $sharedOrigin = Join-Path $sourceRoot 'Downloader\HPNet PDF Downloader - VNEID APP\runtime'
}
$sharedDestination = Join-Path $targetRoot 'runtime'
foreach ($required in @('node.exe', 'node_modules\playwright\package.json')) {
    if (-not (Test-Path -LiteralPath (Join-Path $sharedOrigin $required) -PathType Leaf)) { throw "Incomplete release runtime: $sharedOrigin\$required" }
}
Assert-NoLinks $sharedOrigin
Assert-NoLinks $sharedDestination
$runtimeItems = @(Get-ChildItem -LiteralPath $sharedOrigin -Recurse -Force)
if ($runtimeItems | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }) { throw "Linked item in runtime: $sharedOrigin" }
foreach ($file in @($runtimeItems | Where-Object { -not $_.PSIsContainer })) {
    $relative = $file.FullName.Substring($sharedOrigin.Length + 1)
    $target = [IO.Path]::GetFullPath((Join-Path $sharedDestination $relative))
    if (-not $target.StartsWith($sharedDestination + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe shared runtime destination.' }
    $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
    if (Test-Path -LiteralPath $target) {
        if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $hash) { throw "Existing runtime differs; no overwrite: $target" }
    } else {
        $copies += [pscustomobject]@{ Source=$file.FullName; Target=$target; Hash=$hash }
    }
}
foreach ($tool in $tools) {
    $origin = Join-Path $sourceRoot $tool.Folder
    $destination = Join-Path $targetRoot $tool.Folder
    Assert-NoLinks $origin
    Assert-NoLinks $destination
    foreach ($required in @($tool.Exe)) {
        if (-not (Test-Path -LiteralPath (Join-Path $origin $required) -PathType Leaf)) { throw "Incomplete release: $origin\$required" }
    }
    $files = @((Get-Item -LiteralPath (Join-Path $origin $tool.Exe)))
    foreach ($file in $files) {
        $relative = $file.FullName.Substring($origin.Length + 1)
        $target = [IO.Path]::GetFullPath((Join-Path $destination $relative))
        if (-not $target.StartsWith($destination + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe destination.' }
        Assert-NoLinks $target
        $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
        if (Test-Path -LiteralPath $target) {
            if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $hash) { throw "Existing runtime differs; no overwrite: $target" }
        } else {
            $copies += [pscustomobject]@{ Source=$file.FullName; Target=$target; Hash=$hash }
        }
    }
}
foreach ($copy in $copies) {
    $parent = Split-Path -Parent $copy.Target
    if (-not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
    [IO.File]::Copy($copy.Source, $copy.Target, $false)
    if ((Get-FileHash -LiteralPath $copy.Target -Algorithm SHA256).Hash -ne $copy.Hash) { throw "Copy verification failed: $($copy.Target)" }
}
Write-Host "RUNTIME_READY: $($copies.Count) files restored; identical existing files kept. No source/config/session/log changes."
