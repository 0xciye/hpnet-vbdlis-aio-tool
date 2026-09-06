from pathlib import Path


def test_successful_build_replaces_old_staging_and_copies_default_zip_to_desktop():
    script = (Path(__file__).parents[1] / "build_release.ps1").read_text(encoding="utf-8-sig")
    assert "$productName = 'HPNet VBDLIS AIO Tool'" in script
    assert "[switch]$SkipDesktopCopy" in script
    assert "$env:SUITE_BUILD_INFO = $buildInfo" in script
    assert "[Environment]::GetFolderPath('Desktop')" in script
    assert "DESKTOP_COPY_PASS" in script
    assert "Get-ChildItem -LiteralPath $buildBase -Directory" in script
    assert "Get-ChildItem -LiteralPath $releaseBase -Directory" in script
    assert script.index("ZIP verification failed") < script.index("A successful release supersedes")


def test_packaged_launcher_contains_build_metadata_and_updater():
    root = Path(__file__).parents[1]
    spec = (root / "src/HPNET_VBDLIS_Tools.spec").read_text(encoding="utf-8")
    workflow = (root / ".github/workflows/auto-release.yml").read_text(encoding="utf-8")
    assert "'auto_update'" in spec and "SUITE_BUILD_INFO" in spec
    assert "branches: [main]" in workflow
    assert "contents: write" in workflow
    assert "HPNet VBDLIS AIO Tool.zip.sha256" in workflow
