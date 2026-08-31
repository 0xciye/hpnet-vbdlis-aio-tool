from io import BytesIO
from pathlib import Path
from zipfile import ZipFile, BadZipFile
from xml.dom import minidom
import hashlib
import re
from .models import UserError
from .fields import missing_required, REQUIRED_TOKENS

WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
TOKEN = re.compile(r"\{\{([A-Z_0-9]+)\}\}")
TEXT_PART = re.compile(r"word/(document|header[0-9]+|footer[0-9]+|footnotes|endnotes)\.xml$")


def paragraph_nodes(paragraph):
    result = []
    for node in paragraph.getElementsByTagNameNS(WORD_NS, "t"):
        parent = node.parentNode
        while parent is not None and not (parent.namespaceURI == WORD_NS and parent.localName == "p"):
            parent = parent.parentNode
        if parent is paragraph:
            result.append(node)
    return result


def node_text(node):
    return "".join(child.data for child in node.childNodes if child.nodeType == child.TEXT_NODE)


def replace_span(nodes, start, end, replacement):
    position = 0
    inserted = False
    for node in nodes:
        text = node_text(node); stop = position + len(text)
        if position < end and stop > start:
            left = max(0, start - position); right = min(len(text), end - position)
            new_text = text[:left] + (replacement if not inserted else "") + text[right:]
            inserted = True
            for child in list(node.childNodes):
                node.removeChild(child)
            node.appendChild(node.ownerDocument.createTextNode(new_text))
            node.setAttribute("xml:space", "preserve")
        position = stop


def paragraphs(document):
    return document.getElementsByTagNameNS(WORD_NS, "p")


class WordTemplate:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.raw = self.path.read_bytes()
        self.digest = hashlib.sha256(self.raw).hexdigest()
        try:
            with ZipFile(BytesIO(self.raw)) as zf:
                if "word/document.xml" not in zf.namelist() or zf.testzip():
                    raise UserError("Mẫu Word không phải DOCX hợp lệ.")
                if sum(i.file_size for i in zf.infolist()) > 100 * 1024 * 1024:
                    raise UserError("Mẫu Word quá lớn. Hãy dùng mẫu thông báo gọn hơn 100 MB sau giải nén.")
                self.entries = [(info, zf.read(info)) for info in zf.infolist()]
            self.tokens = set()
            for info, data in self.entries:
                if TEXT_PART.fullmatch(info.filename):
                    if b"<!DOCTYPE" in data or b"<!ENTITY" in data:
                        raise UserError("Mẫu Word chứa khai báo XML không được hỗ trợ.")
                    doc = minidom.parseString(data)
                    for p in paragraphs(doc):
                        self.tokens.update(TOKEN.findall("".join(node_text(n) for n in paragraph_nodes(p))))
                    doc.unlink()
            required = set(REQUIRED_TOKENS)
            if not required <= self.tokens:
                raise UserError("Mẫu thiếu placeholder bắt buộc: " + ", ".join(sorted(required - self.tokens)))
        except (BadZipFile, ValueError) as exc:
            raise UserError("Không đọc được mẫu DOCX. Hãy chọn lại đúng mẫu placeholder.") from exc

    def render(self, values):
        missing = self.tokens.intersection(REQUIRED_TOKENS) - values.keys()
        if missing:
            raise UserError("Chưa có cách điền placeholder: " + ", ".join(sorted(missing)))
        missing_values = missing_required(values)
        if missing_values:
            raise UserError("Cần nhập đủ mục bắt buộc: " + ", ".join(missing_values) + ".")
        for value in values.values():
            if "{{" in str(value) or re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", str(value)):
                raise UserError("Nội dung điền Word có ký tự điều khiển hoặc dấu placeholder không hợp lệ.")
        output = BytesIO()
        with ZipFile(output, "w") as zf:
            for info, data in self.entries:
                if TEXT_PART.fullmatch(info.filename):
                    doc = minidom.parseString(data)
                    changed = False
                    for p in paragraphs(doc):
                        nodes = paragraph_nodes(p)
                        joined = "".join(node_text(n) for n in nodes)
                        if not values.get("XU_DONG"):
                            match = re.search(r"xứ\s+đồng\s*\{\{XU_DONG\}\}\s*,?\s*", joined, re.IGNORECASE)
                            if match:
                                replace_span(nodes, match.start(), match.end(), "")
                                changed = True
                                joined = "".join(node_text(n) for n in nodes)
                        for match in reversed(list(TOKEN.finditer(joined))):
                            replace_span(nodes, match.start(), match.end(), str(values.get(match[1], "")))
                            changed = True
                        if "{{" in "".join(node_text(n) for n in nodes):
                            raise UserError("Mẫu còn placeholder không đúng định dạng. Hãy kiểm tra mẫu Word.")
                    if changed:
                        data = doc.toxml(encoding="utf-8")
                    doc.unlink()
                zf.writestr(info, data)
        payload = output.getvalue()
        self.verify(payload)
        return payload

    @staticmethod
    def verify(payload):
        with ZipFile(BytesIO(payload)) as zf:
            if zf.testzip() is not None or "word/document.xml" not in zf.namelist():
                raise UserError("File Word vừa tạo không vượt qua kiểm tra tính toàn vẹn.")
            for part in zf.namelist():
                if TEXT_PART.fullmatch(part):
                    doc = minidom.parseString(zf.read(part))
                    try:
                        if any("{{" in "".join(node_text(n) for n in paragraph_nodes(p)) for p in paragraphs(doc)):
                            raise UserError("File Word vừa tạo vẫn còn placeholder chưa điền.")
                    finally:
                        doc.unlink()
