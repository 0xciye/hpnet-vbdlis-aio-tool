"""Bounded, reproducible OOXML patch; run with the bundled document runtime."""
from pathlib import Path
from zipfile import ZipFile
from xml.dom import minidom
import argparse
import hashlib
import json
import re

NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
# The six paragraphs identified in the user's spacing screenshot. No other alignment changes.
PARAGRAPHS = {"58A73022", "16BFFFF9", "657FD163", "03B7582C", "70AE63C5", "5D54EF36"}


def prepare(source, target, evidence):
    raw = source.read_bytes()
    inventory = []; slots = []; patched = set()
    target.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(source) as original, ZipFile(target, "x") as final:
        for part in original.infolist():
            data = original.read(part)
            inventory.append({"part":part.filename,"size":len(data),"sha256":hashlib.sha256(data).hexdigest(),
                              "mode":"bounded text/alignment patch" if part.filename=="word/document.xml" else "preserve-only"})
            if part.filename == "word/document.xml":
                doc = minidom.parseString(data)
                for index,p in enumerate(doc.getElementsByTagNameNS(NS,"p")):
                    joined = "".join(t.firstChild.data if t.firstChild else "" for t in p.getElementsByTagNameNS(NS,"t"))
                    slots.extend({"part":part.filename,"paragraph":index,"paraId":p.getAttribute("w14:paraId"),"token":token}
                                 for token in re.findall(r"\{\{([A-Z_0-9]+)\}\}",joined))
                    if p.getAttribute("w14:paraId") not in PARAGRAPHS: continue
                    patched.add(p.getAttribute("w14:paraId"))
                    p.getElementsByTagNameNS(NS,"jc")[0].setAttribute("w:val","left")
                    for text in p.getElementsByTagNameNS(NS,"t"):
                        if text.firstChild:
                            text.firstChild.data = re.sub(r" {2,}"," ",text.firstChild.data).replace("chồng :", "chồng:")
                assert patched == PARAGRAPHS
                data = doc.toxml(encoding="utf-8"); doc.unlink()
            final.writestr(part,data)
    assert source.read_bytes() == raw
    evidence.write_text(json.dumps({"source":str(source.resolve()),"source_sha256":hashlib.sha256(raw).hexdigest(),
                                    "target_sha256":hashlib.sha256(target.read_bytes()).hexdigest(),"inventory":inventory,"slots":slots,
                                    "changed_paragraphs":sorted(patched)},ensure_ascii=False,indent=2),encoding="utf-8")


if __name__ == "__main__":
    p=argparse.ArgumentParser(); p.add_argument("source",type=Path); p.add_argument("target",type=Path); p.add_argument("evidence",type=Path)
    args=p.parse_args(); prepare(args.source,args.target,args.evidence)
