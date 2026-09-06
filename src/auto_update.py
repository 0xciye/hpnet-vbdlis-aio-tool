"""Small, dependency-free updater for verified GitHub Release ZIPs."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
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


def build_info():
    path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / "build_info.json"
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {"version": "development", "commit": ""}


def parse_release(payload, current_version):
    tag = str(payload.get("tag_name", "")).strip()
    if not tag or payload.get("draft") or payload.get("prerelease") or tag == current_version:
        return None
    assets = {asset.get("name"): asset.get("browser_download_url") for asset in payload.get("assets", [])}
    for asset_name in (REMOTE_ASSET_NAME, ASSET_NAME):
        checksum_name = f"{asset_name}.sha256"
        if assets.get(asset_name) and assets.get(checksum_name):
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


def _safe_extract(archive, destination):
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
        return _safe_extract(archive, root / "extracted")
    except Exception:
        shutil.rmtree(root, ignore_errors=True)
        raise


def launch_installer(new_app):
    if not getattr(sys, "frozen", False):
        raise RuntimeError("Chỉ cập nhật tự động trên bản ứng dụng đã đóng gói.")
    current = Path(sys.executable).resolve().parent
    parent = current.parent
    if current.name != APP_FOLDER or not (current / EXE_NAME).is_file():
        raise RuntimeError("Không xác định được thư mục cài đặt hiện tại.")
    probe = parent / f".hpnet-update-write-test-{os.getpid()}"
    probe.write_text("ok", encoding="ascii")
    probe.unlink()
    script_fd, script_name = tempfile.mkstemp(prefix="hpnet-vbdlis-installer-", suffix=".ps1")
    os.close(script_fd)
    script_path = Path(script_name)
    script_path.write_text(r'''param([int]$AppPid,[string]$Current,[string]$NewApp,[string]$Exe)
$ErrorActionPreference = 'Stop'
$parent = Split-Path -Parent $Current
$previous = Join-Path $parent 'HPNET & VBDLIS Tools.previous'
$log = Join-Path $env:TEMP 'hpnet-vbdlis-update.log'
function Write-UpdateLog([string]$Message) {
    "$(Get-Date -Format o) $Message" | Add-Content -LiteralPath $log -Encoding utf8
}
if ((Split-Path -Parent $previous) -ne $parent) { throw 'Unsafe update path.' }
Write-UpdateLog "installer started pid=$AppPid current=$Current new=$NewApp"
Wait-Process -Id $AppPid -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 800
for ($attempt = 1; $attempt -le 20; $attempt++) {
    try {
        if (Test-Path -LiteralPath $previous) { Remove-Item -LiteralPath $previous -Recurse -Force }
        Move-Item -LiteralPath $Current -Destination $previous
        Move-Item -LiteralPath $NewApp -Destination $Current
        Write-UpdateLog "install succeeded attempt=$attempt"
        Start-Process -FilePath (Join-Path $Current $Exe) -WorkingDirectory $Current -WindowStyle Hidden
        exit 0
    } catch {
        Write-UpdateLog "attempt=$attempt error=$($_.Exception.Message)"
        if (Test-Path -LiteralPath $Current) { Remove-Item -LiteralPath $Current -Recurse -Force -ErrorAction SilentlyContinue }
        if ((Test-Path -LiteralPath $previous) -and -not (Test-Path -LiteralPath $Current)) {
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
        "-NewApp", str(new_app), "-Exe", EXE_NAME,
    ], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
