param([switch]$SelfTest, [switch]$UiSelfTest, [string]$TestImagePath)

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$toolRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path (Split-Path -Parent (Split-Path -Parent $toolRoot)) 'hpnet_ui_common.ps1')
$nodeScript = Join-Path $toolRoot 'hpnet-upload-draft.cjs'
$configPath = Join-Path $toolRoot 'cau_hinh.json'
$profilesPath = Join-Path $toolRoot 'profiles.json'

function Find-HPNetRuntime {
    param([switch]$SkipBrowserCheck)
    # Runtime dùng chung tại nodes_tools/runtime/ — duy nhất, không fallback vào runtime riêng từng tool.
    $sharedRuntime = Join-Path (Split-Path -Parent (Split-Path -Parent $toolRoot)) 'runtime'
    if ((Test-Path -LiteralPath (Join-Path $sharedRuntime 'node.exe')) -and
        (Test-Path -LiteralPath (Join-Path $sharedRuntime 'node_modules\playwright'))) {
        $nodeExe = Join-Path $sharedRuntime 'node.exe'
        $nodeModules = Join-Path $sharedRuntime 'node_modules'
        $runtimeMode = 'Portable dùng chung'
    } else {
        throw 'Không tìm thấy runtime Node/Playwright dùng chung. Hãy dùng gói PORTABLE đúng phiên bản.'
    }

    $edgeCandidates = @(
        'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
        'C:\Program Files\Microsoft\Edge\Application\msedge.exe'
    )
    $edgeExe = $edgeCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $edgeExe -and -not $SkipBrowserCheck) { throw 'Không tìm thấy Microsoft Edge.' }
    return [PSCustomObject]@{ NodeExe=$nodeExe; NodeModules=$nodeModules; EdgeExe=$edgeExe; Mode=$runtimeMode }
}

try { $runtime = Find-HPNetRuntime -SkipBrowserCheck:($SelfTest -or $UiSelfTest) } catch {
    if ($SelfTest -or $UiSelfTest) { throw }
    [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'HPNet Upload VB dự thảo', 'OK', 'Error') | Out-Null
    exit 1
}

if ($SelfTest) {
    [PSCustomObject]@{
        ToolRoot=$toolRoot
        NodeScriptExists=(Test-Path -LiteralPath $nodeScript)
        NodeExe=$runtime.NodeExe
        NodeModules=$runtime.NodeModules
        EdgeExe=$runtime.EdgeExe
        RuntimeMode=$runtime.Mode
    } | ConvertTo-Json
    exit 0
}

function Parse-UploadBatches([string[]]$lines) {
    return @($lines | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | ForEach-Object {
        $parts = $_ -split '\|', 2
        [ordered]@{ folder = $parts[0].Trim(); abstract = if ($parts.Count -eq 2) { $parts[1].Trim() } else { '' } }
    })
}

$stateRoot = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'HPNet VBDLIS AIO Tool\Upload'
New-Item -ItemType Directory -Force -Path $stateRoot | Out-Null
$appRoot = $toolRoot; 1..4 | ForEach-Object { $appRoot = Split-Path -Parent $appRoot }
$previousToolRoot = Join-Path (Join-Path (Split-Path -Parent $appRoot) 'HPNET & VBDLIS Tools.previous') '_internal\nodes_tools\Upload\HPNet Upload VB Du Thao - VNEID APP'
foreach ($name in @('cau_hinh.json','profiles.json','du_lieu_dang_nhap_vneid','nhat_ky','trang_thai_da_up.json')) {
    $saved = Join-Path $stateRoot $name
    foreach ($legacyRoot in @($toolRoot,$previousToolRoot)) {
        $legacy = Join-Path $legacyRoot $name
        if ((Test-Path -LiteralPath $legacy) -and -not (Test-Path -LiteralPath $saved)) { Copy-Item -LiteralPath $legacy -Destination $saved -Recurse }
    }
}
$configPath = Join-Path $stateRoot 'cau_hinh.json'
$profilesPath = Join-Path $stateRoot 'profiles.json'

function Read-JsonSafe([string]$path) {
    if (-not (Test-Path -LiteralPath $path)) { return $null }
    try { return Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json } catch { return $null }
}

function Get-ProfileNames($store) {
    if (-not $store -or -not $store.profiles) { return @() }
    return @($store.profiles.PSObject.Properties | ForEach-Object { $_.Name } | Sort-Object)
}

function Get-ProfileEntry($store, [string]$name) {
    if (-not $store -or -not $store.profiles -or [string]::IsNullOrWhiteSpace($name)) { return $null }
    $property = $store.profiles.PSObject.Properties | Where-Object { $_.Name -eq $name } | Select-Object -First 1
    if ($property) { return $property.Value }
    return $null
}

function Save-ProfileStore([string]$selectedName, [string]$reviewerLevel1) {
    $map = [ordered]@{}
    foreach ($name in @(Get-ProfileNames $script:profileStore)) {
        $entry = Get-ProfileEntry $script:profileStore $name
        $map[$name] = [ordered]@{
            displayName = if ($entry.displayName) { [string]$entry.displayName } else { $name }
            reviewerLevel1 = [string]$entry.reviewerLevel1
            reviewerLevel2 = [string]$entry.reviewerLevel2
        }
    }
    $oldEntry = Get-ProfileEntry $script:profileStore $selectedName
    $map[$selectedName] = [ordered]@{
        displayName = $selectedName
        reviewerLevel1 = $reviewerLevel1
        reviewerLevel2 = if ($oldEntry) { [string]$oldEntry.reviewerLevel2 } else { '' }
    }
    [ordered]@{ lastProfile=$selectedName; profiles=$map } | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $profilesPath -Encoding UTF8
    $script:profileStore = Read-JsonSafe $profilesPath
}

$savedConfig = Read-JsonSafe $configPath
if (-not $savedConfig) {
    [ordered]@{
        profileName = ''
        abstract = ''
        sourceFolder = ''
        reviewerLevel1 = ''
        dryRun = $false
        reuploadModified = $true
        listPageSize = 100
    } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $configPath -Encoding UTF8
    $savedConfig = Read-JsonSafe $configPath
}
$profileStore = Read-JsonSafe $profilesPath
if (-not $profileStore -or -not $profileStore.PSObject.Properties['profiles']) {
    [ordered]@{ lastProfile=''; profiles=[ordered]@{} } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $profilesPath -Encoding UTF8
    $profileStore = Read-JsonSafe $profilesPath
}
$initialProfile = if ($savedConfig -and $savedConfig.profileName) { [string]$savedConfig.profileName } elseif ($profileStore.lastProfile) { [string]$profileStore.lastProfile } else { @(Get-ProfileNames $profileStore | Select-Object -First 1)[0] }
$initialEntry = Get-ProfileEntry $profileStore $initialProfile
$initialReviewer = if ($savedConfig -and $savedConfig.reviewerLevel1) { [string]$savedConfig.reviewerLevel1 } elseif ($initialEntry) { [string]$initialEntry.reviewerLevel1 } else { '' }

[System.Windows.Forms.Application]::EnableVisualStyles()
$form = New-Object System.Windows.Forms.Form
$form.Text = 'HPNet - Tự động tải lên văn bản dự thảo'
$form.StartPosition = 'CenterScreen'
$form.Size = New-Object System.Drawing.Size(1420, 900)
$form.MinimumSize = New-Object System.Drawing.Size(1240, 820)
$form.Font = New-Object System.Drawing.Font('Segoe UI', 9.75)
$form.BackColor = [System.Drawing.Color]::FromArgb(245, 246, 248)
Set-HPNetWindowIdentity -Form $form -ToolRoot $toolRoot -AppId 'HPNET.VBDLIS.Tools.Upload'

$headerPanel = New-Object System.Windows.Forms.Panel
$headerPanel.Dock = 'Top'
$headerPanel.Height = 60
$headerPanel.BackColor = [System.Drawing.Color]::White

$title = New-Object System.Windows.Forms.Label
$title.Location = New-Object System.Drawing.Point(15, 10)
$title.AutoSize = $true
$title.Font = New-Object System.Drawing.Font('Segoe UI', 14, [System.Drawing.FontStyle]::Bold)
$title.ForeColor = [System.Drawing.Color]::FromArgb(41, 50, 60)
$title.Text = 'HPNet Upload văn bản dự thảo'
$headerPanel.Controls.Add($title)

$subtitle = New-Object System.Windows.Forms.Label
$subtitle.Location = New-Object System.Drawing.Point(17, 35)
$subtitle.AutoSize = $true
$subtitle.Font = New-Object System.Drawing.Font('Segoe UI', 9)
$subtitle.ForeColor = [System.Drawing.Color]::FromArgb(100, 100, 100)
$subtitle.Text = 'Tự động hóa quy trình tải văn bản dự thảo lên HPNet'
$headerPanel.Controls.Add($subtitle)

$mainPanel = New-Object System.Windows.Forms.Panel
$mainPanel.Dock = 'Fill'
$mainPanel.Padding = New-Object System.Windows.Forms.Padding(15)
$contentPanel = New-Object System.Windows.Forms.Panel
$contentPanel.Dock = 'Fill'
$contentPanel.BackColor = [System.Drawing.Color]::FromArgb(245, 246, 248)
$contentPanel.Controls.Add($mainPanel)
$form.Controls.Add($contentPanel)
$form.Controls.Add($headerPanel)

# CARD 1: NGUỒN DỮ LIỆU
$group1 = New-Object System.Windows.Forms.GroupBox
$group1.Text = ' NGUỒN DỮ LIỆU '
$group1.Font = New-Object System.Drawing.Font('Segoe UI', 9.75, [System.Drawing.FontStyle]::Bold)
$group1.Size = New-Object System.Drawing.Size(830, 200)
$group1.Margin = New-Object System.Windows.Forms.Padding(0, 0, 0, 15)
$group1.BackColor = [System.Drawing.Color]::White
$mainPanel.Controls.Add($group1)

$fontNormal = New-Object System.Drawing.Font('Segoe UI', 9.75)

$profileLabel = New-Object System.Windows.Forms.Label
$profileLabel.Text = 'Đơn vị / Profile:'
$profileLabel.Location = New-Object System.Drawing.Point(20, 35)
$profileLabel.AutoSize = $true
$profileLabel.Font = $fontNormal
$group1.Controls.Add($profileLabel)

$profileBox = New-Object System.Windows.Forms.ComboBox
$profileBox.Location = New-Object System.Drawing.Point(150, 32)
$profileBox.Size = New-Object System.Drawing.Size(480, 25)
$profileBox.DropDownStyle = 'DropDown'
$profileBox.Font = $fontNormal
foreach ($name in @(Get-ProfileNames $profileStore)) { [void]$profileBox.Items.Add($name) }
$profileBox.Text = $initialProfile
$group1.Controls.Add($profileBox)

$saveProfileButton = New-Object System.Windows.Forms.Button
$saveProfileButton.Text = 'Lưu Profile'
$saveProfileButton.Location = New-Object System.Drawing.Point(650, 31)
$saveProfileButton.Size = New-Object System.Drawing.Size(160, 28)
$saveProfileButton.Font = $fontNormal
$saveProfileButton.BackColor = [System.Drawing.Color]::White
$saveProfileButton.FlatStyle = 'Flat'
$group1.Controls.Add($saveProfileButton)

$folderLabel = New-Object System.Windows.Forms.Label
$folderLabel.Text = 'Danh sách upload:'
$folderLabel.Location = New-Object System.Drawing.Point(20, 75)
$folderLabel.AutoSize = $true
$folderLabel.Font = $fontNormal
$group1.Controls.Add($folderLabel)

$folderBox = New-Object System.Windows.Forms.TextBox
$folderBox.Location = New-Object System.Drawing.Point(150, 72)
$folderBox.Size = New-Object System.Drawing.Size(480, 65)
$folderBox.Multiline = $true
$folderBox.ScrollBars = 'Vertical'
$folderBox.Font = $fontNormal
$folderBox.Text = if ($savedConfig -and $savedConfig.batches) { (@($savedConfig.batches) | ForEach-Object { "$($_.folder) | $($_.abstract)" }) -join "`r`n" } elseif ($savedConfig -and $savedConfig.sourceFolder) { "$( $savedConfig.sourceFolder ) | $( $savedConfig.abstract )" } else { '' }
$group1.Controls.Add($folderBox)

$browseButton = New-Object System.Windows.Forms.Button
$browseButton.Text = 'Thêm thư mục'
$browseButton.Location = New-Object System.Drawing.Point(650, 71)
$browseButton.Size = New-Object System.Drawing.Size(160, 28)
$browseButton.Font = $fontNormal
$browseButton.BackColor = [System.Drawing.Color]::White
$browseButton.FlatStyle = 'Flat'
$group1.Controls.Add($browseButton)

$abstractLabel = New-Object System.Windows.Forms.Label
$abstractLabel.Text = 'Trích yếu chung:'
$abstractLabel.Visible = $false
$abstractLabel.AutoSize = $true
$abstractLabel.Font = $fontNormal
$group1.Controls.Add($abstractLabel)

$abstractBox = New-Object System.Windows.Forms.TextBox
$abstractBox.Visible = $false
$abstractBox.Size = New-Object System.Drawing.Size(660, 65)
$abstractBox.Multiline = $true
$abstractBox.ScrollBars = 'Vertical'
$abstractBox.Font = $fontNormal
$abstractBox.Text = if ($savedConfig -and $savedConfig.abstract) { [string]$savedConfig.abstract } else { '' }
$group1.Controls.Add($abstractBox)


# CARD 2: LUỒNG XỬ LÝ
$group2 = New-Object System.Windows.Forms.GroupBox
$group2.Text = ' LUỒNG XỬ LÝ '
$group2.Font = New-Object System.Drawing.Font('Segoe UI', 9.75, [System.Drawing.FontStyle]::Bold)
$group2.Size = New-Object System.Drawing.Size(830, 95)
$group2.Margin = New-Object System.Windows.Forms.Padding(0, 0, 0, 15)
$group2.BackColor = [System.Drawing.Color]::White
$mainPanel.Controls.Add($group2)

$reviewerLabel = New-Object System.Windows.Forms.Label
$reviewerLabel.Text = 'Người duyệt (Cấp 1):'
$reviewerLabel.Location = New-Object System.Drawing.Point(20, 35)
$reviewerLabel.AutoSize = $true
$reviewerLabel.Font = $fontNormal
$group2.Controls.Add($reviewerLabel)

$reviewerBox = New-Object System.Windows.Forms.TextBox
$reviewerBox.Location = New-Object System.Drawing.Point(150, 32)
$reviewerBox.Size = New-Object System.Drawing.Size(660, 25)
$reviewerBox.Font = $fontNormal
$reviewerBox.Text = $initialReviewer
$group2.Controls.Add($reviewerBox)

$previewLabel = New-Object System.Windows.Forms.Label
$previewLabel.Location = New-Object System.Drawing.Point(150, 65)
$previewLabel.Size = New-Object System.Drawing.Size(660, 20)
$previewLabel.Font = New-Object System.Drawing.Font('Segoe UI', 8.5, [System.Drawing.FontStyle]::Italic)
$previewLabel.ForeColor = [System.Drawing.Color]::Gray
$group2.Controls.Add($previewLabel)


# CARD 3: CẤU HÌNH BỔ SUNG
$group3 = New-Object System.Windows.Forms.GroupBox
$group3.Text = ' CẤU HÌNH BỔ SUNG '
$group3.Font = New-Object System.Drawing.Font('Segoe UI', 9.75, [System.Drawing.FontStyle]::Bold)
$group3.Size = New-Object System.Drawing.Size(830, 85)
$group3.Margin = New-Object System.Windows.Forms.Padding(0, 0, 0, 15)
$group3.BackColor = [System.Drawing.Color]::White
$mainPanel.Controls.Add($group3)

$reuploadModified = New-Object System.Windows.Forms.CheckBox
$reuploadModified.Text = 'Tải lại tệp đã chỉnh sửa (bỏ qua tệp cũ, không tải trùng)'
$reuploadModified.Location = New-Object System.Drawing.Point(20, 30)
$reuploadModified.AutoSize = $true
$reuploadModified.Font = $fontNormal
$reuploadModified.Checked = if ($savedConfig -and $null -ne $savedConfig.reuploadModified) { [bool]$savedConfig.reuploadModified } else { $true }
$group3.Controls.Add($reuploadModified)

$dryRun = New-Object System.Windows.Forms.CheckBox
$dryRun.Text = 'Chế độ kiểm tra (chỉ xác thực, không tải lên)'
$dryRun.Location = New-Object System.Drawing.Point(20, 55)
$dryRun.AutoSize = $true
$dryRun.Font = $fontNormal
$dryRun.Checked = $false
$group3.Controls.Add($dryRun)


# ACTION BAR
$actionBar = New-Object System.Windows.Forms.Panel
$actionBar.Size = New-Object System.Drawing.Size(830, 45)
$actionBar.Margin = New-Object System.Windows.Forms.Padding(0, 0, 0, 15)
$mainPanel.Controls.Add($actionBar)

$startButton = New-Object System.Windows.Forms.Button
$startButton.Text = 'BẮT ĐẦU TẢI LÊN'
$startButton.Location = New-Object System.Drawing.Point(0, 0)
$startButton.Size = New-Object System.Drawing.Size(200, 40)
$startButton.Font = New-Object System.Drawing.Font('Segoe UI', 10, [System.Drawing.FontStyle]::Bold)
$startButton.BackColor = [System.Drawing.Color]::FromArgb(0, 120, 215)
$startButton.ForeColor = [System.Drawing.Color]::White
$startButton.FlatStyle = 'Flat'
$startButton.FlatAppearance.BorderSize = 0
$actionBar.Controls.Add($startButton)

$openLogButton = New-Object System.Windows.Forms.Button
$openLogButton.Text = 'Mở thư mục nhật ký'
$openLogButton.Location = New-Object System.Drawing.Point(215, 0)
$openLogButton.Size = New-Object System.Drawing.Size(160, 40)
$openLogButton.Font = $fontNormal
$openLogButton.BackColor = [System.Drawing.Color]::White
$openLogButton.FlatStyle = 'Flat'
$actionBar.Controls.Add($openLogButton)

$stopButton = New-Object System.Windows.Forms.Button
$stopButton.Text = 'DỪNG TÁC VỤ'
$stopButton.Location = New-Object System.Drawing.Point(390, 0)
$stopButton.Size = New-Object System.Drawing.Size(160, 40)
$stopButton.Font = $fontNormal
$stopButton.BackColor = [System.Drawing.Color]::FromArgb(230, 230, 230)
$stopButton.FlatStyle = 'Flat'
$stopButton.Enabled = $false
$actionBar.Controls.Add($stopButton)


# LOG PANEL
$logLabel = New-Object System.Windows.Forms.Label
$logLabel.Text = 'Nhật ký hoạt động:'
$logLabel.Font = New-Object System.Drawing.Font('Segoe UI', 9.75, [System.Drawing.FontStyle]::Bold)
$logLabel.AutoSize = $true
$logLabel.Margin = New-Object System.Windows.Forms.Padding(0, 0, 0, 5)
$mainPanel.Controls.Add($logLabel)

$progressPanel = New-Object System.Windows.Forms.Panel
$progressPanel.Size = New-Object System.Drawing.Size(830, 32)
$progressPanel.Margin = New-Object System.Windows.Forms.Padding(0, 0, 0, 5)
$mainPanel.Controls.Add($progressPanel)
$progressLabel = New-Object System.Windows.Forms.Label
$progressLabel.Text = 'Sẵn sàng'
$progressLabel.Location = New-Object System.Drawing.Point(0, 7)
$progressLabel.Size = New-Object System.Drawing.Size(185, 20)
$progressLabel.Font = New-Object System.Drawing.Font('Segoe UI', 9)
$progressPanel.Controls.Add($progressLabel)
$progressBar = New-Object System.Windows.Forms.ProgressBar
$progressBar.Location = New-Object System.Drawing.Point(190, 7)
$progressBar.Size = New-Object System.Drawing.Size(640, 20)
$progressBar.Minimum = 0
$progressBar.Maximum = 1
$progressBar.Value = 0
$progressBar.Style = 'Continuous'
$progressBar.AccessibleName = 'Tiến độ upload'
$progressPanel.Controls.Add($progressBar)

$statusBox = New-Object System.Windows.Forms.TextBox
$statusBox.Size = New-Object System.Drawing.Size(830, 180)
$statusBox.Multiline = $true
$statusBox.ScrollBars = 'Vertical'
$statusBox.ReadOnly = $true
$statusBox.Font = New-Object System.Drawing.Font('Consolas', 9.5)
$statusBox.BackColor = [System.Drawing.Color]::FromArgb(30, 30, 30)
$statusBox.ForeColor = [System.Drawing.Color]::FromArgb(200, 200, 200)
$statusBox.Text = "Sẵn sàng thực hiện.`r`nCông cụ sẽ rà soát toàn bộ danh sách HPNet, bỏ qua tệp đã tồn tại và lần lượt tải lên các tệp còn lại."
$mainPanel.Controls.Add($statusBox)

$footerLabel = New-HPNetFooter -Form $form -Text 'Sẵn sàng thực hiện'
$uiWorkspace = New-HPNetSplitWorkspace -MainPanel $mainPanel -InputControls @($group1, $group2, $group3, $actionBar) -ProgressPanel $progressPanel -LogLabel $logLabel -StatusBox $statusBox -ActivityTitle 'PHIÊN UPLOAD' -ActivityHint 'Theo dõi tiến độ, thông báo và nhật ký của phiên upload hiện tại.'

$script:activeProcess = $null
$script:stopRequested = $false

function Stop-ActiveWorker {
    if (-not $script:activeProcess -or $script:activeProcess.HasExited) { return }
    $script:stopRequested = $true
    Set-HPNetFooterState $footerLabel 'Đang dừng tiến trình…' 'Stopped'
    $statusBox.Text = 'Đang dừng tiến trình và Edge do công cụ mở...'
    Set-HPNetProgressStopped $progressBar $progressLabel 'Đang dừng…'
    $form.Refresh()
    try {
        $stopInfo = New-Object System.Diagnostics.ProcessStartInfo
        $stopInfo.FileName = (Join-Path $env:SystemRoot 'System32\taskkill.exe')
        $stopInfo.Arguments = "/PID $($script:activeProcess.Id) /T /F"
        $stopInfo.UseShellExecute = $false
        $stopInfo.CreateNoWindow = $true
        $stopProcess = [System.Diagnostics.Process]::Start($stopInfo)
        $stopProcess.WaitForExit()
    } catch {
        try { $script:activeProcess.Kill() } catch { }
    }
}


# EVENT HANDLERS
$browseButton.Add_Click({
    $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
    $dialog.Description = 'Chọn thêm thư mục chứa các file Word cần up'
    if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
        $newLine = "$($dialog.SelectedPath) | "
        $folderBox.Text = if ([string]::IsNullOrWhiteSpace($folderBox.Text)) { $newLine } else { "$($folderBox.Text.TrimEnd())`r`n$newLine" }
        $folderBox.SelectionStart = $folderBox.TextLength
        $folderBox.Focus()
    }
})

$openLogButton.Add_Click({
    $logDir = Join-Path $stateRoot 'nhat_ky'
    if (-not (Test-Path -LiteralPath $logDir)) { [System.IO.Directory]::CreateDirectory($logDir) | Out-Null }
    Start-Process explorer.exe -ArgumentList @($logDir)
})

$stopButton.Add_Click({ Stop-ActiveWorker })

function Update-WorkflowPreview {
    $previewLabel.Text = "Profile: $($profileBox.Text.Trim())    |    Người duyệt: $($reviewerBox.Text.Trim())"
}

$profileBox.Add_SelectedIndexChanged({
    $entry = Get-ProfileEntry $script:profileStore $profileBox.Text
    if ($entry) { $reviewerBox.Text = [string]$entry.reviewerLevel1 }
    Update-WorkflowPreview
})

$reviewerBox.Add_TextChanged({ Update-WorkflowPreview })

$saveProfileButton.Add_Click({
    $profileName = $profileBox.Text.Trim()
    $reviewer = $reviewerBox.Text.Trim()
    if ([string]::IsNullOrWhiteSpace($profileName)) {
        [System.Windows.Forms.MessageBox]::Show('Vui lòng nhập tên Đơn vị / Profile.', 'Thiếu profile', 'OK', 'Warning') | Out-Null
        return
    }
    if ([string]::IsNullOrWhiteSpace($reviewer)) {
        [System.Windows.Forms.MessageBox]::Show('Vui lòng nhập Người duyệt cấp 1 / lãnh đạo.', 'Thiếu người duyệt', 'OK', 'Warning') | Out-Null
        return
    }
    try {
        Save-ProfileStore $profileName $reviewer
        if (-not $profileBox.Items.Contains($profileName)) { [void]$profileBox.Items.Add($profileName) }
        [System.Windows.Forms.MessageBox]::Show("Đã lưu profile $profileName.", 'Đã lưu cấu hình', 'OK', 'Information') | Out-Null
    } catch {
        [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'Không lưu được profile', 'OK', 'Error') | Out-Null
    }
})
Update-WorkflowPreview

$startButton.Add_Click({
    $lines = @($folderBox.Lines | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    $batches = @(Parse-UploadBatches $lines)
    $folder = if ($batches.Count) { [string]$batches[0].folder } else { '' }
    $abstract = if ($batches.Count) { (($batches | ForEach-Object { $_.abstract }) -join '; ') } else { '' }
    $reviewer = $reviewerBox.Text.Trim()
    if ($batches.Count -eq 0) {
        [System.Windows.Forms.MessageBox]::Show('Hãy nhập ít nhất một thư mục theo dạng: C:\DuThao | Trích yếu.', 'Thiếu thư mục', 'OK', 'Warning') | Out-Null
        return
    }
    $invalidFolder = @($batches | Where-Object { -not (Test-Path -LiteralPath $_.folder -PathType Container) })
    if ($invalidFolder.Count -gt 0) {
        [System.Windows.Forms.MessageBox]::Show("Không tìm thấy thư mục: $($invalidFolder[0].folder)", 'Sai thư mục', 'OK', 'Warning') | Out-Null
        return
    }
    if (@($batches | Where-Object { [string]::IsNullOrWhiteSpace($_.abstract) }).Count -gt 0) {
        [System.Windows.Forms.MessageBox]::Show('Mỗi thư mục phải có trích yếu riêng sau dấu |.', 'Thiếu trích yếu', 'OK', 'Warning') | Out-Null
        return
    }
    if ([string]::IsNullOrWhiteSpace($reviewer)) {
        [System.Windows.Forms.MessageBox]::Show('Vui lòng nhập Người duyệt cấp 1 / lãnh đạo.', 'Thiếu người duyệt', 'OK', 'Warning') | Out-Null
        return
    }
    $wordFiles = @($batches | ForEach-Object { Get-ChildItem -LiteralPath $_.folder -File | Where-Object { $_.Name -notlike '~$*' -and $_.Extension -match '^\.docx?$' } })
    if ($wordFiles.Count -eq 0) {
        [System.Windows.Forms.MessageBox]::Show('Thư mục không có file .doc hoặc .docx.', 'Không có file Word', 'OK', 'Warning') | Out-Null
        return
    }

    $modeText = if ($dryRun.Checked) { 'CHỈ KIỂM TRA, KHÔNG UP' } else { 'UP THẬT LÊN HPNET' }
    $reuploadText = if ($reuploadModified.Checked) { 'Có - bỏ qua bản cũ, up lại bản đã sửa' } else { 'Không - thấy cùng tên là bỏ qua' }
    $message = "Chế độ: $modeText`r`nProfile: $($profileBox.Text.Trim())`r`nSố thư mục: $($batches.Count)`r`nSố file Word: $($wordFiles.Count)`r`nUp lại file đã sửa: $reuploadText`r`nNgười duyệt cấp 1 / lãnh đạo: $reviewer`r`nVị trí: Văn bản trình duyệt (*)`r`n`r`nCác thư mục và trích yếu:`r`n$($lines -join "`r`n")`r`n`r`nTiếp tục?"
    $answer = [System.Windows.Forms.MessageBox]::Show($message, 'Xác nhận chạy công cụ', 'OKCancel', 'Information')
    if ($answer -ne [System.Windows.Forms.DialogResult]::OK) { return }

    try {
        $config = [ordered]@{ profileName=$profileBox.Text.Trim(); abstract=$abstract; batches=$batches; sourceFolder=$folder; reviewerLevel1=$reviewer; dryRun=[bool]$dryRun.Checked; reuploadModified=[bool]$reuploadModified.Checked; listPageSize=100 }
        $config | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $configPath -Encoding UTF8

        $startButton.Enabled = $false
        $browseButton.Enabled = $false
        $folderBox.Enabled = $false
        $profileBox.Enabled = $false
        $reviewerBox.Enabled = $false
        $saveProfileButton.Enabled = $false
        $script:stopRequested = $false
        $stopButton.Enabled = $true
        Set-HPNetFooterState $footerLabel 'Đang xử lý — không đóng cửa sổ' 'Running'
        $statusBox.Text = 'Đang chạy. Nếu Edge hiện trang đăng nhập, hãy chọn VNeID và hoàn tất xác thực; công cụ sẽ tự chạy tiếp. Không đóng Edge cho đến khi công cụ báo xong.'
        $form.Refresh()

        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $runtime.NodeExe
        $psi.Arguments = ('"{0}" "{1}"' -f $nodeScript, $configPath)
        $psi.UseShellExecute = $false
        $psi.CreateNoWindow = $true
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
        $psi.StandardOutputEncoding = $utf8NoBom
        $psi.StandardErrorEncoding = $utf8NoBom
        $psi.EnvironmentVariables['HPNET_NODE_MODULES'] = $runtime.NodeModules
        $psi.EnvironmentVariables['HPNET_EDGE_EXE'] = $runtime.EdgeExe

        $process = New-Object System.Diagnostics.Process
        $process.StartInfo = $psi
        $process.Start() | Out-Null
        $script:activeProcess = $process
        Set-HPNetProgressRunning $progressBar $progressLabel 'Đang quét HPNet…'
        $script:liveOutput = New-Object System.Collections.Concurrent.ConcurrentQueue[string]
        $process.add_OutputDataReceived({ param($sender, $event); if ($null -ne $event.Data) { [void]$script:liveOutput.Enqueue($event.Data) } })
        $process.add_ErrorDataReceived({ param($sender, $event); if ($null -ne $event.Data) { [void]$script:liveOutput.Enqueue("[LỖI] $($event.Data)") } })
        $process.BeginOutputReadLine()
        $process.BeginErrorReadLine()
        while (-not $process.HasExited) {
            [System.Windows.Forms.Application]::DoEvents()
            $statusBox.Lines = @($script:liveOutput.ToArray())
            foreach ($line in @($script:liveOutput.ToArray())) { Update-HPNetProgressFromLine $progressBar $progressLabel $line }
            $statusBox.SelectionStart = $statusBox.TextLength
            $statusBox.ScrollToCaret()
            Start-Sleep -Milliseconds 150
        }
        $process.WaitForExit()
        $statusText = (@($script:liveOutput.ToArray()) -join [Environment]::NewLine).Trim()
        if ($script:stopRequested) {
            Set-HPNetProgressStopped $progressBar $progressLabel 'Đã dừng theo yêu cầu'
            Set-HPNetFooterState $footerLabel 'Đã dừng theo yêu cầu' 'Stopped'
            $statusBox.Text = if ($statusText) { "Đã dừng theo yêu cầu.`r`n$statusText" } else { 'Đã dừng theo yêu cầu.' }
            [System.Windows.Forms.MessageBox]::Show('Tiến trình đã được dừng theo yêu cầu.', 'Đã dừng', 'OK', 'Information') | Out-Null
        } elseif ($process.ExitCode -eq 0) {
            Set-HPNetProgressCompleted $progressBar $progressLabel 'Hoàn tất'
            Set-HPNetFooterState $footerLabel 'Hoàn tất' 'Success'
            $statusBox.Text = $statusText
            $doneText = if ($dryRun.Checked) { 'Đã kiểm tra xong, chưa tải file nào.' } else { 'Đã hoàn tất quét và up các file chưa có.' }
            [System.Windows.Forms.MessageBox]::Show("$doneText`r`nXem chi tiết trong thư mục nhật ký.", 'Hoàn tất', 'OK', 'Information') | Out-Null
        } else {
            Set-HPNetProgressStopped $progressBar $progressLabel 'Chưa hoàn tất — xem lỗi'
            Set-HPNetFooterState $footerLabel 'Chưa hoàn tất — xem nhật ký' 'Warning'
            $statusBox.Text = $statusText
            [System.Windows.Forms.MessageBox]::Show('Công cụ đã dừng an toàn. Xem lại ở khung phía dưới và nhật ký.', 'Đã dừng an toàn', 'OK', 'Warning') | Out-Null
        }
    } catch {
        Set-HPNetProgressStopped $progressBar $progressLabel 'Lỗi — xem chi tiết'
        Set-HPNetFooterState $footerLabel 'Lỗi — xem chi tiết' 'Error'
        $statusBox.Text = $_.Exception.ToString()
        [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'Lỗi', 'OK', 'Error') | Out-Null
    } finally {
        $script:activeProcess = $null
        $stopButton.Enabled = $false
        $startButton.Enabled = $true
        $browseButton.Enabled = $true
        $folderBox.Enabled = $true
        $profileBox.Enabled = $true
        $reviewerBox.Enabled = $true
        $saveProfileButton.Enabled = $true
    }
})

$form.Add_FormClosing({
    if ($script:activeProcess -and -not $script:activeProcess.HasExited) { Stop-ActiveWorker }
})

if ($UiSelfTest) {
    $testBatches = @(Parse-UploadBatches @('C:\A | Trích yếu A', 'C:\B | Trích yếu B', 'C:\C | Trích yếu C'))
    if ($testBatches.Count -ne 3 -or $testBatches[2].abstract -ne 'Trích yếu C') { throw 'UI test: không phân tích đúng ba thư mục và trích yếu.' }
    if (-not $folderBox.Multiline -or $folderBox.Height -lt 50 -or $browseButton.Text -ne 'Thêm thư mục') { throw 'UI test: ô nhập nhiều thư mục chưa sẵn sàng.' }
    $form.StartPosition = 'Manual'; $form.Location = New-Object Drawing.Point(-32000,-32000); $form.ShowInTaskbar = $false
    $form.Show(); $form.PerformLayout(); [Windows.Forms.Application]::DoEvents()
    if ($null -eq $form.Icon) { throw 'UI test: cửa sổ chưa có icon riêng.' }
    if (-not $uiWorkspace -or $uiWorkspace.Workspace.ColumnCount -ne 2 -or $uiWorkspace.ActivityPanel.RowCount -ne 5 -or $statusBox.Dock -ne 'Fill' -or $progressPanel.Dock -ne 'Fill' -or [string]::IsNullOrWhiteSpace($footerLabel.Text)) { throw 'UI test: workspace hoạt động/footer chưa hoàn chỉnh.' }
    foreach ($control in @($group1, $group2, $group3, $actionBar, $progressPanel, $statusBox)) {
        if ($control.Right -gt $mainPanel.ClientSize.Width + 2) { throw "UI test: điều khiển vượt chiều rộng: $($control.Name)" }
    }
    if ($progressBar.Style -ne 'Continuous' -or $progressBar.Maximum -lt 1) { throw 'UI test: thanh tiến độ chưa được cấu hình.' }
    if ($TestImagePath) {
        $bitmap = New-Object Drawing.Bitmap($form.Width, $form.Height)
        try { $form.DrawToBitmap($bitmap, (New-Object Drawing.Rectangle(0,0,$form.Width,$form.Height))); $bitmap.Save($TestImagePath, [Drawing.Imaging.ImageFormat]::Png) }
        finally { $bitmap.Dispose() }
    }
    $form.Dispose()
    Write-Output 'UI_SELF_TEST_OK: nhiều thư mục/trích yếu, trạng thái điều khiển và bố cục; không mở Edge và không upload.'
    exit 0
}

[void]$form.ShowDialog()
