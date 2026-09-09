"""Small, dependency-free updater for verified GitHub Release ZIPs."""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path, PurePosixPath
from urllib.request import Request, urlopen
from zipfile import ZipFile


REPOSITORY = "0xciye/hpnet-vbdlis-aio-tool"
ASSET_NAME = "HPNet VBDLIS AIO Tool.zip"
REMOTE_ASSET_NAME = "HPNet.VBDLIS.AIO.Tool.zip"
APP_FOLDER = "HPNET & VBDLIS Tools"
EXE_NAME = f"{APP_FOLDER}.exe"
API_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
MAX_DOWNLOAD_BYTES = 1_000_000_000
MAX_EXTRACTED_BYTES = 2_000_000_000


def _semantic_version(value):
    match = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)", str(value).strip())
    return tuple(map(int, match.groups())) if match else None


def _release_asset_url(value, tag=None):
    from urllib.parse import urlsplit
    try:
        url = urlsplit(str(value))
    except ValueError:
        return False
    prefix = f"/{REPOSITORY}/releases/download/{tag}/" if tag else f"/{REPOSITORY}/releases/download/"
    return url.scheme == "https" and url.hostname == "github.com" and url.path.startswith(prefix)


def build_info():
    path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / "build_info.json"
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {"version": "development", "commit": ""}


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
            return {"version": tag, "zip_url": assets[asset_name], "checksum_url": assets[checksum_name]}
    return None


def check_for_update():
    request = Request(API_URL, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "HPNet-VBDLIS-AIO-Updater",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    with urlopen(request, timeout=8) as response:
        payload = json.loads(response.read(2_000_000))
    return parse_release(payload, build_info().get("version", "development"))


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


def _download(url, target, limit=MAX_DOWNLOAD_BYTES):
    request = Request(url, headers={"User-Agent": "HPNet-VBDLIS-AIO-Updater"})
    total = 0
    with urlopen(request, timeout=30) as response, target.open("wb") as output:
        declared = int(response.headers.get("Content-Length", "0") or 0)
        if declared > limit:
            raise ValueError("Bản cập nhật vượt quá giới hạn dung lượng an toàn.")
        while chunk := response.read(1024 * 1024):
            total += len(chunk)
            if total > limit:
                raise ValueError("Bản cập nhật vượt quá giới hạn dung lượng an toàn.")
            output.write(chunk)


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


def download_update(release):
    root = Path(tempfile.mkdtemp(prefix="hpnet-vbdlis-update-"))
    archive = root / ASSET_NAME
    checksum = root / f"{ASSET_NAME}.sha256"
    try:
        _download(release["zip_url"], archive)
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


def launch_installer(new_app):
    if not getattr(sys, "frozen", False):
        raise RuntimeError("Chỉ cập nhật tự động trên bản ứng dụng đã đóng gói.")
    current = Path(sys.executable).resolve().parent
    parent = current.parent
    if current == parent or not (current / EXE_NAME).is_file() or not (current / "_internal").is_dir():
        raise RuntimeError("Thư mục ứng dụng thiếu file cần thiết. Hãy giải nén đầy đủ bản tải xuống rồi thử lại.")
    previous = parent / f"{current.name}.previous-{uuid.uuid4().hex}"
    probe = parent / f".hpnet-update-write-test-{os.getpid()}"
    probe.write_text("ok", encoding="ascii")
    probe.unlink()
    script_fd, script_name = tempfile.mkstemp(prefix="hpnet-vbdlis-installer-", suffix=".ps1")
    os.close(script_fd)
    script_path = Path(script_name)
    script_path.write_text(r'''param([int]$AppPid,[string]$Current,[string]$NewApp,[string]$Exe,[string]$Previous)
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
if ((Split-Path -Parent $previous) -ne $parent) { throw 'Unsafe update path.' }
Write-UpdateLog "installer started pid=$AppPid current=$Current new=$NewApp"
Wait-Process -Id $AppPid -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 1200
Copy-UserState $Current
for ($attempt = 1; $attempt -le 20; $attempt++) {
    $movedCurrent = $false
    try {
        if (Test-Path -LiteralPath $previous) { throw 'Backup path already exists.' }
        Move-Item -LiteralPath $Current -Destination $previous
        $movedCurrent = $true
        Move-Item -LiteralPath $NewApp -Destination $Current
        Write-UpdateLog "install succeeded attempt=$attempt"
        Start-Process -FilePath (Join-Path $Current $Exe) -WorkingDirectory $Current -WindowStyle Hidden
        exit 0
    } catch {
        Write-UpdateLog "attempt=$attempt error=$($_.Exception.Message)"
        if ($movedCurrent -and (Test-Path -LiteralPath $Current)) { Remove-Item -LiteralPath $Current -Recurse -Force -ErrorAction SilentlyContinue }
        if ($movedCurrent -and (Test-Path -LiteralPath $previous) -and -not (Test-Path -LiteralPath $Current)) {
            Move-Item -LiteralPath $previous -Destination $Current -Force -ErrorAction SilentlyContinue
        }
        Start-Sleep -Milliseconds 750
    }
}
Write-UpdateLog 'install failed after 20 attempts'
throw 'Không thể thay thế bản cài đặt sau 20 lần thử.'
''', encoding="utf-8-sig")
    subprocess.Popen([
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden",
        "-File", str(script_path), "-AppPid", str(os.getpid()), "-Current", str(current),
        "-NewApp", str(new_app), "-Exe", EXE_NAME, "-Previous", str(previous),
    ], cwd=str(parent), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
