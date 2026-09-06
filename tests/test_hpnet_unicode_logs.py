from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = (
    ROOT / "src/nodes_tools/Downloader/HPNet PDF Downloader - VNEID APP",
    ROOT / "src/nodes_tools/Upload/HPNet Upload VB Du Thao - VNEID APP",
    ROOT / "src/nodes_tools/Duyet/HPNet Duyet VB Du Thao - VNEID APP",
)


def test_hpnet_ui_reads_node_stdout_and_stderr_as_utf8():
    scripts = [next(folder.glob("HPNet-*.ps1")) for folder in TOOLS]
    for script in scripts:
        source = script.read_text(encoding="utf-8-sig")
        assert "StandardOutputEncoding=$utf8NoBom" in source.replace(" ", "")
        assert "StandardErrorEncoding=$utf8NoBom" in source.replace(" ", "")
        assert "new-objectsystem.text.utf8encoding($false)" in source.replace(" ", "").casefold()


def test_hpnet_text_and_csv_logs_keep_utf8_bom_for_windows_readers():
    node_scripts = [next(folder.glob("*.cjs")) for folder in TOOLS]
    for script in node_scripts:
        source = script.read_text(encoding="utf-8")
        assert "\\uFEFF" in source


def test_hpnet_user_state_lives_outside_install_folder():
    scripts = [next(folder.glob("HPNet-*.ps1")) for folder in TOOLS]
    for script in scripts:
        source = script.read_text(encoding="utf-8-sig")
        assert "GetFolderPath('LocalApplicationData')" in source
        assert "HPNet VBDLIS AIO Tool" in source
        assert "du_lieu_dang_nhap_vneid" in source
