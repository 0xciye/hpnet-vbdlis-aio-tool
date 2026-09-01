"""Sync notice template from research/ into src/template/ and update evidence.

Run automatically by build_release.ps1 before PyInstaller packaging.
research/notice_template/MAU_22_*.docx is the single source of truth.
The copy in src/tools/notice_builder/template/ is always regenerated here.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from xml.dom import minidom

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_NAME = "MAU_22_THONG_BAO_XAC_NHAN_KET_QUA_DANG_KY_DAT_DAI.docx"
RESEARCH = ROOT / "research" / "notice_template" / TEMPLATE_NAME
PACKAGED = ROOT / "src" / "tools" / "notice_builder" / "template" / TEMPLATE_NAME
EVIDENCE = ROOT / "research" / "notice_template" / "template-evidence.json"

WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W14_NS = "http://schemas.microsoft.com/office/word/2010/wordml"
TOKEN = re.compile(r"\{\{([A-Z_0-9]+)\}\}")

# Paragraphs that had justified alignment fixed. Kept for spacing normalization.
NORMALIZE_PARAGRAPH_IDS = {
    "7C9943F6", "1ED125E3", "58A73022", "16BFFFF9", "657FD163",
    "03B7582C", "70AE63C5", "6D3675DF", "5D54EF36",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def node_text(node) -> str:
    return "".join(
        child.data for child in node.childNodes if child.nodeType == child.TEXT_NODE
    )


def normalize_text_nodes(paragraph):
    nodes = paragraph.getElementsByTagNameNS(WORD_NS, "t")
    for node in nodes:
        value = node_text(node)
        value = re.sub(r"[ \t]{2,}", " ", value)
        value = re.sub(r"[ \t]+([,;:.])", r"\1", value)
        while node.firstChild:
            node.removeChild(node.firstChild)
        node.appendChild(node.ownerDocument.createTextNode(value))
    for previous, current in zip(nodes, nodes[1:]):
        prev_text = previous.firstChild.data if previous.firstChild else ""
        curr_text = current.firstChild.data if current.firstChild else ""
        if prev_text.endswith(" ") and curr_text.startswith(" "):
            current.firstChild.data = curr_text.lstrip(" ")
    if nodes:
        last = nodes[-1]
        if last.firstChild:
            last.firstChild.data = last.firstChild.data.rstrip()


def normalize_package(source_bytes: bytes) -> bytes:
    """Apply spacing/alignment normalization (same as normalize_notice_template.py)."""
    source = ZipFile(BytesIO(source_bytes))
    document_xml = source.read("word/document.xml").decode("utf-8")
    document = minidom.parseString(document_xml.encode("utf-8"))
    changed = set()
    for paragraph in document.getElementsByTagNameNS(WORD_NS, "p"):
        para_id = (
            paragraph.getAttributeNS(W14_NS, "paraId")
            or paragraph.getAttribute("w14:paraId")
        )
        if para_id not in NORMALIZE_PARAGRAPH_IDS:
            continue
        old = paragraph.toxml()
        properties = paragraph.getElementsByTagNameNS(WORD_NS, "pPr")
        if properties:
            alignments = properties[0].getElementsByTagNameNS(WORD_NS, "jc")
            if alignments:
                alignments[0].setAttribute("w:val", "left")
            else:
                alignment = document.createElement("w:jc")
                alignment.setAttribute("w:val", "left")
                properties[0].appendChild(alignment)
        normalize_text_nodes(paragraph)
        new = paragraph.toxml()
        if old != new:
            assert document_xml.count(old) == 1, f"duplicate paragraph XML for {para_id}"
            document_xml = document_xml.replace(old, new, 1)
            changed.add(para_id)
    document.unlink()
    if not changed:
        source.close()
        return source_bytes
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as target:
        for info in source.infolist():
            data = (
                document_xml.encode("utf-8")
                if info.filename == "word/document.xml"
                else source.read(info.filename)
            )
            target.writestr(info, data)
    source.close()
    return output.getvalue()


def build_evidence(normalized: bytes, source_sha256: str) -> dict:
    inventory = []
    slots = []
    with ZipFile(BytesIO(normalized)) as zf:
        for info in zf.infolist():
            data = zf.read(info.filename)
            inventory.append({
                "part": info.filename,
                "size": len(data),
                "sha256": sha256(data),
                "mode": "bounded text/alignment patch"
                if info.filename == "word/document.xml"
                else "preserve-only",
            })
        doc_xml = zf.read("word/document.xml")
    document = minidom.parseString(doc_xml)
    for i, paragraph in enumerate(document.getElementsByTagNameNS(WORD_NS, "p")):
        para_id = (
            paragraph.getAttributeNS(W14_NS, "paraId")
            or paragraph.getAttribute("w14:paraId")
        )
        text = "".join(
            node_text(n) for n in paragraph.getElementsByTagNameNS(WORD_NS, "t")
        )
        for token in TOKEN.findall(text):
            slots.append({
                "part": "word/document.xml",
                "paragraph": i,
                "paraId": para_id,
                "token": token,
            })
    document.unlink()
    # changed_paragraphs: those in NORMALIZE_PARAGRAPH_IDS that still exist
    existing_ids = set()
    with ZipFile(BytesIO(normalized)) as zf:
        doc = minidom.parseString(zf.read("word/document.xml"))
        for p in doc.getElementsByTagNameNS(WORD_NS, "p"):
            pid = p.getAttributeNS(W14_NS, "paraId") or p.getAttribute("w14:paraId")
            if pid in NORMALIZE_PARAGRAPH_IDS:
                existing_ids.add(pid)
        doc.unlink()
    return {
        "source": f"research/notice_template/{TEMPLATE_NAME}",
        "source_original_sha256": source_sha256,
        "canonical_sha256": sha256(normalized),
        "inventory": inventory,
        "slots": slots,
        "changed_paragraphs": sorted(existing_ids),
    }


def main():
    if not RESEARCH.is_file():
        print(f"ERROR: source not found: {RESEARCH}", file=sys.stderr)
        sys.exit(1)

    source_bytes = RESEARCH.read_bytes()
    source_sha = sha256(source_bytes)

    normalized = normalize_package(source_bytes)
    canonical_sha = sha256(normalized)

    # Write normalized copy back to research (source of truth stays normalized)
    RESEARCH.write_bytes(normalized)

    # Write copy to src/template/ for PyInstaller packaging
    PACKAGED.parent.mkdir(parents=True, exist_ok=True)
    PACKAGED.write_bytes(normalized)

    # Rebuild evidence with current hashes and slots
    evidence = build_evidence(normalized, source_sha)
    tmp = EVIDENCE.with_suffix(".tmp.json")
    tmp.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(EVIDENCE)

    print(f"SYNC_OK: {TEMPLATE_NAME}")
    print(f"  source sha256  : {source_sha}")
    print(f"  canonical sha256: {canonical_sha}")
    print(f"  slots          : {len(evidence['slots'])}")
    print(f"  evidence       : {EVIDENCE}")
    print(f"  packaged       : {PACKAGED}")


if __name__ == "__main__":
    main()
