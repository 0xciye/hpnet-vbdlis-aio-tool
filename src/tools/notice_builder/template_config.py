from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path

from .paths import resource


@dataclass(frozen=True)
class TemplateConfig:
    id: str
    name: str
    template_file: str
    is_default: bool = False
    static_values: dict[str, str] = field(default_factory=dict)
    required_fields: tuple[str, ...] = ()
    user_fields: tuple[str, ...] = ()
    optional_fields: tuple[str, ...] = ()
    placeholder_mapping: dict[str, str] = field(default_factory=dict)
    validation_rules: dict[str, object] = field(default_factory=dict)
    document_rules: dict[str, object] = field(default_factory=dict)

    @property
    def path(self) -> Path:
        return resource("template") / self.template_file


def template_configs() -> tuple[TemplateConfig, ...]:
    payload = json.loads(resource("config/template_configs.json").read_text(encoding="utf-8"))
    return tuple(TemplateConfig(
        **{**item,
           "required_fields": tuple(item.get("required_fields", ())),
           "user_fields": tuple(item.get("user_fields", ())),
           "optional_fields": tuple(item.get("optional_fields", ()))})
        for item in payload["templates"])


def default_template_config() -> TemplateConfig:
    return next(config for config in template_configs() if config.is_default)


def template_config_for_path(path: str | Path) -> TemplateConfig:
    candidate = Path(path)
    for config in template_configs():
        if candidate.name.casefold() == config.template_file.casefold():
            return config
    # Custom templates retain the original Mẫu 22 contract.
    from .core.fields import REQUIRED_TOKENS, REQUIRED_COMMON, OPTIONAL_COMMON
    return TemplateConfig(
        "CUSTOM", "Mẫu tùy chọn", candidate.name,
        required_fields=tuple(REQUIRED_TOKENS),
        user_fields=tuple(REQUIRED_COMMON),
        optional_fields=tuple(OPTIONAL_COMMON),
    )
