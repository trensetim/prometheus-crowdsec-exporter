from typing import Any, Type

from dataclasses import dataclass
from datetime import datetime, timezone

from models._parse_utils import (
    parse_bool_field,
    parse_datetime_field,
    parse_string_field
)

@dataclass(frozen = True)
class AllowlistItem:
    value: str
    description: str
    created_at: datetime
    expiration: datetime | None

    @classmethod
    def parse(cls: Type["AllowlistItem"], raw: dict[str, Any]) -> "AllowlistItem": # pylint: disable=missing-function-docstring
        if not isinstance(raw, dict):
            raise ValueError("AllowlistItem is not a dict")

        if not raw.get("value"):
            raise ValueError("AllowlistItem is missing value")

        created_at = parse_datetime_field(raw, "created_at") or datetime.fromtimestamp(0, tz=timezone.utc)
        expiration = parse_datetime_field(raw, "expiration")

        return cls(
            value = parse_string_field(raw, "value"),
            description = parse_string_field(raw, "description", ""),
            created_at = created_at,
            expiration = expiration,
        )

    @staticmethod
    def metric_labels() -> list[str]:
        return [
            "allowlist_name",
            "value",
            "description",
            "created_at",
            "expiration"
        ]

    def metric_label_values(self, allowlist_name: str) -> list[str]:
        return [
            allowlist_name,
            self.value,
            self.description,
            self.created_at.isoformat(),
            self.expiration.isoformat() if self.expiration is not None else ""
        ]

    @staticmethod
    def created_metric_labels() -> list[str]:
        return ["allowlist_name", "value"]
    def created_metric_label_values(self, allowlist_name: str) -> list[str]:
        return [allowlist_name, self.value]
    @staticmethod
    def expiration_metric_labels() -> list[str]:
        return AllowlistItem.created_metric_labels()
    def expiration_metric_label_values(self, allowlist_name: str) -> list[str]:
        return self.created_metric_label_values(allowlist_name)

@dataclass(frozen = True)
class Allowlist:
    name: str
    description: str
    items: list[AllowlistItem]
    created_at: datetime
    updated_at: datetime
    console_managed: bool

    @classmethod
    def parse(cls: Type["Allowlist"], raw: dict[str, Any]) -> "Allowlist": # pylint: disable=missing-function-docstring
        if not isinstance(raw, dict):
            raise ValueError("Allowlist is not a dict")

        if not raw.get("name"):
            raise ValueError("Allowlist is missing name")

        raw_items = raw.get("items") or []
        items = [AllowlistItem.parse(rd) for rd in raw_items]

        return cls(
            name = parse_string_field(raw, "name"),
            description = parse_string_field(raw, "description"),
            items = items,
            created_at = parse_datetime_field(raw, "created_at") or datetime.fromtimestamp(0, tz=timezone.utc),
            updated_at = parse_datetime_field(raw, "updated_at") or datetime.fromtimestamp(0, tz=timezone.utc),
            console_managed = parse_bool_field(raw, "console_managed")
        )

    @staticmethod
    def metric_labels() -> list[str]:
        return [
            "allowlist_name",
            "console_managed",
            "description",
            "created_at",
            "updated_at",
        ]

    def metric_label_values(self) -> list[str]:
        return [
            self.name,
            str(self.console_managed).lower(),
            self.description,
            self.created_at.isoformat(),
            self.updated_at.isoformat(),
        ]

    @staticmethod
    def created_metric_labels() -> list[str]:
        return ["allowlist_name"]

    def created_metric_label_values(self) -> list[str]:
        return [self.name]

    @staticmethod
    def updated_metric_labels() -> list[str]:
        return Allowlist.created_metric_labels()
    def updated_metric_label_values(self) -> list[str]:
        return self.created_metric_label_values()

    @staticmethod
    def console_managed_metric_labels() -> list[str]:
        return ["console_managed"]
    def console_managed_metric_label_values(self) -> list[str]:
        return [str(self.console_managed).lower()]

