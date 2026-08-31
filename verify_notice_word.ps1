param([Parameter(Mandatory=$true)][string]$Docx,[Parameter(Mandatory=$true)][string]$Pdf)
$ErrorActionPreference='Stop'
$source=(Resolve-Path -LiteralPath $Docx).Path
$target=[IO.Path]::GetFullPath($Pdf)
if (Test-Path -LiteralPath $target) { throw 'PDF QA already exists; choose a new output.' }
$word=$null
$document=$null
try {
    $word=New-Object -ComObject Word.Application
    $word.Visible=$false
    $word.DisplayAlerts=0
    $word.AutomationSecurity=3
    $document=$word.Documents.Open($source,$false,$true,$false)
    $document.Repaginate()
    $pages=$document.ComputeStatistics(2)
    $document.ExportAsFixedFormat($target,17)
    Write-Output "WORD_OPEN_AND_PDF_EXPORT_PASS: $pages pages; $target"
} finally {
    if ($null -ne $document) { $document.Close(0); [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($document) }
    if ($null -ne $word) { $word.Quit(0); [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($word) }
}
