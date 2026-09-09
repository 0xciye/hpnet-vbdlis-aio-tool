param([switch]$SelfTest, [switch]$UiSelfTest, [string]$TestImagePath)

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$toolRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path (Split-Path -Parent (Split-Path -Parent $toolRoot)) 'hpnet_ui_common.ps1')
$nodeScript = Join-Path $toolRoot 'hpnet-approve-draft.cjs'
$configPath = Join-Path $toolRoot 'cau_hinh.json'
$profilesPath = Join-Path $toolRoot 'profiles.json'
$scanPath = Join-Path $toolRoot 'ket_qua_quet_moi_nhat.json'
$defaultTitle = 'Bản nháp Thông báo xác nhận'

function Read-ApprovalOutput($Process, [scriptblock]$OnLine) {
    # Đọc cả stdout/stderr trên luồng giao diện; callback sự kiện .NET chạy ngoài
    # runspace PowerShell nên có thể làm cửa sổ tự đóng khi Edge vừa khởi động.
    $readers = @($Process.StandardOutput, $Process.StandardError)
    $tasks = @($readers[0].ReadLineAsync(), $readers[1].ReadLineAsync())
    while ($null -ne $tasks[0] -or $null -ne $tasks[1]) {
        for ($i = 0; $i -lt 2; $i++) {
            if ($null -ne $tasks[$i] -and $tasks[$i].IsCompleted) {
                $line = $tasks[$i].GetAwaiter().GetResult()
                if ($null -eq $line) { $tasks[$i] = $null }
                else {
                    if ($i -eq 1) { $line = "[LỖI] $line" }
                    & $OnLine $line
                    $tasks[$i] = $readers[$i].ReadLineAsync()
                }
            }
        }
        [Windows.Forms.Application]::DoEvents()
        Start-Sleep -Milliseconds 10
    }
    $Process.WaitForExit()
}

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
    [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'HPNet Duyệt VB dự thảo', 'OK', 'Error') | Out-Null
    exit 1
}

if ($SelfTest) {
    [PSCustomObject]@{ ToolRoot=$toolRoot; NodeScriptExists=(Test-Path -LiteralPath $nodeScript); NodeExe=$runtime.NodeExe; NodeModules=$runtime.NodeModules; EdgeExe=$runtime.EdgeExe; RuntimeMode=$runtime.Mode } | ConvertTo-Json
    exit 0
}

$stateRoot = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'HPNet VBDLIS AIO Tool\Duyet'
New-Item -ItemType Directory -Force -Path $stateRoot | Out-Null
$appRoot = $toolRoot; 1..4 | ForEach-Object { $appRoot = Split-Path -Parent $appRoot }
$previousToolRoot = Join-Path (Join-Path (Split-Path -Parent $appRoot) 'HPNET & VBDLIS Tools.previous') '_internal\nodes_tools\Duyet\HPNet Duyet VB Du Thao - VNEID APP'
foreach ($name in @('cau_hinh.json','profiles.json','du_lieu_dang_nhap_vneid','nhat_ky','ket_qua_quet_moi_nhat.json')) {
    $saved = Join-Path $stateRoot $name
    foreach ($legacyRoot in @($toolRoot,$previousToolRoot)) {
        $legacy = Join-Path $legacyRoot $name
        if ((Test-Path -LiteralPath $legacy) -and -not (Test-Path -LiteralPath $saved)) { Copy-Item -LiteralPath $legacy -Destination $saved -Recurse }
    }
}
$configPath = Join-Path $stateRoot 'cau_hinh.json'
$profilesPath = Join-Path $stateRoot 'profiles.json'
$scanPath = Join-Path $stateRoot 'ket_qua_quet_moi_nhat.json'

function Read-JsonSafe([string]$path) {
    if (-not (Test-Path -LiteralPath $path)) { return $null }
    try { return Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json } catch { return $null }
}

function Get-TitleList([string]$text) {
    return @($text -split "`r?`n" | ForEach-Object { $_.Normalize([System.Text.NormalizationForm]::FormC).Trim() } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -Unique)
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

function Save-ProfileStore([string]$selectedName, [string]$submitter, [string]$nextReviewer) {
    $map = [ordered]@{}
    foreach ($name in @(Get-ProfileNames $script:profileStore)) {
        $entry = Get-ProfileEntry $script:profileStore $name
        $map[$name] = [ordered]@{
            displayName = if ($entry.displayName) { [string]$entry.displayName } else { $name }
            submitter = [string]$entry.submitter
            nextReviewer = [string]$entry.nextReviewer
        }
    }
    $map[$selectedName] = [ordered]@{
        displayName = $selectedName
        submitter = $submitter
        nextReviewer = $nextReviewer
    }
    $document = [ordered]@{ lastProfile=$selectedName; profiles=$map }
    $document | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $profilesPath -Encoding UTF8
    $script:profileStore = Read-JsonSafe $profilesPath
}

$savedConfig = Read-JsonSafe $configPath
if (-not $savedConfig) {
    [ordered]@{
        profileName = ''
        mode = 'scan'
        exactTitle = ''
        submitter = ''
        nextReviewer = ''
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
$initialSubmitter = if ($savedConfig -and $savedConfig.submitter) { [string]$savedConfig.submitter } elseif ($initialEntry) { [string]$initialEntry.submitter } else { '' }
$initialNextReviewer = if ($savedConfig -and $savedConfig.nextReviewer) { [string]$savedConfig.nextReviewer } elseif ($initialEntry) { [string]$initialEntry.nextReviewer } else { '' }

[System.Windows.Forms.Application]::EnableVisualStyles()
$form = New-Object System.Windows.Forms.Form
$form.Text = 'HPNet - Duyệt văn bản dự thảo'
$form.StartPosition = 'CenterScreen'
$form.Size = New-Object System.Drawing.Size(1420, 920)
$form.MinimumSize = New-Object System.Drawing.Size(1240, 840)
$form.Font = New-Object System.Drawing.Font('Segoe UI', 9.75)
$form.BackColor = [System.Drawing.Color]::FromArgb(245, 246, 248)
Set-HPNetWindowIdentity -Form $form -ToolRoot $toolRoot -AppId 'HPNET.VBDLIS.Tools.Approve'

$headerPanel = New-Object System.Windows.Forms.Panel
$headerPanel.Dock = 'Top'
$headerPanel.Height = 60
$headerPanel.BackColor = [System.Drawing.Color]::White

$title = New-Object System.Windows.Forms.Label
$title.Location = New-Object System.Drawing.Point(15, 10)
$title.AutoSize = $true
$title.Font = New-Object System.Drawing.Font('Segoe UI', 14, [System.Drawing.FontStyle]::Bold)
$title.ForeColor = [System.Drawing.Color]::FromArgb(41, 50, 60)
$title.Text = 'HPNet Duyệt văn bản dự thảo'
$headerPanel.Controls.Add($title)

$subtitle = New-Object System.Windows.Forms.Label
$subtitle.Location = New-Object System.Drawing.Point(17, 35)
$subtitle.AutoSize = $true
$subtitle.Font = New-Object System.Drawing.Font('Segoe UI', 9)
$subtitle.ForeColor = [System.Drawing.Color]::FromArgb(100, 100, 100)
$subtitle.Text = 'Tự động hóa việc kiểm tra và chuyển duyệt văn bản dự thảo'
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

$fontNormal = New-Object System.Drawing.Font('Segoe UI', 9.75)
$fontBold = New-Object System.Drawing.Font('Segoe UI', 9.75, [System.Drawing.FontStyle]::Bold)

# CARD 1: NGUỒN DỮ LIỆU & BỘ LỌC
$group1 = New-Object System.Windows.Forms.GroupBox
$group1.Text = ' LỌC VĂN BẢN '
$group1.Font = $fontBold
$group1.Size = New-Object System.Drawing.Size(830, 160)
$group1.Margin = New-Object System.Windows.Forms.Padding(0, 0, 0, 15)
$group1.BackColor = [System.Drawing.Color]::White
$mainPanel.Controls.Add($group1)

$profileLabel = New-Object System.Windows.Forms.Label
$profileLabel.Text = 'Đơn vị / Profile:'
$profileLabel.Location = New-Object System.Drawing.Point(20, 35)
$profileLabel.AutoSize = $true
$profileLabel.Font = $fontNormal
$group1.Controls.Add($profileLabel)

$profileBox = New-Object System.Windows.Forms.ComboBox
$profileBox.Location = New-Object System.Drawing.Point(200, 32)
$profileBox.Size = New-Object System.Drawing.Size(430, 25)
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

$abstractLabel = New-Object System.Windows.Forms.Label
$abstractLabel.Text = 'Trích yếu khớp chính xác:'
$abstractLabel.Location = New-Object System.Drawing.Point(20, 75)
$abstractLabel.AutoSize = $true
$abstractLabel.Font = $fontNormal
$group1.Controls.Add($abstractLabel)

$abstractBox = New-Object System.Windows.Forms.TextBox
$abstractBox.Location = New-Object System.Drawing.Point(200, 72)
$abstractBox.Size = New-Object System.Drawing.Size(610, 65)
$abstractBox.Multiline = $true
$abstractBox.ScrollBars = 'Vertical'
$abstractBox.Font = $fontNormal
$abstractBox.Text = if ($savedConfig -and $savedConfig.exactTitle) { [string]$savedConfig.exactTitle } else { $defaultTitle }
$group1.Controls.Add($abstractBox)


# CARD 2: LUỒNG DUYỆT
$group2 = New-Object System.Windows.Forms.GroupBox
$group2.Text = ' THÔNG TIN CHUYỂN DUYỆT '
$group2.Font = $fontBold
$group2.Size = New-Object System.Drawing.Size(830, 130)
$group2.Margin = New-Object System.Windows.Forms.Padding(0, 0, 0, 15)
$group2.BackColor = [System.Drawing.Color]::White
$mainPanel.Controls.Add($group2)

$submitterLabel = New-Object System.Windows.Forms.Label
$submitterLabel.Text = 'Người trình duyệt hiện tại:'
$submitterLabel.Location = New-Object System.Drawing.Point(20, 35)
$submitterLabel.AutoSize = $true
$submitterLabel.Font = $fontNormal
$group2.Controls.Add($submitterLabel)

$submitterBox = New-Object System.Windows.Forms.TextBox
$submitterBox.Location = New-Object System.Drawing.Point(200, 32)
$submitterBox.Size = New-Object System.Drawing.Size(610, 25)
$submitterBox.Font = $fontNormal
$submitterBox.Text = $initialSubmitter
$group2.Controls.Add($submitterBox)

$nextReviewerLabel = New-Object System.Windows.Forms.Label
$nextReviewerLabel.Text = 'Người nhận chuyển tiếp:'
$nextReviewerLabel.Location = New-Object System.Drawing.Point(20, 75)
$nextReviewerLabel.AutoSize = $true
$nextReviewerLabel.Font = $fontNormal
$group2.Controls.Add($nextReviewerLabel)

$nextReviewerBox = New-Object System.Windows.Forms.TextBox
$nextReviewerBox.Location = New-Object System.Drawing.Point(200, 72)
$nextReviewerBox.Size = New-Object System.Drawing.Size(610, 25)
$nextReviewerBox.Font = $fontNormal
$nextReviewerBox.Text = $initialNextReviewer
$group2.Controls.Add($nextReviewerBox)

$previewLabel = New-Object System.Windows.Forms.Label
$previewLabel.Location = New-Object System.Drawing.Point(200, 105)
$previewLabel.Size = New-Object System.Drawing.Size(610, 20)
$previewLabel.Font = New-Object System.Drawing.Font('Segoe UI', 8.5, [System.Drawing.FontStyle]::Italic)
$previewLabel.ForeColor = [System.Drawing.Color]::Gray
$group2.Controls.Add($previewLabel)


# CAUTION MESSAGE
$safetyLabel = New-Object System.Windows.Forms.Label
$safetyLabel.Size = New-Object System.Drawing.Size(830, 45)
$safetyLabel.Font = $fontNormal
$safetyLabel.ForeColor = [System.Drawing.Color]::FromArgb(198, 40, 40)
$safetyLabel.Margin = New-Object System.Windows.Forms.Padding(0, 0, 0, 15)
$safetyLabel.Text = 'LƯU Ý: Bước 1 chỉ kiểm tra dữ liệu trên toàn bộ các trang và không chuyển duyệt. Bước 2 chỉ mở sau khi kiểm tra xong; phần mềm sẽ hỏi lại trước khi chuyển nhiều văn bản cùng lúc.'
$mainPanel.Controls.Add($safetyLabel)


# ACTION BAR
$actionBar = New-Object System.Windows.Forms.Panel
$actionBar.Size = New-Object System.Drawing.Size(830, 45)
$actionBar.Margin = New-Object System.Windows.Forms.Padding(0, 0, 0, 15)
$mainPanel.Controls.Add($actionBar)

$scanButton = New-Object System.Windows.Forms.Button
$scanButton.Text = 'BƯỚC 1: KIỂM TRA VĂN BẢN'
$scanButton.Location = New-Object System.Drawing.Point(0, 0)
$scanButton.Size = New-Object System.Drawing.Size(200, 40)
$scanButton.Font = $fontBold
$scanButton.BackColor = [System.Drawing.Color]::FromArgb(36, 88, 197)
$scanButton.ForeColor = [System.Drawing.Color]::White
$scanButton.FlatStyle = 'Flat'
$scanButton.FlatAppearance.BorderSize = 0
$actionBar.Controls.Add($scanButton)

$approveButton = New-Object System.Windows.Forms.Button
$approveButton.Text = 'BƯỚC 2: CHUYỂN DUYỆT (CHƯA CÓ KẾT QUẢ)'
$approveButton.Location = New-Object System.Drawing.Point(215, 0)
$approveButton.Size = New-Object System.Drawing.Size(340, 40)
$approveButton.Font = $fontBold
$approveButton.Enabled = $false
$approveButton.BackColor = [System.Drawing.Color]::FromArgb(229, 231, 235)
$approveButton.ForeColor = [System.Drawing.Color]::White
$approveButton.FlatStyle = 'Flat'
$approveButton.FlatAppearance.BorderSize = 0
$actionBar.Controls.Add($approveButton)

$openLogButton = New-Object System.Windows.Forms.Button
$openLogButton.Text = 'Mở thư mục nhật ký'
$openLogButton.Location = New-Object System.Drawing.Point(570, 0)
$openLogButton.Size = New-Object System.Drawing.Size(160, 40)
$openLogButton.Font = $fontNormal
$openLogButton.BackColor = [System.Drawing.Color]::White
$openLogButton.FlatStyle = 'Flat'
$actionBar.Controls.Add($openLogButton)

$stopButton = New-Object System.Windows.Forms.Button
$stopButton.Text = 'DỪNG TÁC VỤ'
$stopButton.Location = New-Object System.Drawing.Point(730, 0)
$stopButton.Size = New-Object System.Drawing.Size(95, 40)
$stopButton.Font = $fontNormal
$stopButton.BackColor = [System.Drawing.Color]::FromArgb(230, 230, 230)
$stopButton.FlatStyle = 'Flat'
$stopButton.Enabled = $false
$actionBar.Controls.Add($stopButton)


# LOG PANEL
$logLabel = New-Object System.Windows.Forms.Label
$logLabel.Text = 'Nhật ký hoạt động:'
$logLabel.Font = $fontBold
$logLabel.AutoSize = $true
$logLabel.Margin = New-Object System.Windows.Forms.Padding(0, 0, 0, 5)
$mainPanel.Controls.Add($logLabel)

$progressPanel = New-Object System.Windows.Forms.Panel
$progressPanel.Size = New-Object System.Drawing.Size(830, 32)
$progressPanel.Margin = New-Object System.Windows.Forms.Padding(0, 0, 0, 5)
$mainPanel.Controls.Add($progressPanel)
$progressLabel = New-Object System.Windows.Forms.Label
$progressLabel.Text = 'Sẵn sàng thực hiện'
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
$progressBar.AccessibleName = 'Tiến độ duyệt'
$progressPanel.Controls.Add($progressBar)

$statusBox = New-Object System.Windows.Forms.TextBox
$statusBox.Size = New-Object System.Drawing.Size(830, 180)
$statusBox.Multiline = $true
$statusBox.ScrollBars = 'Vertical'
$statusBox.ReadOnly = $true
$statusBox.Font = New-Object System.Drawing.Font('Consolas', 9.5)
$statusBox.BackColor = [System.Drawing.Color]::FromArgb(30, 30, 30)
$statusBox.ForeColor = [System.Drawing.Color]::FromArgb(200, 200, 200)
$statusBox.Text = "Sẵn sàng thực hiện. Vui lòng kiểm tra thông tin trước khi bắt đầu."
$mainPanel.Controls.Add($statusBox)

$footerLabel = New-HPNetFooter -Form $form -Text 'Sẵn sàng thực hiện'
$uiWorkspace = New-HPNetSplitWorkspace -MainPanel $mainPanel -InputControls @($group1, $group2, $safetyLabel, $actionBar) -ProgressPanel $progressPanel -LogLabel $logLabel -StatusBox $statusBox -ActivityTitle 'TIẾN ĐỘ XỬ LÝ' -ActivityHint 'Kiểm tra kết quả, xác nhận thông tin rồi mới chuyển duyệt.'

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
function Invalidate-ScanResult {
    $approveButton.Enabled = $false
    $approveButton.Text = 'BƯỚC 2: CHƯA CÓ KẾT QUẢ RÀ SOÁT'
    Set-ApprovalButtonStyles
}

function Set-ApprovalButtonStyles {
    $scanButton.BackColor = [System.Drawing.Color]::FromArgb(36, 88, 197)
    $scanButton.ForeColor = [System.Drawing.Color]::White
    if ($approveButton.Enabled) {
        $approveButton.BackColor = [System.Drawing.Color]::FromArgb(46, 125, 50)
        $approveButton.ForeColor = [System.Drawing.Color]::White
    } else {
        $approveButton.BackColor = [System.Drawing.Color]::FromArgb(229, 231, 235)
        $approveButton.ForeColor = [System.Drawing.Color]::FromArgb(107, 119, 136)
    }
    $stopButton.BackColor = [System.Drawing.Color]::FromArgb(198, 61, 69)
    $stopButton.ForeColor = [System.Drawing.Color]::White
}

function Update-WorkflowPreview {
    $previewLabel.Text = "$($submitterBox.Text.Trim()) ➔ DUYỆT ➔ $($nextReviewerBox.Text.Trim())"
}

$profileBox.Add_SelectedIndexChanged({
    $entry = Get-ProfileEntry $script:profileStore $profileBox.Text
    if ($entry) {
        $submitterBox.Text = [string]$entry.submitter
        $nextReviewerBox.Text = [string]$entry.nextReviewer
    }
    Update-WorkflowPreview
    Invalidate-ScanResult
})

$saveProfileButton.Add_Click({
    $profileName = $profileBox.Text.Trim()
    $submitter = $submitterBox.Text.Trim()
    $nextReviewer = $nextReviewerBox.Text.Trim()
    if ([string]::IsNullOrWhiteSpace($profileName)) {
        [System.Windows.Forms.MessageBox]::Show('Vui lòng nhập tên Đơn vị / Profile.', 'Thiếu profile', 'OK', 'Warning') | Out-Null
        return
    }
    if ([string]::IsNullOrWhiteSpace($submitter)) {
        [System.Windows.Forms.MessageBox]::Show('Vui lòng nhập Người trình duyệt hiện tại.', 'Thiếu người trình duyệt', 'OK', 'Warning') | Out-Null
        return
    }
    if ([string]::IsNullOrWhiteSpace($nextReviewer)) {
        [System.Windows.Forms.MessageBox]::Show('Vui lòng nhập Người nhận chuyển tiếp.', 'Thiếu người nhận', 'OK', 'Warning') | Out-Null
        return
    }
    try {
        Save-ProfileStore $profileName $submitter $nextReviewer
        if (-not $profileBox.Items.Contains($profileName)) { [void]$profileBox.Items.Add($profileName) }
        [System.Windows.Forms.MessageBox]::Show("Đã lưu profile $profileName.", 'Đã lưu cấu hình', 'OK', 'Information') | Out-Null
    } catch {
        [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'Không lưu được profile', 'OK', 'Error') | Out-Null
    }
})

$submitterBox.Add_TextChanged({ Update-WorkflowPreview; Invalidate-ScanResult })
$nextReviewerBox.Add_TextChanged({ Update-WorkflowPreview; Invalidate-ScanResult })
Update-WorkflowPreview

function Invoke-HPNetTool([string]$mode) {
    $exactTitles = @(Get-TitleList $abstractBox.Text)
    if ($exactTitles.Count -eq 0) {
        [System.Windows.Forms.MessageBox]::Show('Hãy nhập ít nhất một trích yếu, mỗi trích yếu một dòng.', 'Thiếu trích yếu', 'OK', 'Warning') | Out-Null
        return $false
    }
    $exactTitle = $exactTitles -join "`n"
    $profileName = $profileBox.Text.Trim()
    $submitter = $submitterBox.Text.Trim()
    $nextReviewer = $nextReviewerBox.Text.Trim()
    if ([string]::IsNullOrWhiteSpace($submitter)) {
        [System.Windows.Forms.MessageBox]::Show('Vui lòng nhập Người trình duyệt hiện tại.', 'Thiếu người trình duyệt', 'OK', 'Warning') | Out-Null
        return $false
    }
    if ([string]::IsNullOrWhiteSpace($nextReviewer)) {
        [System.Windows.Forms.MessageBox]::Show('Vui lòng nhập Người nhận chuyển tiếp.', 'Thiếu người nhận', 'OK', 'Warning') | Out-Null
        return $false
    }
    $config = [ordered]@{ mode=$mode; profileName=$profileName; exactTitle=$exactTitle; exactTitles=$exactTitles; submitter=$submitter; nextReviewer=$nextReviewer; listPageSize=100 }
    $config | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $configPath -Encoding UTF8
    $scanButton.Enabled = $false
    $approveButton.Enabled = $false
    $abstractBox.Enabled = $false
    $profileBox.Enabled = $false
    $submitterBox.Enabled = $false
    $nextReviewerBox.Enabled = $false
    $saveProfileButton.Enabled = $false
    $script:stopRequested = $false
    $stopButton.Enabled = $true
    Set-HPNetFooterState $footerLabel 'Đang xử lý — khóa bước duyệt' 'Running'
    Set-HPNetProgressRunning $progressBar $progressLabel 'Đang kiểm tra trên HPNet…'
    $statusBox.Text = if ($mode -eq 'scan') { 'Đang kiểm tra toàn bộ các trang. Nếu Edge hiển thị trang đăng nhập, vui lòng chọn VNeID và hoàn tất xác thực; công cụ sẽ tự động tiếp tục.' } else { 'Đang chuyển duyệt lần lượt các văn bản đã xác nhận. Nếu được yêu cầu, vui lòng đăng nhập bằng VNeID. Không đóng Edge cho đến khi công cụ thông báo hoàn tất.' }
    $form.Refresh()
    try {
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
        $script:liveOutput = New-Object System.Collections.Concurrent.ConcurrentQueue[string]
        Read-ApprovalOutput $process {
            param($line)
            [void]$script:liveOutput.Enqueue($line)
            $statusBox.Lines = @($script:liveOutput.ToArray())
            Update-HPNetProgressFromLine $progressBar $progressLabel $line
            $statusBox.SelectionStart = $statusBox.TextLength
            $statusBox.ScrollToCaret()
        }
        $statusText = (@($script:liveOutput.ToArray()) -join [Environment]::NewLine).Trim()
        if ($script:stopRequested) {
            Set-HPNetProgressStopped $progressBar $progressLabel 'Đã dừng theo yêu cầu'
            Set-HPNetFooterState $footerLabel 'Đã dừng theo yêu cầu' 'Stopped'
            $statusBox.Text = if ($statusText) { "Đã dừng theo yêu cầu.`r`n$statusText" } else { 'Đã dừng theo yêu cầu.' }
            [System.Windows.Forms.MessageBox]::Show('Tiến trình đã được dừng theo yêu cầu.', 'Đã dừng', 'OK', 'Information') | Out-Null
            return $false
        }
        $statusBox.Text = $statusText
        if ($process.ExitCode -ne 0) {
            Set-HPNetProgressStopped $progressBar $progressLabel 'Chưa hoàn tất — xem lỗi'
            Set-HPNetFooterState $footerLabel 'Chưa hoàn tất — xem nhật ký' 'Warning'
            [System.Windows.Forms.MessageBox]::Show('Tác vụ đã dừng an toàn. Không có văn bản nào được chuyển duyệt nếu chưa được xác nhận. Vui lòng xem chi tiết trong nhật ký.', 'Đã dừng an toàn', 'OK', 'Warning') | Out-Null
            return $false
        }
        Set-HPNetProgressCompleted $progressBar $progressLabel 'Hoàn tất'
        Set-HPNetFooterState $footerLabel 'Hoàn tất bước hiện tại' 'Success'
        return $true
    } catch {
        Set-HPNetProgressStopped $progressBar $progressLabel 'Lỗi — xem chi tiết'
        Set-HPNetFooterState $footerLabel 'Lỗi — xem chi tiết' 'Error'
        $statusBox.Text = $_.Exception.ToString()
        [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'Lỗi', 'OK', 'Error') | Out-Null
        return $false
    } finally {
        $script:activeProcess = $null
        $stopButton.Enabled = $false
        $scanButton.Enabled = $true
        $abstractBox.Enabled = $true
        $profileBox.Enabled = $true
        $submitterBox.Enabled = $true
        $nextReviewerBox.Enabled = $true
        $saveProfileButton.Enabled = $true
    }
}

$abstractBox.Add_TextChanged({
    Invalidate-ScanResult
})

$scanButton.Add_Click({
    if (Invoke-HPNetTool 'scan') {
        try {
            $report = Get-Content -LiteralPath $scanPath -Raw -Encoding UTF8 | ConvertFrom-Json
            $count = [int]$report.candidateCount
            $approveButton.Text = "BƯỚC 2: CHUYỂN DUYỆT $count VĂN BẢN"
            $approveButton.Enabled = ($count -gt 0)
            Set-ApprovalButtonStyles
            [System.Windows.Forms.MessageBox]::Show("Đã kiểm tra $($report.totalRecordsScanned) văn bản trên toàn bộ các trang.`r`nTìm thấy $count văn bản khớp chính xác.`r`n`r`nChưa có văn bản nào được chuyển duyệt.", 'Kiểm tra hoàn tất', 'OK', 'Information') | Out-Null
        } catch {
            $approveButton.Enabled = $false
            Set-ApprovalButtonStyles
            [System.Windows.Forms.MessageBox]::Show('Không thể đọc kết quả rà soát. Vui lòng thực hiện lại bước 1.', 'Lỗi kết quả rà soát', 'OK', 'Warning') | Out-Null
        }
    }
})

$approveButton.Add_Click({
    try { $report = Get-Content -LiteralPath $scanPath -Raw -Encoding UTF8 | ConvertFrom-Json } catch {
        [System.Windows.Forms.MessageBox]::Show('Chưa có kết quả rà soát hợp lệ. Vui lòng thực hiện bước 1 trước.', 'Cần rà soát lại', 'OK', 'Warning') | Out-Null
        return
    }
    $count = [int]$report.candidateCount
    if ($count -le 0) { return }
    $reportTitles = if ($report.exactTitles) { @($report.exactTitles) } else { @(Get-TitleList ([string]$report.exactTitle)) }
    $currentTitles = @(Get-TitleList $abstractBox.Text)
    $sameTitles = ($reportTitles.Count -eq $currentTitles.Count)
    if ($sameTitles) { for ($i = 0; $i -lt $reportTitles.Count; $i++) { if ($reportTitles[$i].Normalize([System.Text.NormalizationForm]::FormC).Trim() -ne $currentTitles[$i]) { $sameTitles = $false; break } } }
    if (-not $sameTitles) {
        [System.Windows.Forms.MessageBox]::Show('Trích yếu đã thay đổi. Vui lòng rà soát lại trước khi chuyển duyệt.', 'Cần rà soát lại', 'OK', 'Warning') | Out-Null
        return
    }
    $currentSubmitter = $submitterBox.Text.Trim()
    $currentNextReviewer = $nextReviewerBox.Text.Trim()
    if (([string]$report.submitter).Normalize([System.Text.NormalizationForm]::FormC).Trim().ToUpperInvariant() -ne $currentSubmitter.Normalize([System.Text.NormalizationForm]::FormC).Trim().ToUpperInvariant() -or
        ([string]$report.nextReviewer).Normalize([System.Text.NormalizationForm]::FormC).Trim().ToUpperInvariant() -ne $currentNextReviewer.Normalize([System.Text.NormalizationForm]::FormC).Trim().ToUpperInvariant()) {
        [System.Windows.Forms.MessageBox]::Show('Thông tin người xử lý đã thay đổi. Vui lòng rà soát lại trước khi chuyển duyệt.', 'Cần rà soát lại', 'OK', 'Warning') | Out-Null
        return
    }
    $expectedStatus = "Đang trình [$currentSubmitter] duyệt"
    $message = "XÁC NHẬN DUYỆT THẬT TRÊN HPNET`r`n`r`nProfile: $($profileBox.Text.Trim())`r`nSố văn bản tối đa: $count`r`nTrích yếu khớp chính xác:`r`n$($report.exactTitle)`r`n`r`nNgười trình duyệt: $currentSubmitter`r`nTình trạng bắt buộc: $expectedStatus`r`nNgười nhận chuyển tiếp: $currentNextReviewer`r`n`r`nCông cụ sẽ kiểm tra lại từng mục, bỏ qua mục đã đổi tình trạng, rồi bấm 'Đồng ý và chuyển duyệt tiếp'. Bạn có chắc chắn tiếp tục?"
    $answer = [System.Windows.Forms.MessageBox]::Show($message, 'XÁC NHẬN TRƯỚC KHI DUYỆT', 'YesNo', 'Warning', 'Button2')
    if ($answer -ne [System.Windows.Forms.DialogResult]::Yes) { return }
    if (Invoke-HPNetTool 'approve') {
        $approveButton.Enabled = $false
        $approveButton.Text = 'BƯỚC 2: ĐÃ HOÀN TẤT, VUI LÒNG RÀ SOÁT LẠI'
        Set-ApprovalButtonStyles
        [System.Windows.Forms.MessageBox]::Show('Đã xử lý toàn bộ mục trong phạm vi đã xác nhận và tự động dừng. Vui lòng xem nhật ký để biết chi tiết từng văn bản được chuyển duyệt hoặc bỏ qua.', 'Hoàn tất', 'OK', 'Information') | Out-Null
    }
})

$openLogButton.Add_Click({
    $logDir = Join-Path $stateRoot 'nhat_ky'
    if (-not (Test-Path -LiteralPath $logDir)) { [System.IO.Directory]::CreateDirectory($logDir) | Out-Null }
    Start-Process explorer.exe -ArgumentList @($logDir)
})

$stopButton.Add_Click({ Stop-ActiveWorker })
Set-ApprovalButtonStyles

$form.Add_FormClosing({
    if ($script:activeProcess -and -not $script:activeProcess.HasExited) { Stop-ActiveWorker }
})

if ($UiSelfTest) {
    $testTitles = @(Get-TitleList "Trích yếu 1`r`nTrích yếu 2`r`nTrích yếu X")
    if ($testTitles.Count -ne 3 -or $testTitles[1] -ne 'Trích yếu 2') { throw 'UI test: không phân tích đúng nhiều trích yếu.' }
    if (-not $abstractBox.Multiline -or $abstractBox.Height -lt 50 -or $approveButton.Enabled) { throw 'UI test: ô trích yếu hoặc khóa bước duyệt không đúng.' }
    $form.StartPosition = 'Manual'; $form.Location = New-Object Drawing.Point(-32000,-32000); $form.ShowInTaskbar = $false
    $form.Show(); $form.PerformLayout(); [Windows.Forms.Application]::DoEvents()
    if ($null -eq $form.Icon) { throw 'UI test: cửa sổ chưa có icon riêng.' }
    if (-not $uiWorkspace -or $uiWorkspace.Workspace.ColumnCount -ne 2 -or $uiWorkspace.ActivityPanel.RowCount -ne 5 -or $statusBox.Dock -ne 'Fill' -or $progressPanel.Dock -ne 'Fill' -or [string]::IsNullOrWhiteSpace($footerLabel.Text)) { throw 'UI test: workspace hoạt động/footer chưa hoàn chỉnh.' }
    foreach ($control in @($group1, $group2, $actionBar, $progressPanel, $statusBox)) {
        if ($control.Right -gt $mainPanel.ClientSize.Width + 2) { throw "UI test: điều khiển vượt chiều rộng: $($control.Name)" }
    }
    if ($progressBar.Style -ne 'Continuous' -or $progressBar.Maximum -lt 1) { throw 'UI test: thanh tiến độ chưa được cấu hình.' }
    if ($TestImagePath) {
        $bitmap = New-Object Drawing.Bitmap($form.Width, $form.Height)
        try { $form.DrawToBitmap($bitmap, (New-Object Drawing.Rectangle(0,0,$form.Width,$form.Height))); $bitmap.Save($TestImagePath, [Drawing.Imaging.ImageFormat]::Png) }
        finally { $bitmap.Dispose() }
    }
    $form.Dispose()
    Write-Output 'UI_SELF_TEST_OK: nhiều trích yếu, khóa duyệt an toàn và bố cục; không mở Edge và không duyệt.'
    exit 0
}

[void]$form.ShowDialog()
