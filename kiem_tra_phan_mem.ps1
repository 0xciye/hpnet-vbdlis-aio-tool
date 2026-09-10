param([string]$ProjectRoot = $PSScriptRoot)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$node = Join-Path $projectRoot 'src\nodes_tools\runtime\node.exe'
$failures = [Collections.Generic.List[string]]::new()

function Invoke-Check([string]$Name, [string]$Command, [string[]]$Arguments) {
    Write-Host "`n=== $Name ===" -ForegroundColor Cyan
    try {
        & $Command @Arguments
        if ($LASTEXITCODE -ne 0) { throw "Exit code $LASTEXITCODE" }
        Write-Host "[PASS] $Name" -ForegroundColor Green
    } catch {
        $failures.Add("${Name}: $($_.Exception.Message)")
        Write-Host "[FAIL] $Name - $($_.Exception.Message)" -ForegroundColor Red
    }
}

Push-Location -LiteralPath $projectRoot
try {
    Invoke-Check 'Python tests' 'py.exe' @('-3.12', '-X', 'utf8', (Join-Path $projectRoot 'run_tests.py'))

    if (-not (Test-Path -LiteralPath $node -PathType Leaf)) {
        $failures.Add("Node runtime is missing: $node")
        Write-Host "[FAIL] Node runtime is missing: $node" -ForegroundColor Red
    } else {
        $workers = @(
            'Downloader\HPNet PDF Downloader - VNEID APP\hpnet-downloader.cjs',
            'Upload\HPNet Upload VB Du Thao - VNEID APP\hpnet-upload-draft.cjs',
            'Duyet\HPNet Duyet VB Du Thao - VNEID APP\hpnet-approve-draft.cjs'
        )
        foreach ($relative in $workers) {
            $worker = Join-Path (Join-Path $projectRoot 'src\nodes_tools') $relative
            Invoke-Check "Node syntax: $relative" $node @('--check', $worker)
            Invoke-Check "Node self-test: $relative" $node @($worker, '--self-test')
        }
    }

    $uiScripts = @(
        'Downloader\HPNet PDF Downloader - VNEID APP\HPNet-PDF-Downloader.ps1',
        'Upload\HPNet Upload VB Du Thao - VNEID APP\HPNet-Upload-VB-Du-Thao.ps1',
        'Duyet\HPNet Duyet VB Du Thao - VNEID APP\HPNet-Duyet-VB-Du-Thao.ps1'
    )
    foreach ($relative in $uiScripts) {
        $script = Join-Path (Join-Path $projectRoot 'src\nodes_tools') $relative
        Invoke-Check "PowerShell UI self-test: $relative" 'powershell.exe' @(
            '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $script, '-UiSelfTest'
        )
    }
} finally {
    Pop-Location
}

Write-Host ''
if ($failures.Count) {
    Write-Host "TEST FAILED: $($failures.Count) check(s) failed." -ForegroundColor Red
    $failures | ForEach-Object { Write-Host "- $_" -ForegroundColor Red }
    exit 1
}

Write-Host 'ALL TESTS PASSED. No HPNet page was opened and no real data was changed.' -ForegroundColor Green
exit 0
