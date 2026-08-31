param([switch]$SelfTest, [switch]$UiSelfTest, [string]$TestImagePath)

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$toolRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$nodeScript = Join-Path $toolRoot 'hpnet-downloader.cjs'
$configPath = Join-Path $toolRoot 'cau_hinh.json'

function Normalize-CommuneCode([string]$text) {
    $code = if ($null -eq $text) { '' } else { $text.Trim() }
    if ($code -notmatch '^\d{5}$') { throw 'Mã xã phải gồm đúng 5 chữ số, ví dụ: 10930.' }
    return $code
}

function Parse-NotificationNumbers([string]$text) {
    if ([string]::IsNullOrWhiteSpace($text)) { throw 'Vui lòng nhập ít nhất một số thông báo.' }
    $numbers = New-Object 'System.Collections.Generic.HashSet[int]'
    foreach ($rawPart in ($text -split '[,;\r\n]+')) {
        $part = $rawPart.Trim()
        if (-not $part) { continue }
        if ($part -match '^\d+$') { [void]$numbers.Add([int]$part); continue }
        if ($part -notmatch '^(\d+)\s*[\u002D\u2013\u2014]\s*(\d+)$') {
            throw "Định dạng không hợp lệ: $part. Ví dụ đúng: 1712, 1715, 1720-1725"
        }
        $start = [int]$Matches[1]; $end = [int]$Matches[2]
        if ($end -lt $start) { throw "Khoảng số phải tăng dần: $part" }
        if (($end - $start + 1) -gt 10000) { throw "Khoảng số quá lớn: $part" }
        for ($number = $start; $number -le $end; $number++) { [void]$numbers.Add($number) }
    }
    if ($numbers.Count -eq 0) { throw 'Không nhận diện được số thông báo nào.' }
    return @($numbers | Sort-Object)
}

function Parse-DocumentSymbols([string]$text) {
    return @($text -split '[,;\r\n]+' | ForEach-Object { $_.Trim() } | Where-Object { $_ } | Select-Object -Unique)
}

function Has-ConfigProperty($object, [string]$name) {
    return ($null -ne $object -and $null -ne $object.PSObject.Properties[$name])
}

function Find-HPNetRuntime {
    param([switch]$SkipBrowserCheck)
    $portableRoot = Join-Path $toolRoot 'runtime'
    $portableNode = Join-Path $portableRoot 'node.exe'
    $portableModules = Join-Path $portableRoot 'node_modules'
    if ((Test-Path -LiteralPath $portableNode) -and (Test-Path -LiteralPath (Join-Path $portableModules 'playwright'))) {
        $nodeExe = $portableNode; $nodeModules = $portableModules; $runtimeMode = 'Portable đi kèm công cụ'
    } else {
        $runtimeRoot = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\node'
        $nodeExe = Join-Path $runtimeRoot 'bin\node.exe'; $nodeModules = Join-Path $runtimeRoot 'node_modules'; $runtimeMode = 'Bộ chạy của Codex trên máy hiện tại'
        if (-not (Test-Path -LiteralPath $nodeExe)) { throw 'Không tìm thấy bộ chạy. Hãy dùng gói PORTABLE.' }
        if (-not (Test-Path -LiteralPath (Join-Path $nodeModules 'playwright'))) { throw 'Không tìm thấy Playwright. Hãy dùng gói PORTABLE.' }
    }
    $edgeExe = @('C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe','C:\Program Files\Microsoft\Edge\Application\msedge.exe') | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $edgeExe -and -not $SkipBrowserCheck) { throw 'Không tìm thấy Microsoft Edge.' }
    return [PSCustomObject]@{ NodeExe=$nodeExe; NodeModules=$nodeModules; EdgeExe=$edgeExe; Mode=$runtimeMode }
}

try { $runtime = Find-HPNetRuntime -SkipBrowserCheck:($SelfTest -or $UiSelfTest) } catch {
    if ($SelfTest -or $UiSelfTest) { throw }
    [System.Windows.Forms.MessageBox]::Show($_.Exception.Message,'HPNet PDF Downloader','OK','Error') | Out-Null
    exit 1
}

if ($SelfTest) {
    $numbers = @(Parse-NotificationNumbers '1712,1715,1720-1723,1712')
    if (($numbers -join ',') -ne '1712,1715,1720,1721,1722,1723') { throw 'Self-test PowerShell: parser số thông báo không đúng.' }
    if ((Parse-DocumentSymbols "TB-ĐKĐĐ`r`nQĐ-UBND`r`nTB-ĐKĐĐ").Count -ne 2) { throw 'Self-test PowerShell: parser ký hiệu không đúng.' }
    if ((Normalize-CommuneCode ' 10930 ') -ne '10930') { throw 'Self-test PowerShell: mã xã không đúng.' }
    [PSCustomObject]@{ NodeScriptExists=(Test-Path -LiteralPath $nodeScript); RuntimeMode=$runtime.Mode; NotificationParser='PASS'; SymbolParser='PASS'; DatePicker='dd/MM/yyyy'; CommuneCode='PASS' } | ConvertTo-Json
    exit 0
}

$defaultOutput = Join-Path ([Environment]::GetFolderPath('Desktop')) 'PDF HPNET'
$savedConfig = $null
if (Test-Path -LiteralPath $configPath) {
    try { $savedConfig = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json } catch { $savedConfig = $null }
}
if (-not $savedConfig) {
    $savedConfig = [pscustomobject][ordered]@{
        configVersion=3; downloadMode='titles'; titleFilterEnabled=$true; allowedTitles=@(); notificationFilterEnabled=$false; notificationNumbers=''
        symbolFilterEnabled=$false; documentSymbols=''; dateFilterEnabled=$false; dateMode='exact'; exactDate=(Get-Date).ToString('yyyy-MM-dd')
        startDate=(Get-Date).ToString('yyyy-MM-dd'); endDate=(Get-Date).ToString('yyyy-MM-dd'); communeCode='10930'; outputDir=$defaultOutput
        readFilter='all'; onlyUnread=$false; listPageSize=100; allowMissingCommuneCode=$true
    }
    if (-not $UiSelfTest) { $savedConfig | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $configPath -Encoding UTF8 }
}

$legacyNumberMode = (Has-ConfigProperty $savedConfig 'downloadMode') -and ([string]$savedConfig.downloadMode -eq 'numbers')
$savedTitleEnabled = if (Has-ConfigProperty $savedConfig 'titleFilterEnabled') { [bool]$savedConfig.titleFilterEnabled } else { -not $legacyNumberMode }
$savedNumberEnabled = if (Has-ConfigProperty $savedConfig 'notificationFilterEnabled') { [bool]$savedConfig.notificationFilterEnabled } else { $legacyNumberMode }
$savedSymbolEnabled = if (Has-ConfigProperty $savedConfig 'symbolFilterEnabled') { [bool]$savedConfig.symbolFilterEnabled } else { $false }
$savedDateEnabled = if (Has-ConfigProperty $savedConfig 'dateFilterEnabled') { [bool]$savedConfig.dateFilterEnabled } else { $false }

function Get-SavedDate([string]$name) {
    $value = if (Has-ConfigProperty $savedConfig $name) { [string]$savedConfig.$name } else { '' }
    $parsed = [datetime]::Today
    if ([datetime]::TryParseExact($value,@('yyyy-MM-dd','dd/MM/yyyy','dd-MM-yyyy'),[Globalization.CultureInfo]::InvariantCulture,[Globalization.DateTimeStyles]::None,[ref]$parsed)) { return $parsed }
    return [datetime]::Today
}

function New-Label($parent,[string]$text,[int]$x,[int]$y,[int]$w,[int]$h,$font) {
    $control = New-Object System.Windows.Forms.Label
    $control.Text=$text; $control.Location=New-Object System.Drawing.Point($x,$y); $control.Size=New-Object System.Drawing.Size($w,$h); $control.Font=$font
    $parent.Controls.Add($control); return $control
}

[System.Windows.Forms.Application]::EnableVisualStyles()
$fontNormal = New-Object System.Drawing.Font('Segoe UI',9.75)
$fontBold = New-Object System.Drawing.Font('Segoe UI',9.75,[System.Drawing.FontStyle]::Bold)
$form = New-Object System.Windows.Forms.Form
$form.Text='HPNet PDF Downloader - Đối soát đầy đủ 2026.08.31'; $form.StartPosition='CenterScreen'; $form.Size=New-Object System.Drawing.Size(930,1000); $form.MinimumSize=New-Object System.Drawing.Size(890,900); $form.Font=$fontNormal; $form.BackColor=[Drawing.Color]::FromArgb(245,246,248)
$header = New-Object System.Windows.Forms.Panel; $header.Dock='Top'; $header.Height=65; $header.BackColor=[Drawing.Color]::White
$headTitle=New-Label $header 'HPNet PDF Downloader' 16 8 500 28 (New-Object Drawing.Font('Segoe UI',14,[Drawing.FontStyle]::Bold))
$headSub=New-Label $header 'Bật nhiều bộ lọc để kết hợp theo điều kiện AND' 18 38 700 22 $fontNormal; $headSub.ForeColor=[Drawing.Color]::DimGray
$main = New-Object System.Windows.Forms.FlowLayoutPanel; $main.Dock='Fill'; $main.FlowDirection='TopDown'; $main.WrapContents=$false; $main.AutoScroll=$true; $main.Padding=New-Object Windows.Forms.Padding(15)
$form.Controls.Add($main); $form.Controls.Add($header)

$group1=New-Object Windows.Forms.GroupBox; $group1.Text=' CẤU HÌNH TẢI '; $group1.Font=$fontBold; $group1.Size=New-Object Drawing.Size(860,150); $group1.Margin=New-Object Windows.Forms.Padding(0,0,0,12); $group1.BackColor=[Drawing.Color]::White; $main.Controls.Add($group1)
[void](New-Label $group1 'Trạng thái văn bản:' 20 32 150 25 $fontNormal)
$readFilterBox=New-Object Windows.Forms.ComboBox; $readFilterBox.Location=New-Object Drawing.Point(180,29); $readFilterBox.Size=New-Object Drawing.Size(655,26); $readFilterBox.DropDownStyle='DropDownList'; $readFilterBox.Font=$fontNormal
[void]$readFilterBox.Items.Add('Tất cả (không lọc chữ đậm)'); [void]$readFilterBox.Items.Add('Chỉ văn bản chữ đậm (chưa xem)'); [void]$readFilterBox.Items.Add('Chỉ văn bản không đậm (đã xem)')
$savedRead=if(Has-ConfigProperty $savedConfig 'readFilter'){[string]$savedConfig.readFilter}elseif($savedConfig.onlyUnread){'unread'}else{'all'}
$readFilterBox.SelectedIndex=if($savedRead -eq 'unread'){1}elseif($savedRead -eq 'read'){2}else{0}; $group1.Controls.Add($readFilterBox)
[void](New-Label $group1 'Mã xã (5 chữ số):' 20 69 150 25 $fontNormal)
$communeCodeBox=New-Object Windows.Forms.TextBox; $communeCodeBox.Location=New-Object Drawing.Point(180,66); $communeCodeBox.Size=New-Object Drawing.Size(180,25); $communeCodeBox.MaxLength=5; $communeCodeBox.Text=if($savedConfig.communeCode){[string]$savedConfig.communeCode}else{'10930'}; $group1.Controls.Add($communeCodeBox)
$missingCodeCheck=New-Object Windows.Forms.CheckBox; $missingCodeCheck.Text='Nhận thêm tên file không có mã xã'; $missingCodeCheck.Location=New-Object Drawing.Point(380,66); $missingCodeCheck.Size=New-Object Drawing.Size(455,25); $missingCodeCheck.Font=$fontNormal; $missingCodeCheck.Checked=if(Has-ConfigProperty $savedConfig 'allowMissingCommuneCode'){[bool]$savedConfig.allowMissingCommuneCode}else{$true}; $group1.Controls.Add($missingCodeCheck)
$formatLabel=New-Label $group1 '' 20 105 815 35 (New-Object Drawing.Font('Segoe UI',8.5,[Drawing.FontStyle]::Italic)); $formatLabel.ForeColor=[Drawing.Color]::DarkGreen

$group2=New-Object Windows.Forms.GroupBox; $group2.Text=' BỘ LỌC TÌM KIẾM - AND '; $group2.Font=$fontBold; $group2.Size=New-Object Drawing.Size(860,445); $group2.Margin=New-Object Windows.Forms.Padding(0,0,0,12); $group2.BackColor=[Drawing.Color]::White; $main.Controls.Add($group2)
$titleCheck=New-Object Windows.Forms.CheckBox; $titleCheck.Text='Lọc trích yếu chứa:'; $titleCheck.Location=New-Object Drawing.Point(20,34); $titleCheck.Size=New-Object Drawing.Size(205,25); $titleCheck.Checked=$savedTitleEnabled; $titleCheck.Font=$fontNormal; $group2.Controls.Add($titleCheck)
$titlesBox=New-Object Windows.Forms.TextBox; $titlesBox.Location=New-Object Drawing.Point(235,28); $titlesBox.Size=New-Object Drawing.Size(600,68); $titlesBox.Multiline=$true; $titlesBox.ScrollBars='Vertical'; $titlesBox.Text=if($savedConfig.allowedTitles){$savedConfig.allowedTitles -join [Environment]::NewLine}else{''}; $group2.Controls.Add($titlesBox)
$numberCheck=New-Object Windows.Forms.CheckBox; $numberCheck.Text='Lọc số thông báo:'; $numberCheck.Location=New-Object Drawing.Point(20,114); $numberCheck.Size=New-Object Drawing.Size(205,25); $numberCheck.Checked=$savedNumberEnabled; $numberCheck.Font=$fontNormal; $group2.Controls.Add($numberCheck)
$numbersBox=New-Object Windows.Forms.TextBox; $numbersBox.Location=New-Object Drawing.Point(235,106); $numbersBox.Size=New-Object Drawing.Size(600,68); $numbersBox.Multiline=$true; $numbersBox.ScrollBars='Vertical'; $numbersBox.Text=if($savedConfig.notificationNumbers){[string]$savedConfig.notificationNumbers}else{''}; $group2.Controls.Add($numbersBox)
$symbolCheck=New-Object Windows.Forms.CheckBox; $symbolCheck.Text='Lọc ký hiệu VB:'; $symbolCheck.Location=New-Object Drawing.Point(20,192); $symbolCheck.Size=New-Object Drawing.Size(205,25); $symbolCheck.Checked=$savedSymbolEnabled; $symbolCheck.Font=$fontNormal; $group2.Controls.Add($symbolCheck)
$symbolBox=New-Object Windows.Forms.TextBox; $symbolBox.Location=New-Object Drawing.Point(235,188); $symbolBox.Size=New-Object Drawing.Size(600,25); $symbolBox.Text=if($savedConfig.documentSymbols){[string]$savedConfig.documentSymbols}else{''}; $group2.Controls.Add($symbolBox)
$symbolHint=New-Label $group2 'Ví dụ: TB-ĐKĐĐ. So khớp toàn bộ ký hiệu sau chuẩn hóa để tránh tải nhầm.' 235 216 600 22 (New-Object Drawing.Font('Segoe UI',8.5,[Drawing.FontStyle]::Italic)); $symbolHint.ForeColor=[Drawing.Color]::DimGray
$dateCheck=New-Object Windows.Forms.CheckBox; $dateCheck.Text='Lọc ngày văn bản:'; $dateCheck.Location=New-Object Drawing.Point(20,251); $dateCheck.Size=New-Object Drawing.Size(205,25); $dateCheck.Checked=$savedDateEnabled; $dateCheck.Font=$fontNormal; $group2.Controls.Add($dateCheck)
$exactRadio=New-Object Windows.Forms.RadioButton; $exactRadio.Text='Đúng ngày'; $exactRadio.Location=New-Object Drawing.Point(235,249); $exactRadio.Size=New-Object Drawing.Size(110,25); $exactRadio.Font=$fontNormal; $group2.Controls.Add($exactRadio)
$rangeRadio=New-Object Windows.Forms.RadioButton; $rangeRadio.Text='Khoảng ngày'; $rangeRadio.Location=New-Object Drawing.Point(355,249); $rangeRadio.Size=New-Object Drawing.Size(130,25); $rangeRadio.Font=$fontNormal; $group2.Controls.Add($rangeRadio)
if ((Has-ConfigProperty $savedConfig 'dateMode') -and ([string]$savedConfig.dateMode -eq 'range')) { $rangeRadio.Checked=$true } else { $exactRadio.Checked=$true }
$exactLabel=New-Label $group2 'Ngày:' 235 290 60 25 $fontNormal
$exactPicker=New-Object Windows.Forms.DateTimePicker; $exactPicker.Location=New-Object Drawing.Point(295,285); $exactPicker.Size=New-Object Drawing.Size(175,25); $exactPicker.Format='Custom'; $exactPicker.CustomFormat='dd/MM/yyyy'; $exactPicker.Value=Get-SavedDate 'exactDate'; $group2.Controls.Add($exactPicker)
$startLabel=New-Label $group2 'Từ ngày:' 490 290 75 25 $fontNormal
$startPicker=New-Object Windows.Forms.DateTimePicker; $startPicker.Location=New-Object Drawing.Point(565,285); $startPicker.Size=New-Object Drawing.Size(125,25); $startPicker.Format='Custom'; $startPicker.CustomFormat='dd/MM/yyyy'; $startPicker.Value=Get-SavedDate 'startDate'; $group2.Controls.Add($startPicker)
$endLabel=New-Label $group2 'đến:' 700 290 40 25 $fontNormal
$endPicker=New-Object Windows.Forms.DateTimePicker; $endPicker.Location=New-Object Drawing.Point(740,285); $endPicker.Size=New-Object Drawing.Size(95,25); $endPicker.Format='Custom'; $endPicker.CustomFormat='dd/MM/yyyy'; $endPicker.Value=Get-SavedDate 'endDate'; $group2.Controls.Add($endPicker)
$filterSummary=New-Label $group2 '' 20 328 815 100 (New-Object Drawing.Font('Segoe UI',9,[Drawing.FontStyle]::Italic)); $filterSummary.ForeColor=[Drawing.Color]::DarkBlue

$group3=New-Object Windows.Forms.GroupBox; $group3.Text=' THƯ MỤC LƯU FILE '; $group3.Font=$fontBold; $group3.Size=New-Object Drawing.Size(860,80); $group3.Margin=New-Object Windows.Forms.Padding(0,0,0,12); $group3.BackColor=[Drawing.Color]::White; $main.Controls.Add($group3)
$folderBox=New-Object Windows.Forms.TextBox; $folderBox.Location=New-Object Drawing.Point(20,33); $folderBox.Size=New-Object Drawing.Size(650,25); $folderBox.Text=if($savedConfig.outputDir){[string]$savedConfig.outputDir}else{$defaultOutput}; $group3.Controls.Add($folderBox)
$browseButton=New-Object Windows.Forms.Button; $browseButton.Text='Chọn thư mục'; $browseButton.Location=New-Object Drawing.Point(685,30); $browseButton.Size=New-Object Drawing.Size(150,30); $browseButton.FlatStyle='Flat'; $browseButton.BackColor=[Drawing.Color]::White; $group3.Controls.Add($browseButton)

$actions=New-Object Windows.Forms.Panel; $actions.Size=New-Object Drawing.Size(860,45); $actions.Margin=New-Object Windows.Forms.Padding(0,0,0,12); $main.Controls.Add($actions)
$startButton=New-Object Windows.Forms.Button; $startButton.Text='BẮT ĐẦU QUÉT VÀ TẢI'; $startButton.Location=New-Object Drawing.Point(0,0); $startButton.Size=New-Object Drawing.Size(215,40); $startButton.Font=$fontBold; $startButton.BackColor=[Drawing.Color]::FromArgb(25,118,210); $startButton.ForeColor=[Drawing.Color]::White; $startButton.FlatStyle='Flat'; $startButton.FlatAppearance.BorderSize=0
$openFolderButton=New-Object Windows.Forms.Button; $openFolderButton.Text='Mở thư mục kết quả'; $openFolderButton.Location=New-Object Drawing.Point(230,0); $openFolderButton.Size=New-Object Drawing.Size(180,40); $openFolderButton.FlatStyle='Flat'; $openFolderButton.BackColor=[Drawing.Color]::White
$resetButton=New-Object Windows.Forms.Button; $resetButton.Text='Đặt lại bộ lọc'; $resetButton.Location=New-Object Drawing.Point(425,0); $resetButton.Size=New-Object Drawing.Size(150,40); $resetButton.FlatStyle='Flat'; $resetButton.BackColor=[Drawing.Color]::White
$stopButton=New-Object Windows.Forms.Button; $stopButton.Text='DỪNG AN TOÀN'; $stopButton.Location=New-Object Drawing.Point(590,0); $stopButton.Size=New-Object Drawing.Size(155,40); $stopButton.FlatStyle='Flat'; $stopButton.Enabled=$false
$actions.Controls.AddRange(@($startButton,$openFolderButton,$resetButton,$stopButton))
$logLabel=New-Object Windows.Forms.Label; $logLabel.Text='Nhật ký hoạt động:'; $logLabel.Font=$fontBold; $logLabel.AutoSize=$true; $logLabel.Margin=New-Object Windows.Forms.Padding(0,0,0,5); $main.Controls.Add($logLabel)
$statusBox=New-Object Windows.Forms.TextBox; $statusBox.Size=New-Object Drawing.Size(860,170); $statusBox.Multiline=$true; $statusBox.ScrollBars='Vertical'; $statusBox.ReadOnly=$true; $statusBox.Font=New-Object Drawing.Font('Consolas',9); $statusBox.BackColor=[Drawing.Color]::FromArgb(30,30,30); $statusBox.ForeColor=[Drawing.Color]::Gainsboro; $statusBox.Text="Sẵn sàng.`r`nBật các bộ lọc cần dùng; các nhóm đã bật được kết hợp theo AND."; $main.Controls.Add($statusBox)

$script:activeProcess=$null; $script:stopRequested=$false
function Stop-ActiveWorker {
    if (-not $script:activeProcess -or $script:activeProcess.HasExited) { return }
    $script:stopRequested=$true; $statusBox.Text='Đang dừng tiến trình và Edge do công cụ mở...'; $form.Refresh()
    try {
        $stopInfo=New-Object Diagnostics.ProcessStartInfo; $stopInfo.FileName=Join-Path $env:SystemRoot 'System32\taskkill.exe'; $stopInfo.Arguments="/PID $($script:activeProcess.Id) /T /F"; $stopInfo.UseShellExecute=$false; $stopInfo.CreateNoWindow=$true
        $stopProcess=[Diagnostics.Process]::Start($stopInfo); $stopProcess.WaitForExit()
    } catch { try { $script:activeProcess.Kill() } catch {} }
}

function Update-FilterUi {
    $titlesBox.Enabled=$titleCheck.Checked; $numbersBox.Enabled=$numberCheck.Checked; $symbolBox.Enabled=$symbolCheck.Checked
    $exactRadio.Enabled=$dateCheck.Checked; $rangeRadio.Enabled=$dateCheck.Checked
    $exactPicker.Enabled=($dateCheck.Checked -and $exactRadio.Checked); $exactLabel.Enabled=$exactPicker.Enabled
    $startPicker.Enabled=($dateCheck.Checked -and $rangeRadio.Checked); $endPicker.Enabled=$startPicker.Enabled; $startLabel.Enabled=$startPicker.Enabled; $endLabel.Enabled=$startPicker.Enabled
    $parts=New-Object 'System.Collections.Generic.List[string]'
    if($titleCheck.Checked){$count=@($titlesBox.Lines|Where-Object{-not[string]::IsNullOrWhiteSpace($_)}).Count;$parts.Add("Trích yếu chứa: $count giá trị")}
    if($numberCheck.Checked){try{$n=@(Parse-NotificationNumbers $numbersBox.Text);$parts.Add("Số thông báo: $($n.Count)")}catch{$parts.Add("Số thông báo: $($_.Exception.Message)")}}
    if($symbolCheck.Checked){$parts.Add("Ký hiệu VB chính xác: $((Parse-DocumentSymbols $symbolBox.Text).Count) giá trị")}
    if($dateCheck.Checked){if($exactRadio.Checked){$parts.Add("Đúng ngày: $($exactPicker.Value.ToString('dd/MM/yyyy'))")}else{$parts.Add("Khoảng ngày: $($startPicker.Value.ToString('dd/MM/yyyy')) - $($endPicker.Value.ToString('dd/MM/yyyy')) (gồm hai đầu)")}}
    if($readFilterBox.SelectedIndex -gt 0){$parts.Add("Trạng thái: $($readFilterBox.SelectedItem)")}
    $filterSummary.Text=if($parts.Count){"AND giữa các nhóm đã bật:`r`n"+($parts -join '  |  ')}else{'Chưa bật bộ lọc nào. Hãy bật ít nhất một trong 4 bộ lọc chính.'}
}

function Update-FileNameFormat {
    try{$code=Normalize-CommuneCode $communeCodeBox.Text;$formatLabel.Text="Nhận: CHUACOGIAY_${code}_{tờ}_{thửa}-TBXN.(signed/ldsigned/lsigned).pdf";if($missingCodeCheck.Checked){$formatLabel.Text+="`r`nNgoại lệ: CHUACOGIAY_{tờ}_{thửa}-TBXN.(signed/ldsigned/lsigned).pdf — giữ nguyên tên."};$formatLabel.ForeColor=[Drawing.Color]::DarkGreen}
    catch{$formatLabel.Text=$_.Exception.Message;$formatLabel.ForeColor=[Drawing.Color]::DarkRed}
}

@($titleCheck,$numberCheck,$symbolCheck,$dateCheck,$exactRadio,$rangeRadio,$readFilterBox)|ForEach-Object{$_.Add_Click({Update-FilterUi})}
$titlesBox.Add_TextChanged({Update-FilterUi});$numbersBox.Add_TextChanged({Update-FilterUi});$symbolBox.Add_TextChanged({Update-FilterUi});$exactPicker.Add_ValueChanged({Update-FilterUi});$startPicker.Add_ValueChanged({Update-FilterUi});$endPicker.Add_ValueChanged({Update-FilterUi});$communeCodeBox.Add_TextChanged({Update-FileNameFormat})
Update-FilterUi; Update-FileNameFormat
$missingCodeCheck.Add_CheckedChanged({Update-FileNameFormat})

$browseButton.Add_Click({$dialog=New-Object Windows.Forms.FolderBrowserDialog;$dialog.Description='Chọn thư mục lưu PDF tải từ HPNet';$dialog.SelectedPath=$folderBox.Text;if($dialog.ShowDialog() -eq [Windows.Forms.DialogResult]::OK){$folderBox.Text=$dialog.SelectedPath}})
$openFolderButton.Add_Click({if(Test-Path -LiteralPath $folderBox.Text){Start-Process explorer.exe -ArgumentList @($folderBox.Text)}})
$resetButton.Add_Click({$titleCheck.Checked=$false;$numberCheck.Checked=$false;$symbolCheck.Checked=$false;$dateCheck.Checked=$false;$readFilterBox.SelectedIndex=0;$titlesBox.Clear();$numbersBox.Clear();$symbolBox.Clear();$exactRadio.Checked=$true;$exactPicker.Value=[datetime]::Today;$startPicker.Value=[datetime]::Today;$endPicker.Value=[datetime]::Today;Update-FilterUi})
$stopButton.Add_Click({Stop-ActiveWorker})

$startButton.Add_Click({
    $titles=@($titlesBox.Lines|ForEach-Object{$_.Trim()}|Where-Object{$_});$symbols=@(Parse-DocumentSymbols $symbolBox.Text)
    if(-not($titleCheck.Checked -or $numberCheck.Checked -or $symbolCheck.Checked -or $dateCheck.Checked)){[Windows.Forms.MessageBox]::Show('Hãy bật ít nhất một bộ lọc chính.','Thiếu bộ lọc','OK','Warning')|Out-Null;return}
    if($titleCheck.Checked -and $titles.Count -eq 0){[Windows.Forms.MessageBox]::Show('Bộ lọc trích yếu đang bật nhưng chưa có nội dung.','Thiếu trích yếu','OK','Warning')|Out-Null;return}
    if($numberCheck.Checked){try{[void](Parse-NotificationNumbers $numbersBox.Text)}catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message,'Sai số thông báo','OK','Warning')|Out-Null;return}}
    if($symbolCheck.Checked -and $symbols.Count -eq 0){[Windows.Forms.MessageBox]::Show('Bộ lọc ký hiệu VB đang bật nhưng chưa có ký hiệu.','Thiếu ký hiệu','OK','Warning')|Out-Null;return}
    if($dateCheck.Checked -and $rangeRadio.Checked -and $startPicker.Value.Date -gt $endPicker.Value.Date){[Windows.Forms.MessageBox]::Show('Ngày bắt đầu phải nhỏ hơn hoặc bằng ngày kết thúc.','Sai khoảng ngày','OK','Warning')|Out-Null;return}
    if([string]::IsNullOrWhiteSpace($folderBox.Text)){[Windows.Forms.MessageBox]::Show('Hãy chọn thư mục lưu PDF.','Thiếu thư mục','OK','Warning')|Out-Null;return}
    try{$communeCode=Normalize-CommuneCode $communeCodeBox.Text}catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message,'Sai mã xã','OK','Warning')|Out-Null;return}
    try{
        [IO.Directory]::CreateDirectory($folderBox.Text)|Out-Null
        $readFilter=if($readFilterBox.SelectedIndex -eq 1){'unread'}elseif($readFilterBox.SelectedIndex -eq 2){'read'}else{'all'}
        $dateMode=if($rangeRadio.Checked){'range'}else{'exact'}
        $legacyMode=if($numberCheck.Checked -and -not $titleCheck.Checked -and -not $symbolCheck.Checked -and -not $dateCheck.Checked){'numbers'}else{'titles'}
        [ordered]@{configVersion=3;downloadMode=$legacyMode;titleFilterEnabled=$titleCheck.Checked;allowedTitles=$titles;notificationFilterEnabled=$numberCheck.Checked;notificationNumbers=$numbersBox.Text.Trim();symbolFilterEnabled=$symbolCheck.Checked;documentSymbols=$symbolBox.Text.Trim();dateFilterEnabled=$dateCheck.Checked;dateMode=$dateMode;exactDate=$exactPicker.Value.ToString('yyyy-MM-dd');startDate=$startPicker.Value.ToString('yyyy-MM-dd');endDate=$endPicker.Value.ToString('yyyy-MM-dd');communeCode=$communeCode;allowMissingCommuneCode=$missingCodeCheck.Checked;outputDir=$folderBox.Text;readFilter=$readFilter;onlyUnread=($readFilter -eq 'unread');listPageSize=100}|ConvertTo-Json -Depth 5|Set-Content -LiteralPath $configPath -Encoding UTF8
        Update-FilterUi
        $answer=[Windows.Forms.MessageBox]::Show("Microsoft Edge sẽ mở để bạn đăng nhập VNeID.`r`n`r`n$($filterSummary.Text)`r`n`r`nChỉ văn bản thỏa TẤT CẢ nhóm đã bật mới được tải.`r`nNgày lọc là NGÀY VĂN BẢN, không phải ngày upload. Chỉ quét mục VĂN BẢN ĐI.`r`nCSV ĐỐI SOÁT sẽ ghi cả các văn bản bị lọc.",'Xác nhận bộ lọc','OKCancel','Information')
        if($answer -ne [Windows.Forms.DialogResult]::OK){return}
        $allInputs=@($startButton,$browseButton,$resetButton,$titleCheck,$numberCheck,$symbolCheck,$dateCheck,$exactRadio,$rangeRadio,$readFilterBox,$titlesBox,$numbersBox,$symbolBox,$exactPicker,$startPicker,$endPicker,$communeCodeBox,$missingCodeCheck,$folderBox)
        $allInputs|ForEach-Object{$_.Enabled=$false};$stopButton.Enabled=$true;$script:stopRequested=$false;$statusBox.Text='Đang chạy... Nếu Edge hiện trang đăng nhập, hãy chọn VNeID và hoàn tất xác thực.';$form.Refresh()
        $psi=New-Object Diagnostics.ProcessStartInfo;$psi.FileName=$runtime.NodeExe;$psi.Arguments=('"{0}" "{1}"' -f $nodeScript,$configPath);$psi.UseShellExecute=$false;$psi.CreateNoWindow=$true;$psi.RedirectStandardOutput=$true;$psi.RedirectStandardError=$true;$psi.EnvironmentVariables['HPNET_NODE_MODULES']=$runtime.NodeModules;$psi.EnvironmentVariables['HPNET_EDGE_EXE']=$runtime.EdgeExe
        $process=New-Object Diagnostics.Process;$process.StartInfo=$psi;$process.Start()|Out-Null;$script:activeProcess=$process;$stdoutTask=$process.StandardOutput.ReadToEndAsync();$stderrTask=$process.StandardError.ReadToEndAsync()
        while(-not $process.HasExited){[Windows.Forms.Application]::DoEvents();Start-Sleep -Milliseconds 150}
        $statusText=($stdoutTask.Result+[Environment]::NewLine+$stderrTask.Result).Trim()
        if($script:stopRequested){$statusBox.Text="Đã dừng theo yêu cầu.`r`n$statusText";[Windows.Forms.MessageBox]::Show('Tiến trình đã được dừng theo yêu cầu.','Đã dừng','OK','Information')|Out-Null}
        elseif($process.ExitCode -eq 0){$statusBox.Text=$statusText;[Windows.Forms.MessageBox]::Show('Đã quét xong. Xem kết quả và nhật ký trong thư mục đã chọn.','Hoàn tất','OK','Information')|Out-Null}
        else{$statusBox.Text=$statusText;[Windows.Forms.MessageBox]::Show('Công cụ chưa hoàn tất. Xem nội dung lỗi ở khung phía dưới.','Chưa hoàn tất','OK','Warning')|Out-Null}
    }catch{$statusBox.Text=$_.Exception.ToString();[Windows.Forms.MessageBox]::Show($_.Exception.Message,'Lỗi','OK','Error')|Out-Null}
    finally{$script:activeProcess=$null;$stopButton.Enabled=$false;foreach($control in @($startButton,$browseButton,$resetButton,$titleCheck,$numberCheck,$symbolCheck,$dateCheck,$readFilterBox,$communeCodeBox,$missingCodeCheck,$folderBox)){$control.Enabled=$true};Update-FilterUi}
})

$form.Add_FormClosing({if($script:activeProcess -and -not $script:activeProcess.HasExited){Stop-ActiveWorker}})
if ($UiSelfTest) {
    $communeCodeBox.Text='10930'
    $missingCodeCheck.Checked=$true
    Update-FileNameFormat
    if ($formatLabel.Text -notmatch 'Ngoại lệ: CHUACOGIAY_') { throw 'UI test: thiếu hướng dẫn ngoại lệ.' }
    $missingCodeCheck.Checked=$false
    if ($formatLabel.Text -match 'Ngoại lệ:') { throw 'UI test: tắt ngoại lệ không cập nhật.' }
    $missingCodeCheck.Checked=$true
    $form.StartPosition='Manual'; $form.Location=New-Object Drawing.Point(-32000,-32000); $form.ShowInTaskbar=$false
    $form.Show(); $form.PerformLayout(); [Windows.Forms.Application]::DoEvents()
    if ($missingCodeCheck.Right -gt $group1.ClientSize.Width) { throw 'UI test: checkbox tràn khung.' }
    if ($formatLabel.Top -lt $missingCodeCheck.Bottom) { throw 'UI test: hướng dẫn chồng checkbox.' }
    if ($TestImagePath) {
        $bitmap=New-Object Drawing.Bitmap($form.Width,$form.Height)
        try { $form.DrawToBitmap($bitmap,(New-Object Drawing.Rectangle(0,0,$form.Width,$form.Height))); $bitmap.Save($TestImagePath,[Drawing.Imaging.ImageFormat]::Png) }
        finally { $bitmap.Dispose() }
    }
    $form.Dispose()
    Write-Output 'UI_SELF_TEST_OK: ngoại lệ bật/tắt, hướng dẫn, bố cục; không mở Edge và không sửa cấu hình.'
    exit 0
}
[void]$form.ShowDialog()
