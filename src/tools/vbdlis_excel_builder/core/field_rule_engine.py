from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from tools.vbdlis_excel_builder.models import FieldRule, FieldSchema, FieldSource, Household, MappingProfile, Parcel, Person
from tools.vbdlis_excel_builder.utils.text import infer_gender_from_cccd, is_blank, safe_template_replace


@dataclass(slots=True)
class RowContext:
    output_stt: int
    household: Household
    person: Person
    parcel: Parcel
    profile: MappingProfile
    location: str


class FieldRuleEngine:
    def __init__(self, schemas: list[FieldSchema], profile: MappingProfile):
        self.schemas = schemas
        self.profile = profile
        self.transformers: dict[str, Callable[[RowContext], Any]] = {
            "output_stt": lambda c: c.output_stt,
            "commune_code": lambda c: c.profile.commune_code,
            "dossier_name": self._dossier_name,
            "dossier_or_gcn_issue_number": self._dossier_or_gcn_issue_number,
            "person_name": lambda c: c.person.name,
            "cccd": lambda c: c.person.cccd,
            "birth_date": lambda c: c.person.birth_date,
            "gender": self._gender,
            "address": lambda c: c.profile.address,
            "entity_type": lambda c: c.profile.entity_type,
            "role": lambda c: c.profile.owner_value if c.person.is_head else c.profile.member_value,
            "sheet_number": lambda c: c.parcel.sheet_number,
            "parcel_number": lambda c: c.parcel.parcel_number,
            "land_location": lambda c: c.location,
            "area": lambda c: c.parcel.area,
            "area_copy": lambda c: c.parcel.area,
            "document_files": self._document_files,
            "document_type": lambda c: c.profile.document_type,
            "identity_copy": lambda c: c.person.cccd,
            "gcn_issue_number": lambda c: c.parcel.certificate.values.get("gcn_issue_number", ""),
            "gcn_issue_date": lambda c: c.parcel.certificate.values.get("gcn_issue_date", ""),
            "gcn_registry_number": lambda c: c.parcel.certificate.values.get("gcn_registry_number", ""),
            "gcn_type": lambda c: c.parcel.certificate.values.get("gcn_type", ""),
            "gcn_authority": lambda c: c.parcel.certificate.values.get("gcn_authority", ""),
        }

    def _template_values(self, context: RowContext) -> dict[str, Any]:
        return {
            "PREFIX": context.profile.prefix,
            "MA_XA": context.profile.commune_code,
            "SO_TO": context.parcel.sheet_number,
            "SO_THUA": context.parcel.parcel_number,
            "HO_TEN": context.person.name,
            "CCCD": context.person.cccd,
            "DIA_CHI": context.profile.address,
            "XU_DONG": context.location,
            "STT": context.output_stt,
        }

    def _dossier_name(self, context: RowContext) -> str:
        return safe_template_replace(context.profile.item_2_template, self._template_values(context))

    def _document_files(self, context: RowContext) -> str:
        return safe_template_replace(context.profile.item_49_template, self._template_values(context))

    def _dossier_or_gcn_issue_number(self, context: RowContext) -> str:
        issue_number = context.parcel.certificate.values.get("gcn_issue_number", "")
        return str(issue_number).strip() if not is_blank(issue_number) else self._dossier_name(context)

    @staticmethod
    def _gender(context: RowContext) -> str:
        return infer_gender_from_cccd(context.person.cccd)

    @staticmethod
    def _raw_source(context: RowContext, source: str) -> Any:
        if source.startswith("gcn_"):
            return context.parcel.certificate.values.get(source, "")
        canonical = {
            "person_name": context.person.name,
            "cccd": context.person.cccd,
            "birth_date": context.person.birth_date,
            "gender": infer_gender_from_cccd(context.person.cccd),
            "sheet_number": context.parcel.sheet_number,
            "parcel_number": context.parcel.parcel_number,
            "area": context.parcel.area,
            "land_location": context.location,
        }
        if source in canonical:
            return canonical[source]
        if source in context.person.raw:
            return context.person.raw[source]
        return context.parcel.raw.get(source, "")

    def _rule_for(self, schema: FieldSchema) -> FieldRule:
        override = self.profile.field_rules.get(schema.field_id)
        if override:
            payload = dict(override)
            payload.setdefault("field_id", schema.field_id)
            payload.setdefault("required", schema.required)
            return FieldRule.from_dict(payload)
        return FieldRule(
            field_id=schema.field_id,
            mode=FieldSource(schema.mode),
            source=schema.source,
            default=schema.default,
            transformer=schema.transformer,
            fallback=schema.fallback,
            required=schema.required,
            condition=schema.condition,
        )

    def evaluate(self, schema: FieldSchema, context: RowContext) -> Any:
        if schema.transformer == "gender":
            # A legacy field override or source fallback must not fill other markers.
            return self._gender(context)
        rule = self._rule_for(schema)
        if rule.mode == FieldSource.BLANK:
            return ""
        if rule.mode in {FieldSource.FIXED, FieldSource.KEEP_TEMPLATE}:
            return rule.default
        if rule.mode == FieldSource.SOURCE_COLUMN:
            value = self._raw_source(context, rule.source)
            if is_blank(value) and rule.fallback:
                return rule.fallback
            return value
        if rule.mode == FieldSource.COMPUTED:
            transformer = self.transformers.get(rule.transformer)
            if transformer is None:
                raise ValueError(f"Transformer không tồn tại: {rule.transformer}")
            return transformer(context)
        if rule.mode == FieldSource.CONDITIONAL:
            if rule.condition == "has_gcn" and not context.parcel.certificate.has_data:
                return rule.fallback or ""
            if rule.condition == "has_cccd" and not context.person.cccd:
                return rule.fallback or ""
            value = self._raw_source(context, rule.source)
            return value if not is_blank(value) else (rule.fallback or rule.default or "")
        return ""

    def build_row(self, context: RowContext) -> dict[str, Any]:
        row = {schema.column: self.evaluate(schema, context) for schema in self.schemas}
        row["_meta"] = {
            "household": context.household.household_id,
            "person": context.person.name,
            "parcel": f"{context.parcel.sheet_number}/{context.parcel.parcel_number}",
            "source_row": context.person.source_row or context.parcel.source_row,
            "person_source_row": context.person.source_row,
            "parcel_source_row": context.parcel.source_row,
            "has_gcn": context.parcel.certificate.has_data,
            "fallback_location": not bool(context.parcel.location) and bool(context.location),
        }
        return row
