from zipfile import ZipFile

import pytest

import auto_update
from auto_update import APP_FOLDER, ASSET_NAME, EXE_NAME, _safe_extract, parse_release


def payload(tag="auto-2-def456"):
    return {"tag_name": tag, "draft": False, "prerelease": False, "assets": [
        {"name": ASSET_NAME, "browser_download_url": "https://example.test/app.zip"},
        {"name": f"{ASSET_NAME}.sha256", "browser_download_url": "https://example.test/app.zip.sha256"},
    ]}


def test_release_requires_new_version_and_both_verified_assets():
    assert parse_release(payload(), "auto-1-abc123")["version"] == "auto-2-def456"
    assert parse_release(payload(), "auto-2-def456") is None
    incomplete = payload(); incomplete["assets"].pop()
    assert parse_release(incomplete, "auto-1-abc123") is None


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
