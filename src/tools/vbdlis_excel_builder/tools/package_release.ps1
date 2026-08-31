param([string]$ReleaseTag = '2026.08.31-logs')

$ErrorActionPreference = 'Stop'
if ($ReleaseTag -notmatch '^[A-Za-z0-9.-]+$') { throw 'Invalid release tag' }
$projectDir = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$releaseDir = Join-Path $projectDir 'release'
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$stageDir = Join-Path $projectDir "tmp/release-ui-cccd-$stamp"
$verifyDir = Join-Path $projectDir "tmp/release-ui-cccd-verify-$stamp"
$backupDir = Join-Path $projectDir "tmp/release-backup-ui-cccd-$stamp"
$appName = 'VBDLIS Excel Builder'
$folderName = "$appName $ReleaseTag"
$zipName = "VBDLIS Excel Builder Windows x64 $ReleaseTag.zip"
$stagedApp = Join-Path $stageDir $folderName
$stagedZip = Join-Path $projectDir "tmp/release-ui-cccd-$stamp.zip"

function Assert-InProject([string]$Target) {
    $resolvedTarget = [IO.Path]::GetFullPath($Target)
    if (-not $resolvedTarget.StartsWith($projectDir + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw "Target outside project: $resolvedTarget"
    }
    return $resolvedTarget
}

New-Item -ItemType Directory -Path $stageDir, $verifyDir -ErrorAction Stop | Out-Null
Copy-Item -LiteralPath (Join-Path $projectDir "dist/$appName") -Destination $stagedApp -Recurse
Copy-Item -LiteralPath (Join-Path $projectDir 'output/pdf/HƯỚNG DẪN SỬ DỤNG VBDLIS EXCEL BUILDER.pdf') -Destination (Join-Path $stagedApp 'HƯỚNG DẪN SỬ DỤNG.pdf')
Copy-Item -LiteralPath (Join-Path $projectDir 'docs/RELEASE_START_HERE.txt') -Destination (Join-Path $stagedApp 'BẮT ĐẦU TẠI ĐÂY.txt')
Copy-Item -LiteralPath (Join-Path $projectDir 'docs/RELEASE_NOTES.txt') -Destination (Join-Path $stagedApp 'GHI CHÚ PHÁT HÀNH.txt')
Copy-Item -LiteralPath (Join-Path $projectDir 'docs/DIAGNOSTIC_GUIDE.txt') -Destination (Join-Path $stagedApp 'HƯỚNG DẪN ĐỌC BÁO CÁO.txt')
foreach ($required in @(
    "$appName.exe", 'HƯỚNG DẪN SỬ DỤNG.pdf', 'BẮT ĐẦU TẠI ĐÂY.txt',
    'HƯỚNG DẪN ĐỌC BÁO CÁO.txt',
    '_internal/resources/BieuMauThuThapThongTinGiayChungNhan.xlsx',
    '_internal/resources/app_icon.ico', '_internal/resources/chevron_down.svg',
    '_internal/resources/check.svg', '_internal/config/profiles.json',
    '_internal/config/template_schema.json'
)) {
    if (-not (Test-Path -LiteralPath (Join-Path $stagedApp $required) -PathType Leaf)) {
        throw "Release missing: $required"
    }
}

Add-Type -AssemblyName System.IO.Compression.FileSystem
[IO.Compression.ZipFile]::CreateFromDirectory($stageDir, $stagedZip, [IO.Compression.CompressionLevel]::Optimal, $false)
[IO.Compression.ZipFile]::ExtractToDirectory($stagedZip, $verifyDir)
$fileCount = 0
foreach ($file in (Get-ChildItem -LiteralPath $stageDir -Recurse -File)) {
    $relative = [IO.Path]::GetRelativePath($stageDir, $file.FullName)
    $extractedFile = Join-Path $verifyDir $relative
    if ((Get-FileHash -LiteralPath $file.FullName).Hash -ne (Get-FileHash -LiteralPath $extractedFile).Hash) {
        throw "ZIP file mismatch: $relative"
    }
    $fileCount++
}
& (Join-Path $projectDir '.venv314/Scripts/python.exe') (Join-Path $PSScriptRoot 'verify_build.py') (Join-Path $verifyDir "$folderName/$appName.exe")
if ($LASTEXITCODE -ne 0) { throw 'Extracted release failed smoke test' }
& (Join-Path $projectDir '.venv314/Scripts/python.exe') (Join-Path $PSScriptRoot 'windows_file_icon.py') (Join-Path $verifyDir "$folderName/$appName.exe") --refresh --output (Join-Path $projectDir "tmp/icon-release-$stamp")
if ($LASTEXITCODE -ne 0) { throw 'Extracted release failed Shell icon check' }

# Keep the previous release recoverable. Validate all move targets first.
foreach ($target in @($releaseDir, $backupDir, $stagedApp, $stagedZip,
    (Join-Path $releaseDir $folderName), (Join-Path $releaseDir $zipName))) {
    Assert-InProject $target | Out-Null
}
New-Item -ItemType Directory -Path $releaseDir, $backupDir -Force | Out-Null
foreach ($name in @($folderName, $zipName)) {
    $existing = Join-Path $releaseDir $name
    if (Test-Path -LiteralPath $existing) {
        Move-Item -LiteralPath $existing -Destination $backupDir
    }
}
Move-Item -LiteralPath $stagedApp -Destination $releaseDir
Move-Item -LiteralPath $stagedZip -Destination (Join-Path $releaseDir $zipName)
$finalZip = Get-Item -LiteralPath (Join-Path $releaseDir $zipName)
Write-Output "Release PASS: $fileCount files verified; $($finalZip.Length) bytes"
Write-Output "ZIP: $($finalZip.FullName)"
Write-Output "SHA256: $((Get-FileHash -LiteralPath $finalZip.FullName).Hash)"
Write-Output "Previous release preserved: $backupDir"
