from pathlib import Path
import os
import json

DEFAULT_TEMPLATE_NAME = "MAU_22_THONG_BAO_XAC_NHAN_KET_QUA_DANG_KY_DAT_DAI.docx"


def resource(relative):
    return Path(__file__).resolve().parent / relative


def default_template_path():
    from .template_config import default_template_config
    return default_template_config().path


def default_template_fields():
    from .template_config import default_template_config
    values = json.loads(resource("config/legal_defaults.json").read_text(encoding="utf-8"))
    config = default_template_config()
    return {**{key:values.get(key, "") for key in config.user_fields},
            **{key:"" for key in config.optional_fields}}


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
