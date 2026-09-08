# HPNET UI design system

This document records the shared desktop UI rules used by the HPNET and VBDLIS tools. Existing workflows and file formats remain unchanged.

## Audit

| Application | UI framework | Main window | Long tasks | Current icon | Taskbar icon | UI issues addressed |
| --- | --- | --- | --- | --- | --- | --- |
| HPNET PDF Downloader | Windows Forms + Node | `HPNet-PDF-Downloader.ps1` | Page scan and downloads | `nodes_tools/Downloader/app_icon.ico` | Window icon + `HPNET.VBDLIS.Tools.Downloader` | Live output, real/indeterminate progress, stop state, dense filters, default PowerShell icon |
| HPNET Upload dự thảo | Windows Forms + Node | `HPNet-Upload-VB-Du-Thao.ps1` | Duplicate scan and sequential upload | `nodes_tools/Upload/app_icon.ico` | Window icon + `HPNET.VBDLIS.Tools.Upload` | Multiple folder/abstract input, real progress, live output, safe stop, default icon |
| HPNET Duyệt dự thảo | Windows Forms + Node | `HPNet-Duyet-VB-Du-Thao.ps1` | Full scan and sequential approval | `nodes_tools/Duyet/app_icon.ico` | Window icon + `HPNET.VBDLIS.Tools.Approve` | Multiple exact titles, two-step gate, real progress, live output, default icon |
| Tạo thông báo đất đai | PySide6 | `tools/notice_builder/ui.py` | Batch document generation | `tools/notice_builder/assets/app_icon.ico` | Qt window icon + suite AppUserModelID | Eight-step flow, determinate progress, activity, cancel and result states |
| VBDLIS Excel Builder | PySide6 | `tools/vbdlis_excel_builder/ui/main_window.py` | Validate and export workbook | `tools/vbdlis_excel_builder/resources/app_icon.ico` | Qt window icon + suite AppUserModelID | Five-step tabs, background worker, diagnostics and export state |
| Auto Rename | PySide6 | `tools/hpnet_file_generator/ui/main_window.py` | Batch file generation | `tools/hpnet_file_generator/assets/app_icon.ico` | Qt window icon + suite AppUserModelID | Shared theme, determinate progress, result table |
| Kiểm tra thửa trùng | PySide6 | `tools/duplicate_parcel/ui.py` | Workbook scan and cleanup | `tools/duplicate_parcel/assets/app_icon.ico` | Qt window icon + suite AppUserModelID | Shared theme, worker, indeterminate progress and preview gate |
| Chuẩn hóa dữ liệu | PySide6 | `tools/data_normalizer/ui.py` | Workbook scan and apply | `tools/data_normalizer/assets/app_icon.ico` | Qt window icon + suite AppUserModelID | Shared theme, worker, indeterminate progress and preview gate |
| PDF Cleaner | PySide6 | `tools/signed_pdf_cleaner/ui/main_window.py` | PDF scan and batch processing | `tools/signed_pdf_cleaner/app_icon.ico` | Qt window icon + suite AppUserModelID | Determinate progress, scan preview, warnings and completion summary |

## Tokens

The Qt tools use `launcher_ui.theme` as the shared token source. It exports `COLORS`, `SPACING`, `TYPOGRAPHY`, and `RADIUS`; the stylesheet resolves these tokens before it is applied:

- Canvas `#F5F7FB`, surface `#FFFFFF`, text `#172B42`, muted text `#53657A`.
- Primary `#2458C5`, hover `#1948A8`, pressed `#153B88`.
- Success `#2E7D32`, error `#C53D45`, border `#DCE4EF`, focus `#2458C5`.
- Spacing tokens are `xs=4`, `sm=8`, `md=12`, `lg=16`, and `xl=24` px.
- Radius tokens are `small=5`, `medium=8`, and `large=12` px.
- Typography tokens cover display, heading, body, caption and monospace; Segoe UI is the interface family and Consolas is used for activity output.

PowerShell tools follow the same visual intent with white surfaces, Segoe UI labels, clear action buttons, dark activity output and explicit warning/confirmation dialogs. `nodes_tools/hpnet_ui_common.ps1` is the shared Windows identity, DPI scaling and window-icon component.

## Shared and refactored components

- `launcher_ui.theme`: shared colors, spacing, typography, radii, button/input states and focus treatment.
- `launcher_ui.view`: responsive application shell, navigation, searchable cards, indeterminate launch feedback and toast results.
- `tools.qt_worker.Worker`: reusable non-blocking worker used by the Excel utilities.
- `nodes_tools/hpnet_ui_common.ps1`: shared split workspace, footer status, icon, AppUserModelID and real progress-state helpers for the three PowerShell applications.
- `tools/create_hpnet_icons.py`: deterministic source for the nine related but distinct Windows icon assets.

## Progress and safety

Long operations run in a worker process/thread so the UI continues to pump events. PowerShell tools show a real determinate bar when Node reports a numeric `current/total` checkpoint and use an indeterminate bar while HPNet has not supplied a trustworthy total; there is no synthetic percentage. Upload and approval remain sequential because each item is re-checked immediately before the action and verified after it. This avoids fast duplicate clicks or approving a record whose state changed while the batch was running.

Each long task exposes an idle, running, completed, error or cancelled message through the activity workspace and writes the detailed technical log beside the tool's user state. The PowerShell tools use a responsive two-column workspace: inputs and actions stay together on the left while progress and live output remain visible on the right.

## Icons and Windows integration

`tools/create_hpnet_icons.py` generates the deterministic multi-size icon family (16 through 256 px). The three C# launchers are compiled with their own icon using `tools/build_hpnet_launchers.ps1`; the launcher executable therefore supplies the window, taskbar, Alt+Tab and shortcut identity. Each PowerShell tool now uses the same split workspace and footer status treatment. Qt windows set the matching icon explicitly and the suite sets a stable AppUserModelID in `launcher.py`.

When a release is built, the launcher build, embedded resources, packaged smoke test, all nine multi-size icon assets, four executable icon resource groups and the three PowerShell window icons are checked by `verify_release.py`. Upload and approval UI self-tests render their real WinForms windows off screen and verify layout without changing HPNet data.
