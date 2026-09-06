param([switch]$SelfTest)

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$toolRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$nodeScript = Join-Path $toolRoot 'hpnet-approve-draft.cjs'
$configPath = Join-Path $toolRoot 'cau_hinh.json'
$profilesPath = Join-Path $toolRoot 'profiles.json'
$scanPath = Join-Path $toolRoot 'ket_qua_quet_moi_nhat.json'
$defaultTitle = 'Bản nháp Thông báo xác nhận'

function Find-HPNetRuntime {
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
    if (-not $edgeExe) { throw 'Không tìm thấy Microsoft Edge.' }
    return [PSCustomObject]@{ NodeExe=$nodeExe; NodeModules=$nodeModules; EdgeExe=$edgeExe; Mode=$runtimeMode }
}

try { $runtime = Find-HPNetRuntime } catch {
    if ($SelfTest) { throw }
    [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'HPNet Duyệt VB dự thảo', 'OK', 'Error') | Out-Null
    exit 1
}

if ($SelfTest) {
    [PSCustomObject]@{ ToolRoot=$toolRoot; NodeScriptExists=(Test-Path -LiteralPath $nodeScript); NodeExe=$runtime.NodeExe; NodeModules=$runtime.NodeModules; EdgeExe=$runtime.EdgeExe; RuntimeMode=$runtime.Mode } | ConvertTo-Json
    exit 0
}

$stateRoot = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'HPNet VBDLIS AIO Tool\Duyet'
New-Item -ItemType Directory -Force -Path $stateRoot | Out-Null
foreach ($name in @('cau_hinh.json','profiles.json','du_lieu_dang_nhap_vneid','nhat_ky','ket_qua_quet_moi_nhat.json')) {
    $legacy = Join-Path $toolRoot $name; $saved = Join-Path $stateRoot $name
    if ((Test-Path -LiteralPath $legacy) -and -not (Test-Path -LiteralPath $saved)) { Copy-Item -LiteralPath $legacy -Destination $saved -Recurse }
}
$configPath = Join-Path $stateRoot 'cau_hinh.json'
$profilesPath = Join-Path $stateRoot 'profiles.json'
$scanPath = Join-Path $stateRoot 'ket_qua_quet_moi_nhat.json'

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
$form.Text = 'HPNet - Tự động duyệt VB dự thảo'
$form.StartPosition = 'CenterScreen'
$form.Size = New-Object System.Drawing.Size(900, 840)
$form.MinimumSize = New-Object System.Drawing.Size(860, 780)
$form.Font = New-Object System.Drawing.Font('Segoe UI', 9.75)
$form.BackColor = [System.Drawing.Color]::FromArgb(245, 246, 248)

$headerPanel = New-Object System.Windows.Forms.Panel
$headerPanel.Dock = 'Top'
$headerPanel.Height = 60
$headerPanel.BackColor = [System.Drawing.Color]::White

$title = New-Object System.Windows.Forms.Label
$title.Location = New-Object System.Drawing.Point(15, 10)
$title.AutoSize = $true
$title.Font = New-Object System.Drawing.Font('Segoe UI', 14, [System.Drawing.FontStyle]::Bold)
$title.ForeColor = [System.Drawing.Color]::FromArgb(41, 50, 60)
$title.Text = 'HPNet Duyệt VB Dự Thảo'
$headerPanel.Controls.Add($title)

$subtitle = New-Object System.Windows.Forms.Label
$subtitle.Location = New-Object System.Drawing.Point(17, 35)
$subtitle.AutoSize = $true
$subtitle.Font = New-Object System.Drawing.Font('Segoe UI', 9)
$subtitle.ForeColor = [System.Drawing.Color]::FromArgb(100, 100, 100)
$subtitle.Text = 'Tự động hóa quy trình quét và duyệt hàng loạt văn bản'
$headerPanel.Controls.Add($subtitle)

$mainPanel = New-Object System.Windows.Forms.FlowLayoutPanel
$mainPanel.Dock = 'Fill'
$mainPanel.FlowDirection = 'TopDown'
$mainPanel.WrapContents = $false
$mainPanel.AutoScroll = $true
$mainPanel.Padding = New-Object System.Windows.Forms.Padding(15)
$form.Controls.Add($mainPanel)
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
$group2.Text = ' THÔNG TIN LUỒNG DUYỆT '
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
$safetyLabel.Text = 'LƯU Ý: Bước 1 chỉ quét toàn bộ các trang, không bấm duyệt. Bước 2 chỉ mở sau khi quét xong; phần mềm sẽ yêu cầu xác nhận lần cuối trước khi tự động duyệt hàng loạt.'
$mainPanel.Controls.Add($safetyLabel)


# ACTION BAR
$actionBar = New-Object System.Windows.Forms.Panel
$actionBar.Size = New-Object System.Drawing.Size(830, 45)
$actionBar.Margin = New-Object System.Windows.Forms.Padding(0, 0, 0, 15)
$mainPanel.Controls.Add($actionBar)

$scanButton = New-Object System.Windows.Forms.Button
$scanButton.Text = 'BƯỚC 1: QUÉT VĂN BẢN'
$scanButton.Location = New-Object System.Drawing.Point(0, 0)
$scanButton.Size = New-Object System.Drawing.Size(200, 40)
$scanButton.Font = $fontBold
$scanButton.BackColor = [System.Drawing.Color]::FromArgb(255, 193, 7)
$scanButton.ForeColor = [System.Drawing.Color]::Black
$scanButton.FlatStyle = 'Flat'
$scanButton.FlatAppearance.BorderSize = 0
$actionBar.Controls.Add($scanButton)

$approveButton = New-Object System.Windows.Forms.Button
$approveButton.Text = 'BƯỚC 2: DUYỆT (CHƯA CÓ DỮ LIỆU QUÉT)'
$approveButton.Location = New-Object System.Drawing.Point(215, 0)
$approveButton.Size = New-Object System.Drawing.Size(340, 40)
$approveButton.Font = $fontBold
$approveButton.Enabled = $false
$approveButton.BackColor = [System.Drawing.Color]::FromArgb(198, 40, 40)
$approveButton.ForeColor = [System.Drawing.Color]::White
$approveButton.FlatStyle = 'Flat'
$approveButton.FlatAppearance.BorderSize = 0
$actionBar.Controls.Add($approveButton)

$openLogButton = New-Object System.Windows.Forms.Button
$openLogButton.Text = 'Mở thư mục Nhật ký'
$openLogButton.Location = New-Object System.Drawing.Point(570, 0)
$openLogButton.Size = New-Object System.Drawing.Size(160, 40)
$openLogButton.Font = $fontNormal
$openLogButton.BackColor = [System.Drawing.Color]::White
$openLogButton.FlatStyle = 'Flat'
$actionBar.Controls.Add($openLogButton)

$stopButton = New-Object System.Windows.Forms.Button
$stopButton.Text = 'DỪNG'
$stopButton.Location = New-Object System.Drawing.Point(745, 0)
$stopButton.Size = New-Object System.Drawing.Size(85, 40)
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

$statusBox = New-Object System.Windows.Forms.TextBox
$statusBox.Size = New-Object System.Drawing.Size(830, 180)
$statusBox.Multiline = $true
$statusBox.ScrollBars = 'Vertical'
$statusBox.ReadOnly = $true
$statusBox.Font = New-Object System.Drawing.Font('Consolas', 9.5)
$statusBox.BackColor = [System.Drawing.Color]::FromArgb(30, 30, 30)
$statusBox.ForeColor = [System.Drawing.Color]::FromArgb(200, 200, 200)
$statusBox.Text = "Sẵn sàng."
$mainPanel.Controls.Add($statusBox)

$script:activeProcess = $null
$script:stopRequested = $false

function Stop-ActiveWorker {
    if (-not $script:activeProcess -or $script:activeProcess.HasExited) { return }
    $script:stopRequested = $true
    $statusBox.Text = 'Đang dừng tiến trình và Edge do công cụ mở...'
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
    $approveButton.Text = 'BƯỚC 2 - CHƯA CÓ KẾT QUẢ QUÉT'
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
    $exactTitle = $abstractBox.Text.Trim()
    if ([string]::IsNullOrWhiteSpace($exactTitle)) {
        [System.Windows.Forms.MessageBox]::Show('Hãy nhập trích yếu cần khớp chính xác.', 'Thiếu trích yếu', 'OK', 'Warning') | Out-Null
        return $false
    }
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
    $config = [ordered]@{ mode=$mode; profileName=$profileName; exactTitle=$exactTitle; submitter=$submitter; nextReviewer=$nextReviewer; listPageSize=100 }
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
    $statusBox.Text = if ($mode -eq 'scan') { 'Đang quét toàn bộ các trang. Nếu Edge hiện trang đăng nhập, hãy chọn VNeID và hoàn tất xác thực; công cụ sẽ tự chạy tiếp.' } else { 'Đang duyệt lần lượt các văn bản đã xác nhận. Nếu được hỏi, hãy đăng nhập bằng VNeID. Không đóng Edge cho đến khi công cụ báo hoàn tất.' }
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
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        while (-not $process.HasExited) {
            [System.Windows.Forms.Application]::DoEvents()
            Start-Sleep -Milliseconds 150
        }
        $stdout = $stdoutTask.Result
        $stderr = $stderrTask.Result
        $statusText = ($stdout + [Environment]::NewLine + $stderr).Trim()
        if ($script:stopRequested) {
            $statusBox.Text = if ($statusText) { "Đã dừng theo yêu cầu.`r`n$statusText" } else { 'Đã dừng theo yêu cầu.' }
            [System.Windows.Forms.MessageBox]::Show('Tiến trình đã được dừng theo yêu cầu.', 'Đã dừng', 'OK', 'Information') | Out-Null
            return $false
        }
        $statusBox.Text = $statusText
        if ($process.ExitCode -ne 0) {
            [System.Windows.Forms.MessageBox]::Show('Công cụ đã dừng an toàn. Không tự bấm duyệt văn bản chưa xác nhận. Xem chi tiết ở khung nhật ký.', 'Đã dừng an toàn', 'OK', 'Warning') | Out-Null
            return $false
        }
        return $true
    } catch {
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
            $approveButton.Text = "BƯỚC 2 - DUYỆT $count VĂN BẢN"
            $approveButton.Enabled = ($count -gt 0)
            [System.Windows.Forms.MessageBox]::Show("Đã quét $($report.totalRecordsScanned) văn bản trên tất cả các trang.`r`nTìm thấy $count văn bản khớp chính xác.`r`n`r`nChưa duyệt văn bản nào.", 'Quét hoàn tất', 'OK', 'Information') | Out-Null
        } catch {
            $approveButton.Enabled = $false
            [System.Windows.Forms.MessageBox]::Show('Không đọc được kết quả quét. Hãy quét lại.', 'Lỗi kết quả quét', 'OK', 'Warning') | Out-Null
        }
    }
})

$approveButton.Add_Click({
    try { $report = Get-Content -LiteralPath $scanPath -Raw -Encoding UTF8 | ConvertFrom-Json } catch {
        [System.Windows.Forms.MessageBox]::Show('Không có kết quả quét hợp lệ. Hãy bấm BƯỚC 1.', 'Cần quét lại', 'OK', 'Warning') | Out-Null
        return
    }
    $count = [int]$report.candidateCount
    if ($count -le 0) { return }
    $reportTitle = ([string]$report.exactTitle).Normalize([System.Text.NormalizationForm]::FormC).Trim()
    $currentTitle = $abstractBox.Text.Normalize([System.Text.NormalizationForm]::FormC).Trim()
    if ($reportTitle -ne $currentTitle) {
        [System.Windows.Forms.MessageBox]::Show('Trích yếu đã thay đổi. Hãy quét lại trước khi duyệt.', 'Cần quét lại', 'OK', 'Warning') | Out-Null
        return
    }
    $currentSubmitter = $submitterBox.Text.Trim()
    $currentNextReviewer = $nextReviewerBox.Text.Trim()
    if (([string]$report.submitter).Normalize([System.Text.NormalizationForm]::FormC).Trim().ToUpperInvariant() -ne $currentSubmitter.Normalize([System.Text.NormalizationForm]::FormC).Trim().ToUpperInvariant() -or
        ([string]$report.nextReviewer).Normalize([System.Text.NormalizationForm]::FormC).Trim().ToUpperInvariant() -ne $currentNextReviewer.Normalize([System.Text.NormalizationForm]::FormC).Trim().ToUpperInvariant()) {
        [System.Windows.Forms.MessageBox]::Show('Thông tin người xử lý đã thay đổi. Hãy quét lại trước khi duyệt.', 'Cần quét lại', 'OK', 'Warning') | Out-Null
        return
    }
    $expectedStatus = "Đang trình [$currentSubmitter] duyệt"
    $message = "XÁC NHẬN DUYỆT THẬT TRÊN HPNET`r`n`r`nProfile: $($profileBox.Text.Trim())`r`nSố văn bản tối đa: $count`r`nTrích yếu khớp chính xác:`r`n$($report.exactTitle)`r`n`r`nNgười trình duyệt: $currentSubmitter`r`nTình trạng bắt buộc: $expectedStatus`r`nNgười nhận chuyển tiếp: $currentNextReviewer`r`n`r`nCông cụ sẽ kiểm tra lại từng mục, bỏ qua mục đã đổi tình trạng, rồi bấm 'Đồng ý và chuyển duyệt tiếp'. Bạn có chắc chắn tiếp tục?"
    $answer = [System.Windows.Forms.MessageBox]::Show($message, 'XÁC NHẬN TRƯỚC KHI DUYỆT', 'YesNo', 'Warning', 'Button2')
    if ($answer -ne [System.Windows.Forms.DialogResult]::Yes) { return }
    if (Invoke-HPNetTool 'approve') {
        $approveButton.Enabled = $false
        $approveButton.Text = 'BƯỚC 2 - ĐÃ HOÀN TẤT, HÃY QUÉT LẠI'
        [System.Windows.Forms.MessageBox]::Show('Đã xử lý hết các mục trong lần quét được xác nhận và tự động dừng. Hãy xem nhật ký để biết từng văn bản đã duyệt hoặc được bỏ qua.', 'Hoàn tất', 'OK', 'Information') | Out-Null
    }
})

$openLogButton.Add_Click({
    $logDir = Join-Path $toolRoot 'nhat_ky'
    if (-not (Test-Path -LiteralPath $logDir)) { [System.IO.Directory]::CreateDirectory($logDir) | Out-Null }
    Start-Process explorer.exe -ArgumentList @($logDir)
})

$stopButton.Add_Click({ Stop-ActiveWorker })

$form.Add_FormClosing({
    if ($script:activeProcess -and -not $script:activeProcess.HasExited) { Stop-ActiveWorker }
})

[void]$form.ShowDialog()
