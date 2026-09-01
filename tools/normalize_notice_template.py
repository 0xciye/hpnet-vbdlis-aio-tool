"""Normalize placeholder spacing with a bounded OOXML-only patch."""
from __future__ import annotations

import argparse
from io import BytesIO
import re
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from xml.dom import minidom

TEMPLATE_NAME = "MAU_22_THONG_BAO_XAC_NHAN_KET_QUA_DANG_KY_DAT_DAI.docx"
WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W14_NS = "http://schemas.microsoft.com/office/word/2010/wordml"
# Placeholder-heavy body lines that Word stretched because they were justified.
PARAGRAPH_IDS = {
    "7C9943F6", "1ED125E3", "58A73022", "16BFFFF9", "657FD163",
    "03B7582C", "70AE63C5", "6D3675DF", "5D54EF36",
}


def normalize_text_nodes(paragraph):
    nodes = paragraph.getElementsByTagNameNS(WORD_NS, "t")
    for node in nodes:
        value = "".join(child.data for child in node.childNodes if child.nodeType == child.TEXT_NODE)
        value = re.sub(r"[ \t]{2,}", " ", value)
        value = re.sub(r"[ \t]+([,;:.])", r"\1", value)
        while node.firstChild: node.removeChild(node.firstChild)
        node.appendChild(node.ownerDocument.createTextNode(value))
    for previous, current in zip(nodes, nodes[1:]):
        previous_text = previous.firstChild.data if previous.firstChild else ""
        current_text = current.firstChild.data if current.firstChild else ""
        if previous_text.endswith(" ") and current_text.startswith(" "):
            current.firstChild.data = current_text.lstrip(" ")
    if nodes:
        last = nodes[-1]
        if last.firstChild: last.firstChild.data = last.firstChild.data.rstrip()


def normalize_package(source_bytes: bytes) -> bytes:
    source = ZipFile(BytesIO(source_bytes))
    document_xml = source.read("word/document.xml").decode("utf-8")
    document = minidom.parseString(document_xml.encode("utf-8"))
    changed = set()
    for paragraph in document.getElementsByTagNameNS(WORD_NS, "p"):
        para_id = paragraph.getAttributeNS(W14_NS, "paraId") or paragraph.getAttribute("w14:paraId")
        if para_id not in PARAGRAPH_IDS: continue
        old = paragraph.toxml()
        properties = paragraph.getElementsByTagNameNS(WORD_NS, "pPr")[0]
        alignments = properties.getElementsByTagNameNS(WORD_NS, "jc")
        if alignments:
            alignments[0].setAttribute("w:val", "left")
        else:
            alignment = document.createElement("w:jc"); alignment.setAttribute("w:val", "left")
            properties.appendChild(alignment)
        normalize_text_nodes(paragraph)
        new = paragraph.toxml()
        assert document_xml.count(old) == 1, para_id
        document_xml = document_xml.replace(old, new, 1)
        changed.add(para_id)
    assert changed == PARAGRAPH_IDS, (changed, PARAGRAPH_IDS)
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as target:
        for info in source.infolist():
            data = document_xml.encode("utf-8") if info.filename == "word/document.xml" else source.read(info.filename)
            target.writestr(info, data)
    source.close()
    return output.getvalue()


def normalize(source_bytes: bytes, destinations: list[Path]):
    result = normalize_package(source_bytes)
    for destination in destinations:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(".normalized.tmp.docx")
        temporary.write_bytes(result)
        temporary.replace(destination)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--source-release", type=Path,
                        help="Use the currently verified release template as the source package.")
    args = parser.parse_args()
    root = args.root.resolve()
    research = root / "research" / "notice_template22" / TEMPLATE_NAME
    packaged = root / "src" / "tools" / "notice_builder" / "template" / TEMPLATE_NAME
    if args.source_release:
        with ZipFile(args.source_release.resolve()) as archive:
            entry = next(name for name in archive.namelist() if name.endswith("/" + TEMPLATE_NAME))
            source_bytes = archive.read(entry)
    else:
        source_bytes = research.read_bytes()
    normalize(source_bytes, [research, packaged])
    print(f"NORMALIZED: {research}")
    print(f"SYNCHRONIZED: {packaged}")


if __name__ == "__main__":
    main()
