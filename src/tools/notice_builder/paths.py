from pathlib import Path
import os
import json

DEFAULT_TEMPLATE_NAME = "MAU_22_THONG_BAO_XAC_NHAN_KET_QUA_DANG_KY_DAT_DAI.docx"


def resource(relative):
    return Path(__file__).resolve().parent / relative


def default_template_path():
    return resource("template") / DEFAULT_TEMPLATE_NAME


def default_template_fields():
    from .core.fields import REQUIRED_COMMON, OPTIONAL_COMMON
    values = json.loads(resource("config/legal_defaults.json").read_text(encoding="utf-8"))
    return {**{key:values.get(key, "") for key in REQUIRED_COMMON}, **{key:"" for key in OPTIONAL_COMMON}}


def saved_template_path(settings):
    """Return the saved template path, defaulting to the bundled MAU_22 template."""
    if settings.get("template_kind") == "default":
        return default_template_path()
    path = Path(settings.get("template") or "")
    if path.is_file() and path.suffix.lower() == ".docx":
        return path
    return default_template_path()


def data_dir():
    path = Path(os.getenv("APPDATA", str(Path.home()))) / "HPNET & VBDLIS Tools" / "Tao thong bao"
    path.mkdir(parents=True, exist_ok=True)
    return path
