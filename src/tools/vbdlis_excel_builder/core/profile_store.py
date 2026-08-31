from __future__ import annotations

import json
from pathlib import Path

from tools.vbdlis_excel_builder.models import MappingProfile
from tools.vbdlis_excel_builder.utils.paths import app_data_dir


class ProfileStore:
    def __init__(self, config_dir: str | Path | None = None):
        self.config_dir = Path(config_dir) if config_dir else app_data_dir()
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.profiles_path = self.config_dir / "profiles.json"
        self.settings_path = self.config_dir / "app_settings.json"

    def load_all(self) -> dict[str, MappingProfile]:
        if not self.profiles_path.exists():
            return {"Mặc định": MappingProfile()}
        try:
            payload = json.loads(self.profiles_path.read_text(encoding="utf-8"))
            return {name: MappingProfile.from_dict(data) for name, data in payload.items()}
        except (json.JSONDecodeError, TypeError, ValueError):
            return {"Mặc định": MappingProfile()}

    def save_all(self, profiles: dict[str, MappingProfile]) -> None:
        payload = {name: profile.to_dict() for name, profile in profiles.items()}
        self.profiles_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_last_profile(self) -> str:
        if not self.settings_path.exists():
            return "Mặc định"
        try:
            return json.loads(self.settings_path.read_text(encoding="utf-8")).get("last_profile", "Mặc định")
        except (json.JSONDecodeError, OSError):
            return "Mặc định"

    def save_last_profile(self, name: str) -> None:
        self.settings_path.write_text(
            json.dumps({"last_profile": name}, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @staticmethod
    def export_profile(profile: MappingProfile, path: str | Path) -> None:
        Path(path).write_text(json.dumps(profile.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def import_profile(path: str | Path) -> MappingProfile:
        return MappingProfile.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
