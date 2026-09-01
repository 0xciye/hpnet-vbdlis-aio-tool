"""Verify packaged resources and offline Node checks; never operate HPNet."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parent


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify(folder, archive=None):
    import pefile
    executable = folder / "HPNET & VBDLIS Tools.exe"
    pe = pefile.PE(str(executable))
    try:
        resource_types = {entry.id for entry in pe.DIRECTORY_ENTRY_RESOURCE.entries}
        assert {3, 14}.issubset(resource_types), "Missing embedded EXE icon"
    finally:
        pe.close()
    source_nodes = ROOT / "src/nodes_tools"
    packaged_nodes = folder / "_internal/nodes_tools"
    originals = {p.relative_to(source_nodes).as_posix(): p for p in source_nodes.rglob("*") if p.is_file()}
    packaged = {p.relative_to(packaged_nodes).as_posix(): p for p in packaged_nodes.rglob("*") if p.is_file()}
    assert originals.keys() == packaged.keys(), "Packaged HPNet files missing or unexpected"
    for name in originals:
        assert digest(originals[name]) == digest(packaged[name]), f"Changed HPNet file: {name}"
    for worker in packaged_nodes.glob("*/*/*.cjs"):
        node = packaged_nodes / "runtime/node.exe"
        assert node.is_file(), f"Missing shared portable Node runtime for {worker.name}"
        for flags in (["--check", str(worker)], [str(worker), "--self-test"]):
            result = subprocess.run([str(node), *flags], cwd=worker.parent,
                                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                                    timeout=60, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            assert result.returncode == 0, result.stdout + result.stderr
            if "--self-test" in flags:
                assert "NODE_SELF_TEST_OK" in result.stdout, result.stdout
                print(worker.name + ": " + result.stdout.strip())
    assert len(list(packaged_nodes.glob("*/*/*.cjs"))) == 3
    downloader = packaged_nodes / "Downloader/HPNet PDF Downloader - VNEID APP"
    downloader_ui = downloader / "HPNet-PDF-Downloader.ps1"
    for flag, marker in (("-SelfTest", '"SuffixParser"'), ("-UiSelfTest", "UI_SELF_TEST_OK")):
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(downloader_ui), flag],
            cwd=downloader, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        assert result.returncode == 0 and marker in result.stdout, result.stdout + result.stderr
        print(f"HPNet-PDF-Downloader.ps1 {flag}: PASS")
    for relative in ('template/MAU_22_THONG_BAO_XAC_NHAN_KET_QUA_DANG_KY_DAT_DAI.docx','config/legal_defaults.json','assets/app_icon.ico',
                     'assets/template_placeholder_preview.png',
                     'assets/ui-chevron-down.svg','assets/ui-chevron-up.svg','assets/ui-check.svg'):
        assert digest(ROOT/'src/tools/notice_builder'/relative)==digest(folder/'_internal/tools/notice_builder'/relative), f'Notice resource mismatch: {relative}'
    for original in (ROOT/'docs/HUONG_DAN_BAN_SUA.txt',ROOT/'Huong_dan_su_dung_chi_tiet.txt',ROOT/'README.txt'):
        assert digest(original)==digest(folder/'_internal/launcher_help'/original.name), f'Guide missing/truncated: {original.name}'
    assert {p.name for p in folder.iterdir()} == {"HPNET & VBDLIS Tools.exe","_internal"}, "Unexpected top-level release file"
    forbidden = {"cookies", "cookies.json", "login data", "storage-state.json", "storage_state.json", "__pycache__", ".pytest_cache", "tests", "test", "frozen-smoke.json", "KIEM_THU_TAO_THONG_BAO.md".lower(), "KIEM_TOAN_TICH_HOP.md".lower()}
    for path in folder.rglob("*"):
        # Playwright imports this runtime module from lib/index.js and program.js.
        # It is not the project's development test suite; Node resources above
        # are checked byte-for-byte so preserving it cannot hide added junk.
        if (path.is_dir() and path.is_relative_to(packaged_nodes)
                and path.as_posix().endswith('/runtime/node_modules/playwright/lib/mcp/test')):
            continue
        assert path.name.lower() not in forbidden, f"User/cache file in release: {path}"
    result = {"status": "PASS", "hpnet_files_identical": len(originals), "node_workers": 3, "pdf_downloader_powershell_tests": 2, "exe_icon": True, "embedded_guides":3,"clean_runtime_only":True}
    if archive:
        expected = {folder.name + "/" + p.relative_to(folder).as_posix(): p for p in folder.rglob("*") if p.is_file()}
        with ZipFile(archive) as zf:
            entries = [i for i in zf.infolist() if not i.is_dir()]
            assert len(entries) == len({i.filename for i in entries}), "Duplicate ZIP entries"
            assert {i.filename for i in entries} == expected.keys(), "ZIP contents do not match release folder"
            assert zf.testzip() is None
            for entry in entries:
                with zf.open(entry) as stream:
                    actual = hashlib.file_digest(stream, "sha256").hexdigest()
                assert actual == digest(expected[entry.filename]), entry.filename
        result.update(zip_files=len(entries), zip_sha256=digest(archive))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", type=Path, required=True)
    parser.add_argument("--zip", type=Path)
    args = parser.parse_args()
    verify(args.folder.resolve(), args.zip.resolve() if args.zip else None)
