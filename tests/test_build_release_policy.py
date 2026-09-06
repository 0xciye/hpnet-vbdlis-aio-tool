from pathlib import Path


def test_successful_build_replaces_old_staging_and_copies_default_zip_to_desktop():
    script = (Path(__file__).parents[1] / "build_release.ps1").read_text(encoding="utf-8-sig")
    assert "$productName = 'HPNet VBDLIS AIO Tool'" in script
    assert "[Environment]::GetFolderPath('Desktop')" in script
    assert "DESKTOP_COPY_PASS" in script
    assert "Get-ChildItem -LiteralPath $buildBase -Directory" in script
    assert "Get-ChildItem -LiteralPath $releaseBase -Directory" in script
    assert script.index("ZIP verification failed") < script.index("A successful release supersedes")
