param([switch]$SelfTest)

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$toolRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$nodeScript = Join-Path $toolRoot 'hpnet-upload-draft.cjs'
$configPath = Join-Path $toolRoot 'cau_hinh.json'
$profilesPath = Join-Path $toolRoot 'profiles.json'

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

$stateRoot = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'HPNet VBDLIS AIO Tool\Upload'
New-Item -ItemType Directory -Force -Path $stateRoot | Out-Null
foreach ($name in @('cau_hinh.json','profiles.json','du_lieu_dang_nhap_vneid','nhat_ky','trang_thai_da_up.json')) {
    $legacy = Join-Path $toolRoot $name; $saved = Join-Path $stateRoot $name
    if ((Test-Path -LiteralPath $legacy) -and -not (Test-Path -LiteralPath $saved)) { Copy-Item -LiteralPath $legacy -Destination $saved -Recurse }
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
$form.Text = 'HPNet - Tự động up VB dự thảo'
$form.StartPosition = 'CenterScreen'
$form.Size = New-Object System.Drawing.Size(900, 800)
$form.MinimumSize = New-Object System.Drawing.Size(860, 750)
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
$title.Text = 'HPNet Upload VB Dự Thảo'
$headerPanel.Controls.Add($title)

$subtitle = New-Object System.Windows.Forms.Label
$subtitle.Location = New-Object System.Drawing.Point(17, 35)
$subtitle.AutoSize = $true
$subtitle.Font = New-Object System.Drawing.Font('Segoe UI', 9)
$subtitle.ForeColor = [System.Drawing.Color]::FromArgb(100, 100, 100)
$subtitle.Text = 'Tự động hóa quy trình tải văn bản dự thảo'
$headerPanel.Controls.Add($subtitle)

$mainPanel = New-Object System.Windows.Forms.FlowLayoutPanel
$mainPanel.Dock = 'Fill'
$mainPanel.FlowDirection = 'TopDown'
$mainPanel.WrapContents = $false
$mainPanel.AutoScroll = $true
$mainPanel.Padding = New-Object System.Windows.Forms.Padding(15)
$form.Controls.Add($mainPanel)
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
$folderLabel.Text = 'Thư mục chép File:'
$folderLabel.Location = New-Object System.Drawing.Point(20, 75)
$folderLabel.AutoSize = $true
$folderLabel.Font = $fontNormal
$group1.Controls.Add($folderLabel)

$folderBox = New-Object System.Windows.Forms.TextBox
$folderBox.Location = New-Object System.Drawing.Point(150, 72)
$folderBox.Size = New-Object System.Drawing.Size(480, 25)
$folderBox.Font = $fontNormal
$folderBox.Text = if ($savedConfig -and $savedConfig.sourceFolder) { [string]$savedConfig.sourceFolder } else { '' }
$group1.Controls.Add($folderBox)

$browseButton = New-Object System.Windows.Forms.Button
$browseButton.Text = 'Chọn thư mục'
$browseButton.Location = New-Object System.Drawing.Point(650, 71)
$browseButton.Size = New-Object System.Drawing.Size(160, 28)
$browseButton.Font = $fontNormal
$browseButton.BackColor = [System.Drawing.Color]::White
$browseButton.FlatStyle = 'Flat'
$group1.Controls.Add($browseButton)

$abstractLabel = New-Object System.Windows.Forms.Label
$abstractLabel.Text = 'Trích yếu chung:'
$abstractLabel.Location = New-Object System.Drawing.Point(20, 115)
$abstractLabel.AutoSize = $true
$abstractLabel.Font = $fontNormal
$group1.Controls.Add($abstractLabel)

$abstractBox = New-Object System.Windows.Forms.TextBox
$abstractBox.Location = New-Object System.Drawing.Point(150, 112)
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
$reuploadModified.Text = 'Upload lại file đã sửa (Bỏ qua file cũ, không up lặp)'
$reuploadModified.Location = New-Object System.Drawing.Point(20, 30)
$reuploadModified.AutoSize = $true
$reuploadModified.Font = $fontNormal
$reuploadModified.Checked = if ($savedConfig -and $null -ne $savedConfig.reuploadModified) { [bool]$savedConfig.reuploadModified } else { $true }
$group3.Controls.Add($reuploadModified)

$dryRun = New-Object System.Windows.Forms.CheckBox
$dryRun.Text = 'Chế độ Chạy Thử (Chỉ kiểm tra, không upload)'
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
$startButton.Text = 'BẮT ĐẦU UPLOAD'
$startButton.Location = New-Object System.Drawing.Point(0, 0)
$startButton.Size = New-Object System.Drawing.Size(200, 40)
$startButton.Font = New-Object System.Drawing.Font('Segoe UI', 10, [System.Drawing.FontStyle]::Bold)
$startButton.BackColor = [System.Drawing.Color]::FromArgb(0, 120, 215)
$startButton.ForeColor = [System.Drawing.Color]::White
$startButton.FlatStyle = 'Flat'
$startButton.FlatAppearance.BorderSize = 0
$actionBar.Controls.Add($startButton)

$openLogButton = New-Object System.Windows.Forms.Button
$openLogButton.Text = 'Mở thư mục Nhật ký'
$openLogButton.Location = New-Object System.Drawing.Point(215, 0)
$openLogButton.Size = New-Object System.Drawing.Size(160, 40)
$openLogButton.Font = $fontNormal
$openLogButton.BackColor = [System.Drawing.Color]::White
$openLogButton.FlatStyle = 'Flat'
$actionBar.Controls.Add($openLogButton)

$stopButton = New-Object System.Windows.Forms.Button
$stopButton.Text = 'DỪNG AN TOÀN'
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

$statusBox = New-Object System.Windows.Forms.TextBox
$statusBox.Size = New-Object System.Drawing.Size(830, 180)
$statusBox.Multiline = $true
$statusBox.ScrollBars = 'Vertical'
$statusBox.ReadOnly = $true
$statusBox.Font = New-Object System.Drawing.Font('Consolas', 9.5)
$statusBox.BackColor = [System.Drawing.Color]::FromArgb(30, 30, 30)
$statusBox.ForeColor = [System.Drawing.Color]::FromArgb(200, 200, 200)
$statusBox.Text = "Sẵn sàng.`r`nCông cụ sẽ quét toàn bộ danh sách HPNet trước, bỏ qua file đã có rồi mới up lần lượt các file còn lại."
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
$browseButton.Add_Click({
    $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
    $dialog.Description = 'Chọn thư mục chứa các file Word cần up'
    if (Test-Path -LiteralPath $folderBox.Text) { $dialog.SelectedPath = $folderBox.Text }
    if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { $folderBox.Text = $dialog.SelectedPath }
})

$openLogButton.Add_Click({
    $logDir = Join-Path $toolRoot 'nhat_ky'
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
    $abstract = $abstractBox.Text.Trim()
    $folder = $folderBox.Text.Trim()
    $reviewer = $reviewerBox.Text.Trim()
    if ([string]::IsNullOrWhiteSpace($abstract)) {
        [System.Windows.Forms.MessageBox]::Show('Hãy nhập trích yếu.', 'Thiếu trích yếu', 'OK', 'Warning') | Out-Null
        return
    }
    if (-not (Test-Path -LiteralPath $folder -PathType Container)) {
        [System.Windows.Forms.MessageBox]::Show('Thư mục file Word không tồn tại.', 'Sai thư mục', 'OK', 'Warning') | Out-Null
        return
    }
    if ([string]::IsNullOrWhiteSpace($reviewer)) {
        [System.Windows.Forms.MessageBox]::Show('Vui lòng nhập Người duyệt cấp 1 / lãnh đạo.', 'Thiếu người duyệt', 'OK', 'Warning') | Out-Null
        return
    }
    $wordFiles = @(Get-ChildItem -LiteralPath $folder -File | Where-Object { $_.Name -notlike '~$*' -and $_.Extension -match '^\.docx?$' })
    if ($wordFiles.Count -eq 0) {
        [System.Windows.Forms.MessageBox]::Show('Thư mục không có file .doc hoặc .docx.', 'Không có file Word', 'OK', 'Warning') | Out-Null
        return
    }

    $modeText = if ($dryRun.Checked) { 'CHỈ KIỂM TRA, KHÔNG UP' } else { 'UP THẬT LÊN HPNET' }
    $reuploadText = if ($reuploadModified.Checked) { 'Có - bỏ qua bản cũ, up lại bản đã sửa' } else { 'Không - thấy cùng tên là bỏ qua' }
    $message = "Chế độ: $modeText`r`nProfile: $($profileBox.Text.Trim())`r`nSố file Word: $($wordFiles.Count)`r`nUp lại file đã sửa: $reuploadText`r`nNgười duyệt cấp 1 / lãnh đạo: $reviewer`r`nVị trí: Văn bản trình duyệt (*)`r`n`r`nTrích yếu:`r`n$abstract`r`n`r`nTiếp tục?"
    $answer = [System.Windows.Forms.MessageBox]::Show($message, 'Xác nhận chạy công cụ', 'OKCancel', 'Information')
    if ($answer -ne [System.Windows.Forms.DialogResult]::OK) { return }

    try {
        $config = [ordered]@{ profileName=$profileBox.Text.Trim(); abstract=$abstract; sourceFolder=$folder; reviewerLevel1=$reviewer; dryRun=[bool]$dryRun.Checked; reuploadModified=[bool]$reuploadModified.Checked; listPageSize=100 }
        $config | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $configPath -Encoding UTF8

        $startButton.Enabled = $false
        $browseButton.Enabled = $false
        $profileBox.Enabled = $false
        $reviewerBox.Enabled = $false
        $saveProfileButton.Enabled = $false
        $script:stopRequested = $false
        $stopButton.Enabled = $true
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
        } elseif ($process.ExitCode -eq 0) {
            $statusBox.Text = $statusText
            $doneText = if ($dryRun.Checked) { 'Đã kiểm tra xong, chưa tải file nào.' } else { 'Đã hoàn tất quét và up các file chưa có.' }
            [System.Windows.Forms.MessageBox]::Show("$doneText`r`nXem chi tiết trong thư mục nhật ký.", 'Hoàn tất', 'OK', 'Information') | Out-Null
        } else {
            $statusBox.Text = $statusText
            [System.Windows.Forms.MessageBox]::Show('Công cụ đã dừng an toàn. Xem lại ở khung phía dưới và nhật ký.', 'Đã dừng an toàn', 'OK', 'Warning') | Out-Null
        }
    } catch {
        $statusBox.Text = $_.Exception.ToString()
        [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'Lỗi', 'OK', 'Error') | Out-Null
    } finally {
        $script:activeProcess = $null
        $stopButton.Enabled = $false
        $startButton.Enabled = $true
        $browseButton.Enabled = $true
        $profileBox.Enabled = $true
        $reviewerBox.Enabled = $true
        $saveProfileButton.Enabled = $true
    }
})

$form.Add_FormClosing({
    if ($script:activeProcess -and -not $script:activeProcess.HasExited) { Stop-ActiveWorker }
})

[void]$form.ShowDialog()
