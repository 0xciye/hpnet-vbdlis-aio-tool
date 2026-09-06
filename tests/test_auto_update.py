import os
import shutil
import subprocess
from types import SimpleNamespace
from zipfile import ZipFile

import pytest

import auto_update
from auto_update import APP_FOLDER, ASSET_NAME, EXE_NAME, REMOTE_ASSET_NAME, _safe_extract, parse_release


def payload(tag="auto-2-def456"):
    return {"tag_name": tag, "draft": False, "prerelease": False, "assets": [
        {"name": REMOTE_ASSET_NAME, "browser_download_url": "https://example.test/app.zip"},
        {"name": f"{REMOTE_ASSET_NAME}.sha256", "browser_download_url": "https://example.test/app.zip.sha256"},
    ]}


def test_release_requires_new_version_and_both_verified_assets():
    assert parse_release(payload(), "auto-1-abc123")["version"] == "auto-2-def456"
    assert parse_release(payload(), "auto-2-def456") is None
    incomplete = payload(); incomplete["assets"].pop()
    assert parse_release(incomplete, "auto-1-abc123") is None


def test_release_accepts_space_named_assets():
    space_payload = payload()
    space_payload["assets"] = [
        {"name": ASSET_NAME, "browser_download_url": "https://example.test/space.zip"},
        {"name": f"{ASSET_NAME}.sha256", "browser_download_url": "https://example.test/space.zip.sha256"},
    ]
    release = parse_release(space_payload, "auto-1-abc123")
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
    checksum = tmp_path / "source.sha256"
    checksum.write_text(f"{auto_update.hashlib.sha256(package.read_bytes()).hexdigest()}  {ASSET_NAME}", encoding="ascii")

    def copy_download(url, target, limit=auto_update.MAX_DOWNLOAD_BYTES):
        target.write_bytes(package.read_bytes() if url.endswith(".zip") else checksum.read_bytes())

    monkeypatch.setattr(auto_update, "_download", copy_download)
    app = auto_update.download_update({"zip_url": "good.zip", "checksum_url": "good.sha256"})
    assert (app / EXE_NAME).read_bytes() == b"exe"


def test_installer_replaces_app_and_keeps_previous_copy(tmp_path, monkeypatch):
    current = tmp_path / "install" / APP_FOLDER
    new_app = tmp_path / "download" / APP_FOLDER
    current.mkdir(parents=True); new_app.mkdir(parents=True)
    shutil.copy2(os.environ["COMSPEC"], current / EXE_NAME)
    shutil.copy2(os.environ["COMSPEC"], new_app / EXE_NAME)
    (current / "marker.txt").write_text("old", encoding="ascii")
    (new_app / "marker.txt").write_text("new", encoding="ascii")
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
    args[args.index("-AppPid") + 1] = "2147483647"
    subprocess.run(args, check=True)
    assert (current / "marker.txt").read_text(encoding="ascii") == "new"
    assert (tmp_path / "install" / f"{APP_FOLDER}.previous" / "marker.txt").read_text(encoding="ascii") == "old"
