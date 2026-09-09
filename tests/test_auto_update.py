import os
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest

import auto_update
from auto_update import APP_FOLDER, ASSET_NAME, EXE_NAME, REMOTE_ASSET_NAME, _safe_extract, parse_release


def payload(tag="v1.0.1"):
    return {"tag_name": tag, "draft": False, "prerelease": False, "assets": [
        {"name": REMOTE_ASSET_NAME, "browser_download_url": f"https://github.com/{auto_update.REPOSITORY}/releases/download/{tag}/app.zip"},
        {"name": f"{REMOTE_ASSET_NAME}.sha256", "browser_download_url": f"https://github.com/{auto_update.REPOSITORY}/releases/download/{tag}/app.zip.sha256"},
    ]}


def test_release_requires_new_version_and_both_verified_assets():
    assert parse_release(payload(), "v1.0.0")["version"] == "v1.0.1"
    assert parse_release(payload(), "v1.0.1") is None
    assert parse_release(payload("v1.0.0"), "v2.0.0") is None
    assert parse_release(payload("auto-2-def456"), "v1.0.0") is None
    incomplete = payload(); incomplete["assets"].pop()
    assert parse_release(incomplete, "v1.0.0") is None


def test_release_rejects_assets_outside_repository():
    untrusted = payload()
    untrusted["assets"][0]["browser_download_url"] = "https://example.test/app.zip"
    assert parse_release(untrusted, "v1.0.0") is None


def test_release_accepts_space_named_assets():
    space_payload = payload()
    space_payload["assets"] = [
        {"name": ASSET_NAME, "browser_download_url": f"https://github.com/{auto_update.REPOSITORY}/releases/download/v1.0.1/space.zip"},
        {"name": f"{ASSET_NAME}.sha256", "browser_download_url": f"https://github.com/{auto_update.REPOSITORY}/releases/download/v1.0.1/space.zip.sha256"},
    ]
    release = parse_release(space_payload, "v1.0.0")
    assert release["zip_url"].endswith("space.zip")


def test_safe_extract_accepts_app_and_rejects_traversal(tmp_path):
    good = tmp_path / "good.zip"
    with ZipFile(good, "w") as archive:
        archive.writestr(f"{APP_FOLDER}/{EXE_NAME}", b"exe")
    assert (_safe_extract(good, tmp_path / "good") / EXE_NAME).read_bytes() == b"exe"

    bad = tmp_path / "bad.zip"
    with ZipFile(bad, "w") as archive:
        archive.writestr("../outside.txt", b"bad")
    with pytest.raises(ValueError, match="không an toàn"):
        _safe_extract(bad, tmp_path / "bad")
    assert not (tmp_path / "outside.txt").exists()


def test_download_verifies_checksum_and_returns_extracted_app(tmp_path, monkeypatch):
    package = tmp_path / "source.zip"
    with ZipFile(package, "w") as archive:
        archive.writestr(f"{APP_FOLDER}/{EXE_NAME}", b"exe")
        archive.writestr(f"{APP_FOLDER}/_internal/build_info.json", '{"version":"v1.0.1","repository":"0xciye/hpnet-vbdlis-aio-tool"}')
    checksum = tmp_path / "source.sha256"
    checksum.write_text(f"{auto_update.hashlib.sha256(package.read_bytes()).hexdigest()}  {ASSET_NAME}", encoding="ascii")

    def copy_download(url, target, limit=auto_update.MAX_DOWNLOAD_BYTES):
        target.write_bytes(package.read_bytes() if url.endswith(".zip") else checksum.read_bytes())

    monkeypatch.setattr(auto_update, "_download", copy_download)
    app = auto_update.download_update({"version": "v1.0.1", "zip_url": "good.zip", "checksum_url": "good.sha256"})
    assert (app / EXE_NAME).read_bytes() == b"exe"


@pytest.mark.parametrize("folder", [APP_FOLDER, "HPNet máy mới"])
def test_installer_replaces_app_without_previous_copy(tmp_path, monkeypatch, folder):
    current = tmp_path / "install" / folder
    new_app = tmp_path / "download" / APP_FOLDER
    current.mkdir(parents=True); new_app.mkdir(parents=True)
    shutil.copy2(os.environ["COMSPEC"], current / EXE_NAME)
    shutil.copy2(os.environ["COMSPEC"], new_app / EXE_NAME)
    (current / "marker.txt").write_text("old", encoding="ascii")
    (new_app / "marker.txt").write_text("new", encoding="ascii")
    legacy = current / "_internal/nodes_tools/Upload/HPNet Upload VB Du Thao - VNEID APP"
    legacy.mkdir(parents=True)
    (legacy / "cau_hinh.json").write_text('{"saved": true}', encoding="utf-8")
    captured = {}
    fake_subprocess = SimpleNamespace(
        CREATE_NO_WINDOW=0,
        Popen=lambda args, **kwargs: captured.update(args=list(args), kwargs=kwargs),
    )
    monkeypatch.setattr(auto_update.sys, "frozen", True, raising=False)
    monkeypatch.setattr(auto_update.sys, "executable", str(current / EXE_NAME))
    monkeypatch.setattr(auto_update, "subprocess", fake_subprocess)
    auto_update.launch_installer(new_app)

    args = captured["args"]
    assert captured["kwargs"]["cwd"] == str(current.parent)
    installer = open(args[args.index("-File") + 1], encoding="utf-8-sig").read()
    assert "Stop-ProcessesInApp" not in installer
    assert "Stop-Process" not in installer
    assert "Copy-UserState $Current" in installer
    assert "-Previous" not in args
    assert "$Previous" not in installer
    args[args.index("-AppPid") + 1] = "2147483647"
    environment = {**os.environ, "LOCALAPPDATA": str(tmp_path / "state")}
    subprocess.run(args, check=True, env=environment)
    assert (current / "marker.txt").read_text(encoding="ascii") == "new"
    assert not list(current.parent.glob(f"{current.name}.previous-*"))
    assert (tmp_path / "state/HPNet VBDLIS AIO Tool/Upload/cau_hinh.json").is_file()


def test_cleanup_legacy_previous_dirs_removes_only_known_backup_names(tmp_path):
    current = tmp_path / "Công cụ đang dùng"
    current.mkdir()
    (tmp_path / "Công cụ đang dùng.previous").mkdir()
    (tmp_path / "Công cụ đang dùng.previous-0123456789abcdef0123456789abcdef").mkdir()
    (tmp_path / "Công cụ đang dùng.previous-keep-me").mkdir()
    (tmp_path / "other.previous").mkdir()

    removed = auto_update.cleanup_legacy_previous_dirs(current)

    assert {path.name for path in removed} == {
        "Công cụ đang dùng.previous",
        "Công cụ đang dùng.previous-0123456789abcdef0123456789abcdef",
    }
    assert current.is_dir()
    assert (tmp_path / "Công cụ đang dùng.previous-keep-me").is_dir()
    assert (tmp_path / "other.previous").is_dir()
