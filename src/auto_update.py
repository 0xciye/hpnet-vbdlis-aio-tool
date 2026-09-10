"""Small, dependency-free updater for verified GitHub Release ZIPs."""
import hashlib
from http.client import IncompleteRead
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path, PurePosixPath
from urllib.error import URLError
from urllib.request import Request, urlopen
from zipfile import ZipFile


REPOSITORY = "0xciye/hpnet-vbdlis-aio-tool"
ASSET_NAME = "HPNet VBDLIS AIO Tool.zip"
REMOTE_ASSET_NAME = "HPNet.VBDLIS.AIO.Tool.zip"
APP_FOLDER = "HPNET & VBDLIS Tools"
EXE_NAME = f"{APP_FOLDER}.exe"
API_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
RELEASES_API_URL = f"https://api.github.com/repos/{REPOSITORY}/releases?per_page=100"
MAX_DOWNLOAD_BYTES = 1_000_000_000
MAX_EXTRACTED_BYTES = 2_000_000_000
MAX_DOWNLOAD_SECONDS = 20 * 60
MAX_DOWNLOAD_ATTEMPTS = 5
MAX_RELEASE_NOTES_CHARS = 8_000


def _semantic_version(value):
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", str(value).strip(), re.IGNORECASE)
    return tuple(map(int, match.groups())) if match else None


def _release_asset_url(value, tag=None):
    from urllib.parse import urlsplit
    try:
        url = urlsplit(str(value))
    except ValueError:
        return False
    prefix = f"/{REPOSITORY}/releases/download/{tag}/" if tag else f"/{REPOSITORY}/releases/download/"
    return url.scheme == "https" and url.hostname == "github.com" and url.path.startswith(prefix)


def _release_notes(value):
    notes = str(value or "").strip()
    if len(notes) > MAX_RELEASE_NOTES_CHARS:
        return notes[:MAX_RELEASE_NOTES_CHARS].rstrip() + "\n\n[Đã rút gọn]"
    return notes


def build_info():
    path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / "build_info.json"
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {"version": "development", "commit": ""}


def cleanup_legacy_previous_dirs(current=None):
    """Remove backup folders left by updater versions before direct replacement.

    Older releases moved the installation directory to either
    ``<folder>.previous`` or ``<folder>.previous-<uuid>``. The current updater
    no longer creates those folders, but they can remain after upgrading from
    an older release. Cleanup is limited to sibling directories using those
    exact legacy names and ignores failures so startup is never blocked.
    """
    if current is None:
        if not getattr(sys, "frozen", False):
            return []
        current = Path(sys.executable).resolve().parent
    current = Path(current).resolve()
    parent = current.parent
    removed = []
    try:
        candidates = list(parent.iterdir())
    except OSError:
        return removed
    prefix = f"{current.name}.previous"
    for candidate in candidates:
        if candidate == current or not candidate.is_dir() or candidate.is_symlink():
            continue
        if candidate.name != prefix and not re.fullmatch(re.escape(prefix) + r"-[0-9a-f]{32}", candidate.name, re.IGNORECASE):
            continue
        try:
            shutil.rmtree(candidate)
            removed.append(candidate)
        except OSError:
            continue
    return removed


def parse_release(payload, current_version):
    tag = str(payload.get("tag_name", "")).strip()
    remote = _semantic_version(tag)
    current = _semantic_version(current_version)
    if (not remote or payload.get("draft") or payload.get("prerelease") or
            (current is not None and remote <= current)):
        return None
    assets = {asset.get("name"): asset.get("browser_download_url") for asset in payload.get("assets", [])}
    for asset_name in (REMOTE_ASSET_NAME, ASSET_NAME):
        checksum_name = f"{asset_name}.sha256"
        if (_release_asset_url(assets.get(asset_name), tag) and
                _release_asset_url(assets.get(checksum_name), tag)):
            return {
                "version": tag,
                "zip_url": assets[asset_name],
                "checksum_url": assets[checksum_name],
                "release_notes": _release_notes(payload.get("body")),
            }
    return None


def parse_release_history(payloads, current_version, target_version):
    current = _semantic_version(current_version)
    target = _semantic_version(target_version)
    if current is None or target is None:
        return []
    history = []
    for payload in payloads if isinstance(payloads, list) else []:
        if payload.get("draft") or payload.get("prerelease"):
            continue
        tag = str(payload.get("tag_name", "")).strip()
        version = _semantic_version(tag)
        if version is None or not current < version <= target:
            continue
        history.append({"version": tag, "release_notes": _release_notes(payload.get("body"))})
    return sorted(history, key=lambda item: _semantic_version(item["version"]))


def check_for_update():
    request = Request(API_URL, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "HPNet-VBDLIS-AIO-Updater",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    with urlopen(request, timeout=8) as response:
        payload = json.loads(response.read(2_000_000))
    current_version = build_info().get("version", "development")
    release = parse_release(payload, current_version)
    if not release:
        return None
    try:
        history_request = Request(RELEASES_API_URL, headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "HPNet-VBDLIS-AIO-Updater",
            "X-GitHub-Api-Version": "2022-11-28",
        })
        with urlopen(history_request, timeout=8) as response:
            history_payload = json.loads(response.read(4_000_000))
        release["release_history"] = parse_release_history(
            history_payload, current_version, release["version"]
        ) or [{"version": release["version"], "release_notes": release["release_notes"]}]
    except (OSError, ValueError, TypeError):
        release["release_history"] = [{"version": release["version"], "release_notes": release["release_notes"]}]
    return release


def fetch_latest_version():
    """Return the latest published tag for display in the desktop launcher."""
    request = Request(API_URL, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "HPNet-VBDLIS-AIO-Updater",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    with urlopen(request, timeout=8) as response:
        payload = json.loads(response.read(2_000_000))
    tag = str(payload.get("tag_name", "")).strip()
    if not tag or payload.get("draft") or payload.get("prerelease"):
        return None
    return tag


def _download(url, target, limit=MAX_DOWNLOAD_BYTES, progress=None):
    total = target.stat().st_size if target.exists() else 0
    started = time.monotonic()
    last_error = None
    for attempt in range(1, MAX_DOWNLOAD_ATTEMPTS + 1):
        headers = {"User-Agent": "HPNet-VBDLIS-AIO-Updater"}
        if total:
            headers["Range"] = f"bytes={total}-"
        request = Request(url, headers=headers)
        try:
            with urlopen(request, timeout=30) as response:
                status = getattr(response, "status", response.getcode())
                resumed = total > 0 and status == 206
                if total and not resumed:
                    total = 0
                remaining = int(response.headers.get("Content-Length", "0") or 0)
                expected_total = total + remaining if remaining else 0
                if expected_total > limit:
                    raise ValueError("Bản cập nhật vượt quá giới hạn dung lượng an toàn.")
                if progress:
                    progress(total, expected_total)
                with target.open("ab" if resumed else "wb") as output:
                    while chunk := response.read(1024 * 1024):
                        total += len(chunk)
                        if total > limit:
                            raise ValueError("Bản cập nhật vượt quá giới hạn dung lượng an toàn.")
                        if time.monotonic() - started > MAX_DOWNLOAD_SECONDS:
                            raise TimeoutError("Tải bản cập nhật quá 20 phút. Hãy kiểm tra mạng rồi thử lại.")
                        output.write(chunk)
                        if progress:
                            progress(total, expected_total)
                if expected_total and total < expected_total:
                    raise ConnectionError("Máy chủ ngắt dữ liệu trước khi tải xong.")
                return
        except ValueError:
            raise
        except TimeoutError as error:
            if str(error).startswith("Tải bản cập nhật"):
                raise
            last_error = error
            total = target.stat().st_size if target.exists() else 0
            if attempt < MAX_DOWNLOAD_ATTEMPTS:
                time.sleep(attempt)
        except (IncompleteRead, OSError, URLError) as error:
            last_error = error
            total = target.stat().st_size if target.exists() else 0
            if attempt < MAX_DOWNLOAD_ATTEMPTS:
                time.sleep(attempt)
    raise ConnectionError(
        f"Mạng bị ngắt khi tải bản cập nhật. Đã thử lại {MAX_DOWNLOAD_ATTEMPTS} lần; hãy kiểm tra mạng rồi thử lại."
    ) from last_error


def _safe_extract(archive, destination, expected_version=None):
    with ZipFile(archive) as package:
        extracted_size = 0
        for item in package.infolist():
            path = PurePosixPath(item.filename.replace("\\", "/"))
            mode = item.external_attr >> 16
            extracted_size += item.file_size
            if (not path.parts or path.is_absolute() or ".." in path.parts or
                    ":" in path.parts[0] or mode & 0o170000 == 0o120000 or
                    extracted_size > MAX_EXTRACTED_BYTES):
                raise ValueError("ZIP cập nhật chứa đường dẫn không an toàn.")
        package.extractall(destination)
    app = destination / APP_FOLDER
    if not (app / EXE_NAME).is_file():
        raise ValueError("ZIP cập nhật không có đúng cấu trúc ứng dụng.")
    if expected_version:
        try:
            metadata = json.loads((app / "_internal/build_info.json").read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            raise ValueError("ZIP cập nhật thiếu thông tin phiên bản hợp lệ.")
        if metadata.get("version") != expected_version or metadata.get("repository") != REPOSITORY:
            raise ValueError("ZIP cập nhật không khớp phiên bản hoặc kho phát hành.")
    return app


def download_update(release, progress=None):
    root = Path(tempfile.mkdtemp(prefix="hpnet-vbdlis-update-"))
    archive = root / ASSET_NAME
    checksum = root / f"{ASSET_NAME}.sha256"
    try:
        _download(release["zip_url"], archive, progress=progress)
        _download(release["checksum_url"], checksum, 4096)
        expected = checksum.read_text(encoding="ascii").strip().split()[0].lower()
        digest = hashlib.sha256()
        with archive.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
        actual = digest.hexdigest()
        if len(expected) != 64 or expected != actual:
            raise ValueError("Mã SHA-256 của bản cập nhật không khớp.")
        return _safe_extract(archive, root / "extracted", release["version"])
    except Exception:
        shutil.rmtree(root, ignore_errors=True)
        raise


def launch_installer(new_app, expected_version=None):
    if not getattr(sys, "frozen", False):
        raise RuntimeError("Chỉ cập nhật tự động trên bản ứng dụng đã đóng gói.")
    current = Path(sys.executable).resolve().parent
    parent = current.parent
    if current == parent or not (current / EXE_NAME).is_file() or not (current / "_internal").is_dir():
        raise RuntimeError("Thư mục ứng dụng thiếu file cần thiết. Hãy giải nén đầy đủ bản tải xuống rồi thử lại.")
    probe = parent / f".hpnet-update-write-test-{os.getpid()}"
    probe.write_text("ok", encoding="ascii")
    probe.unlink()
    script_fd, script_name = tempfile.mkstemp(prefix="hpnet-vbdlis-installer-", suffix=".ps1")
    os.close(script_fd)
    script_path = Path(script_name)
    script_path.write_text(r'''param([int]$AppPid,[string]$Current,[string]$NewApp,[string]$Exe,[string]$Version,[switch]$SkipLaunch)
$ErrorActionPreference = 'Stop'
$parent = Split-Path -Parent $Current
$log = Join-Path $env:TEMP 'hpnet-vbdlis-update.log'
function Write-UpdateLog([string]$Message) {
    "$(Get-Date -Format o) $Message" | Add-Content -LiteralPath $log -Encoding utf8
}
function Copy-UserState([string]$OldApp) {
    $stateBase = Join-Path $env:LOCALAPPDATA 'HPNet VBDLIS AIO Tool'
    $tools = @(
        @('Downloader','Downloader\HPNet PDF Downloader - VNEID APP',@('cau_hinh.json','du_lieu_dang_nhap_vneid')),
        @('Upload','Upload\HPNet Upload VB Du Thao - VNEID APP',@('cau_hinh.json','profiles.json','du_lieu_dang_nhap_vneid','nhat_ky','trang_thai_da_up.json')),
        @('Duyet','Duyet\HPNet Duyet VB Du Thao - VNEID APP',@('cau_hinh.json','profiles.json','du_lieu_dang_nhap_vneid','nhat_ky','ket_qua_quet_moi_nhat.json'))
    )
    foreach ($tool in $tools) {
        $destinationRoot = Join-Path $stateBase $tool[0]
        New-Item -ItemType Directory -Force -Path $destinationRoot | Out-Null
        $legacyRoot = Join-Path (Join-Path $OldApp '_internal\nodes_tools') $tool[1]
        foreach ($name in $tool[2]) {
            $source = Join-Path $legacyRoot $name; $destination = Join-Path $destinationRoot $name
            if ((Test-Path -LiteralPath $source) -and -not (Test-Path -LiteralPath $destination)) {
                Copy-Item -LiteralPath $source -Destination $destination -Recurse
            }
        }
    }
}
Write-UpdateLog "installer started pid=$AppPid current=$Current new=$NewApp"
for ($wait = 1; $wait -le 50; $wait++) {
    if (-not (Get-Process -Id $AppPid -ErrorAction SilentlyContinue)) { break }
    Start-Sleep -Milliseconds 200
}
if (Get-Process -Id $AppPid -ErrorAction SilentlyContinue) {
    Write-UpdateLog "launcher did not exit after 10 seconds; stopping pid=$AppPid"
    Stop-Process -Id $AppPid -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Milliseconds 1200
function Stop-AppProcesses([string]$Root,[int]$KeepPid) {
    # Các công cụ HPNet chạy Node.js nằm trong _internal. Windows sẽ khóa
    # node.exe nếu còn tiến trình con, khiến việc thay thư mục cài đặt thất bại.
    $rootFull = [IO.Path]::GetFullPath($Root).TrimEnd('\') + '\'
    for ($round = 1; $round -le 10; $round++) {
        $stopped = 0
        try {
            $processes = @(Get-CimInstance Win32_Process -ErrorAction Stop)
        } catch {
            Write-UpdateLog "cannot enumerate app processes: $($_.Exception.Message)"
            $processes = @()
        }
        foreach ($item in $processes) {
            if ([int]$item.ProcessId -eq $KeepPid) { continue }
            $path = [string]$item.ExecutablePath
            if (-not $path -or -not $path.StartsWith($rootFull, [StringComparison]::OrdinalIgnoreCase)) { continue }
            try {
                Stop-Process -Id ([int]$item.ProcessId) -Force -ErrorAction Stop
                $stopped++
                Write-UpdateLog "stopped app process pid=$($item.ProcessId) path=$path"
            } catch {
                Write-UpdateLog "cannot stop app process pid=$($item.ProcessId): $($_.Exception.Message)"
            }
        }
        if ($stopped -eq 0) { break }
        Start-Sleep -Milliseconds 300
    }
}
Stop-AppProcesses $Current $AppPid
Copy-UserState $Current
for ($attempt = 1; $attempt -le 20; $attempt++) {
    try {
        $metadataPath = Join-Path $NewApp '_internal\build_info.json'
        if (-not (Test-Path -LiteralPath $metadataPath)) { throw 'Bản cập nhật thiếu thông tin phiên bản.' }
        $metadata = Get-Content -LiteralPath $metadataPath -Raw -Encoding utf8 | ConvertFrom-Json
        if ($Version -and [string]$metadata.version -ne $Version) { throw "Bản cập nhật không đúng phiên bản yêu cầu: $($metadata.version)." }
        # Thay trực tiếp thư mục cài đặt; không tạo bản sao .previous.
        if (Test-Path -LiteralPath $Current) { Remove-Item -LiteralPath $Current -Recurse -Force }
        if (-not (Test-Path -LiteralPath $NewApp)) { throw 'Không còn thư mục cập nhật tạm.' }
        Move-Item -LiteralPath $NewApp -Destination $Current
        Write-UpdateLog "install succeeded attempt=$attempt version=$($metadata.version)"
        if (-not $SkipLaunch) {
            Start-Process -FilePath (Join-Path $Current $Exe) -WorkingDirectory $Current -WindowStyle Hidden
        }
        exit 0
    } catch {
        Write-UpdateLog "attempt=$attempt error=$($_.Exception.Message)"
        Start-Sleep -Milliseconds 750
    }
}
Write-UpdateLog 'install failed after 20 attempts'
throw 'Không thể thay thế bản cài đặt sau 20 lần thử.'
''', encoding="utf-8-sig")
    subprocess.Popen([
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden",
        "-File", str(script_path), "-AppPid", str(os.getpid()), "-Current", str(current),
        "-NewApp", str(new_app), "-Exe", EXE_NAME, "-Version", str(expected_version or ""),
    ], cwd=str(parent), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
