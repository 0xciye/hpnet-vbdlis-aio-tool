if (-not ('HPNetWindowsIdentity' -as [type])) {
    Add-Type -TypeDefinition 'using System.Runtime.InteropServices; public static class HPNetWindowsIdentity { [DllImport("shell32.dll", CharSet=CharSet.Unicode)] public static extern int SetCurrentProcessExplicitAppUserModelID(string id); }'
}

function Set-HPNetWindowIdentity {
    param(
        [Parameter(Mandatory=$true)][System.Windows.Forms.Form]$Form,
        [Parameter(Mandatory=$true)][string]$ToolRoot,
        [Parameter(Mandatory=$true)][string]$AppId
    )
    $iconPath = Join-Path (Split-Path -Parent $ToolRoot) 'app_icon.ico'
    if (-not (Test-Path -LiteralPath $iconPath -PathType Leaf)) { throw "Không tìm thấy icon ứng dụng: $iconPath" }
    $icon = New-Object System.Drawing.Icon($iconPath)
    $Form.Icon = $icon
    $Form.AutoScaleMode = [System.Windows.Forms.AutoScaleMode]::Dpi
    $Form.Add_Disposed({ $icon.Dispose() }.GetNewClosure())
    $result = [HPNetWindowsIdentity]::SetCurrentProcessExplicitAppUserModelID($AppId)
    if ($result -ne 0) { throw "Không cấu hình được AppUserModelID (HRESULT $result)." }
}

function Set-HPNetProgressRunning {
    param($ProgressBar, $ProgressLabel, [string]$Text = 'Đang xử lý…')
    if ($ProgressBar) { $ProgressBar.Style = 'Marquee'; $ProgressBar.MarqueeAnimationSpeed = 25 }
    if ($ProgressLabel) { $ProgressLabel.Text = $Text }
}

function Update-HPNetProgressFromLine {
    param($ProgressBar, $ProgressLabel, [string]$Line)
    if (-not $ProgressBar -or [string]::IsNullOrWhiteSpace($Line)) { return }
    $match = [regex]::Match($Line, '(?:\(|Đã kiểm tra\s+)(\d+)\s*/\s*(\d+)')
    if (-not $match.Success) { return }
    $current = [int]$match.Groups[1].Value
    $total = [int]$match.Groups[2].Value
    if ($total -le 0) { return }
    $ProgressBar.Style = 'Continuous'
    $ProgressBar.Minimum = 0
    $ProgressBar.Maximum = $total
    $ProgressBar.Value = [Math]::Min($current, $total)
    if ($ProgressLabel) { $ProgressLabel.Text = "Đang xử lý: $current/$total" }
}

function Set-HPNetProgressCompleted {
    param($ProgressBar, $ProgressLabel, [string]$Text = 'Hoàn tất')
    if ($ProgressBar) {
        $ProgressBar.Style = 'Continuous'
        if ($ProgressBar.Maximum -lt 1) { $ProgressBar.Maximum = 1 }
        $ProgressBar.Value = $ProgressBar.Maximum
    }
    if ($ProgressLabel) { $ProgressLabel.Text = $Text }
}

function Set-HPNetProgressStopped {
    param($ProgressBar, $ProgressLabel, [string]$Text = 'Đã dừng')
    if ($ProgressBar) { $ProgressBar.Style = 'Continuous' }
    if ($ProgressLabel) { $ProgressLabel.Text = $Text }
}

function New-HPNetSplitWorkspace {
    param(
        [Parameter(Mandatory=$true)]$MainPanel,
        [Parameter(Mandatory=$true)][object[]]$InputControls,
        [Parameter(Mandatory=$true)]$ProgressPanel,
        [Parameter(Mandatory=$true)]$LogLabel,
        [Parameter(Mandatory=$true)]$StatusBox,
        [string]$ActivityTitle = 'HOẠT ĐỘNG',
        [string]$ActivityHint = 'Tiến độ và thông báo của phiên chạy hiện tại.'
    )
    $MainPanel.Controls.Clear()
    $MainPanel.Padding = New-Object System.Windows.Forms.Padding(15)
    $workspace = New-Object System.Windows.Forms.TableLayoutPanel
    $workspace.Dock = 'Fill'
    $workspace.ColumnCount = 2
    $workspace.RowCount = 1
    $workspace.BackColor = [System.Drawing.Color]::Transparent
    [void]$workspace.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::Percent, 64)))
    [void]$workspace.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::Percent, 36)))
    [void]$workspace.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::Percent, 100)))

    $inputPanel = New-Object System.Windows.Forms.FlowLayoutPanel
    $inputPanel.Dock = 'Fill'
    $inputPanel.FlowDirection = 'TopDown'
    $inputPanel.WrapContents = $false
    $inputPanel.AutoScroll = $true
    $inputPanel.Padding = New-Object System.Windows.Forms.Padding(0, 0, 10, 0)
    foreach ($control in @($InputControls | Where-Object { $null -ne $_ })) {
        $inputPanel.Controls.Add($control)
    }

    $activityPanel = New-Object System.Windows.Forms.TableLayoutPanel
    $activityPanel.Dock = 'Fill'
    $activityPanel.ColumnCount = 1
    $activityPanel.RowCount = 5
    $activityPanel.Padding = New-Object System.Windows.Forms.Padding(16, 12, 12, 12)
    $activityPanel.BackColor = [System.Drawing.Color]::White
    $activityPanel.CellBorderStyle = 'Single'
    foreach ($height in @(34, 44, 64, 30)) {
        [void]$activityPanel.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::Absolute, $height)))
    }
    [void]$activityPanel.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::Percent, 100)))

    $activityTitleLabel = New-Object System.Windows.Forms.Label
    $activityTitleLabel.Text = $ActivityTitle
    $activityTitleLabel.Dock = 'Fill'
    $activityTitleLabel.Font = New-Object System.Drawing.Font('Segoe UI', 10.5, [System.Drawing.FontStyle]::Bold)
    $activityTitleLabel.ForeColor = [System.Drawing.Color]::FromArgb(41, 50, 60)
    $activityHintLabel = New-Object System.Windows.Forms.Label
    $activityHintLabel.Text = $ActivityHint
    $activityHintLabel.Dock = 'Fill'
    $activityHintLabel.AutoEllipsis = $true
    $activityHintLabel.Font = New-Object System.Drawing.Font('Segoe UI', 8.5)
    $activityHintLabel.ForeColor = [System.Drawing.Color]::FromArgb(100, 100, 100)

    $ProgressPanel.Dock = 'Fill'
    $ProgressPanel.Margin = New-Object System.Windows.Forms.Padding(0, 3, 0, 3)
    $progressLabel = @($ProgressPanel.Controls | Where-Object { $_ -is [System.Windows.Forms.Label] }) | Select-Object -First 1
    $progressBar = @($ProgressPanel.Controls | Where-Object { $_ -is [System.Windows.Forms.ProgressBar] }) | Select-Object -First 1
    if ($progressLabel) { $progressLabel.Dock = 'Top'; $progressLabel.Height = 24; $progressLabel.Location = New-Object System.Drawing.Point(0, 0) }
    if ($progressBar) { $progressBar.Dock = 'Bottom'; $progressBar.Height = 20; $progressBar.Location = New-Object System.Drawing.Point(0, 0); $progressBar.Margin = New-Object System.Windows.Forms.Padding(0) }
    $LogLabel.Dock = 'Fill'
    $LogLabel.Text = 'NHẬT KÝ PHIÊN CHẠY'
    $LogLabel.AutoSize = $false
    $LogLabel.Margin = New-Object System.Windows.Forms.Padding(0)
    $LogLabel.TextAlign = 'MiddleLeft'
    $StatusBox.Dock = 'Fill'
    $StatusBox.Margin = New-Object System.Windows.Forms.Padding(0)

    $activityPanel.Controls.Add($activityTitleLabel, 0, 0)
    $activityPanel.Controls.Add($activityHintLabel, 0, 1)
    $activityPanel.Controls.Add($ProgressPanel, 0, 2)
    $activityPanel.Controls.Add($LogLabel, 0, 3)
    $activityPanel.Controls.Add($StatusBox, 0, 4)
    $workspace.Controls.Add($inputPanel, 0, 0)
    $workspace.Controls.Add($activityPanel, 1, 0)
    $MainPanel.Controls.Add($workspace)
    return @{ Workspace = $workspace; InputPanel = $inputPanel; ActivityPanel = $activityPanel; ActivityTitle = $activityTitleLabel }
}

function New-HPNetFooter {
    param([Parameter(Mandatory=$true)]$Form, [string]$Text = 'Sẵn sàng')
    $footer = New-Object System.Windows.Forms.Panel
    $footer.Dock = 'Bottom'
    $footer.Height = 28
    $footer.BackColor = [System.Drawing.Color]::White
    $footer.BorderStyle = 'FixedSingle'
    $label = New-Object System.Windows.Forms.Label
    $label.Dock = 'Fill'
    $label.Text = "●  $Text"
    $label.ForeColor = [System.Drawing.Color]::FromArgb(46, 125, 50)
    $label.Font = New-Object System.Drawing.Font('Segoe UI', 8.5)
    $label.Padding = New-Object System.Windows.Forms.Padding(12, 5, 0, 0)
    $footer.Controls.Add($label)
    $Form.Controls.Add($footer)
    return $label
}

function Set-HPNetFooterState {
    param($Label, [string]$Text, [ValidateSet('Ready','Running','Success','Warning','Error','Stopped')][string]$State = 'Ready')
    if (-not $Label) { return }
    $Label.Text = "●  $Text"
    $Label.ForeColor = switch ($State) {
        'Success' { [System.Drawing.Color]::FromArgb(46, 125, 50); break }
        'Warning' { [System.Drawing.Color]::FromArgb(183, 110, 0); break }
        'Error' { [System.Drawing.Color]::FromArgb(197, 61, 69); break }
        'Stopped' { [System.Drawing.Color]::FromArgb(117, 117, 117); break }
        'Running' { [System.Drawing.Color]::FromArgb(36, 88, 197); break }
        default { [System.Drawing.Color]::FromArgb(46, 125, 50) }
    }
}
