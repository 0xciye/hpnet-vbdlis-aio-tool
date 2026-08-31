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
foreach ($tool in $tools) {
    $origin = Join-Path $sourceRoot $tool.Folder
    $destination = Join-Path $targetRoot $tool.Folder
    Assert-NoLinks $origin
    Assert-NoLinks $destination
    foreach ($required in @($tool.Exe, 'runtime\node.exe', 'runtime\node_modules\playwright\package.json')) {
        if (-not (Test-Path -LiteralPath (Join-Path $origin $required) -PathType Leaf)) { throw "Incomplete release: $origin\$required" }
    }
    $runtimeItems = @(Get-ChildItem -LiteralPath (Join-Path $origin 'runtime') -Recurse -Force)
    if ($runtimeItems | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }) { throw "Linked item in runtime: $origin" }
    $files = @((Get-Item -LiteralPath (Join-Path $origin $tool.Exe))) + @($runtimeItems | Where-Object { -not $_.PSIsContainer })
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
