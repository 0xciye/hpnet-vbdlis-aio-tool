"""Writable per-tool settings; never depend on the launcher's working directory."""
import json
import os
import sys
from pathlib import Path


def tool_data_dir(tool_name):
    directory = Path(os.getenv("APPDATA", str(Path.home()))) / "HPNET & VBDLIS Tools" / tool_name
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def tool_settings_path(tool_name, filename, module_root, expected_keys):
    target = tool_data_dir(tool_name) / filename
    if target.exists():
        return target
    # Only copy recognized legacy settings. Never remove or overwrite originals.
    candidates = [Path(module_root) / filename]
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / filename)
    candidates.append(Path.cwd() / filename)
    for source in dict.fromkeys(candidates):
        if not source.is_file() or source.resolve() == target.resolve():
            continue
        try:
            raw = source.read_bytes()
            payload = json.loads(raw.decode("utf-8-sig"))
            if not isinstance(payload, dict) or not set(expected_keys).issubset(payload):
                continue
        except (OSError, UnicodeError, ValueError):
            continue
        try:
            with target.open("xb") as handle:
                handle.write(raw)
        except FileExistsError:
            pass
        break
    return target
