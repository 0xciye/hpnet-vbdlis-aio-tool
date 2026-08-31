"""Read-only comparison of bundled tools against the user's original sources."""
from pathlib import Path
import ast
import hashlib
import json
import re
import zipfile

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent / "source code tool hpnet"
PACKAGES = ROOT.parent / "HPNET & VBDLIS"
IGNORED = {".venv", "venv", "__pycache__", "build", "dist", "release", "outputs", "logs", ".git"}

def normalized(text, tool):
    text = re.sub(rf"\btools\.{re.escape(tool)}\.", "", text)
    try:
        return ast.dump(ast.parse(text), include_attributes=False)
    except SyntaxError:
        return text

def audit():
    result = {}
    for original, tool in [("hpnet_file_generator", "hpnet_file_generator"), ("signed_pdf_cleaner", "signed_pdf_cleaner"), ("VBDLIS Excel Builder", "vbdlis_excel_builder")]:
        baseline = BASE / original
        current = ROOT / "src" / "tools" / tool
        same, changes, missing = [], [], []
        for file in sorted(baseline.rglob("*")):
            if not file.is_file() or any(p in IGNORED for p in file.relative_to(baseline).parts):
                continue
            if file.suffix not in {".py", ".json", ".xlsx", ".ico", ".svg"}:
                continue
            rel = file.relative_to(baseline)
            target = current / rel
            if not target.exists(): missing.append(str(rel)); continue
            a, b = file.read_bytes(), target.read_bytes()
            equal = a == b
            if file.suffix == ".py": equal = normalized(a.decode("utf-8-sig"), tool) == normalized(b.decode("utf-8-sig"), tool)
            (same if equal else changes).append(str(rel))
        result[tool] = {"same_count":len(same), "same":same, "changed":changes, "missing":missing}
    for package, group, folder in [("HPNet PDF Downloader - Cap Nhat.zip", "Downloader", "HPNet PDF Downloader - VNEID APP"),
        ("HPNet Upload VB Du Thao.zip", "Upload", "HPNet Upload VB Du Thao - VNEID APP"),
        ("HPNet Duyet VB Du Thao.zip", "Duyet", "HPNet Duyet VB Du Thao - VNEID APP")]:
        same, changes, missing = [], [], []
        with zipfile.ZipFile(PACKAGES / package) as archive:
            for entry in archive.infolist():
                if entry.is_dir(): continue
                rel = Path(*entry.filename.replace("\\", "/").split("/")[1:])
                target = ROOT / "src" / "nodes_tools" / group / folder / rel
                if not target.exists(): missing.append(str(rel)); continue
                (same if hashlib.sha256(archive.read(entry)).digest() == hashlib.sha256(target.read_bytes()).digest() else changes).append(str(rel))
        result[group] = {"same_count":len(same), "changed":changes, "missing":missing}
    return result

if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
