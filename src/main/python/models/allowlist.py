
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from models._base import (
    boolField,
    datetimeField,
    strField,
)

@dataclass(frozen = True)
class AllowlistItem:
    value: str
    description: str
    createdAt: datetime | None
    expiration: datetime | None

    @classmethod
    def parse(cls, raw: dict[str, Any]) -> "AllowlistItem": # pylint: disable=missing-function-docstring
        if not isinstance(raw, dict):
            raise ValueError("AllowlistItem is not a dict")

        if not raw.get("value"):
            raise ValueError("AllowlistItem is missing value")

        return cls(
            value = strField(raw, "value"),
            description = strField(raw, "description", ""),
            createdAt = datetimeField(raw, "created_at"),
            expiration = datetimeField(raw, "expiration"),
        )

    def isExpiringWithin(self, seconds: float) -> bool:
        if self.expiration is None:
            return False
        now = datetime.now(tz = timezone.utc)
        remaining = (self.expiration - now).total_seconds()
        return 0 < remaining <= seconds

    @property
    def isExpired(self) -> bool:
        if self.expiration is None:
            return False
        return datetime.now(tz=timezone.utc) > self.expiration


@dataclass(frozen = True)
class Allowlist:
    name: str
    allowlistId: str
    description: str
    items: tuple[AllowlistItem, ...]
    createdAt: datetime | None
    updatedAt: datetime | None
    consoleManaged: bool

    @classmethod
    def parse(cls, raw: dict[str, Any]) -> "Allowlist | None": # pylint: disable=missing-function-docstring
        if not isinstance(raw, dict):
            raise ValueError("Allowlist is not a dict")

        if not raw.get("name"):
            raise ValueError("Allowlist is missing name")

        rawItems = raw.get("items") or []
        items = tuple(
            item for rd in rawItems
            if (item := AllowlistItem.parse(rd)) is not None
        )

        return cls(
            name = strField(raw, "name"),
            allowlistId = strField(raw, "allowlist_id"),
            description = strField(raw, "description"),
            items = items,
            createdAt = datetimeField(raw, "created_at"),
            updatedAt = datetimeField(raw, "updated_at"),
            consoleManaged = boolField(raw, "console_managed")
        )

    def metricLabels(self) -> dict[str, str]:
        return {
            "name": self.name,
            "allowlistId": self.allowlistId,
            "consoleManaged": str(self.consoleManaged).lower(),
            "description": self.description,
            "createdAt": self.createdAt.isoformat() if self.createdAt else "",
            "updatedAt": self.updatedAt.isoformat() if self.updatedAt else "",
        }

    def metricItems(self) -> list[dict[str, str]]:
        return [
            {
                "allowlistId":  self.allowlistId,
                "name":         self.name,
                "value":        item.value,
                "description":  item.description,
                "expiration":   item.expiration.isoformat() if item.expiration else "",
                "isExpired":    str(item.isExpired).lower(),
            }
            for item in self.items
        ]

    def countExpiringWithin(self, seconds: float) -> int:
        return sum(1 for item in self.items if item.isExpiringWithin(seconds))

    def countActive(self) -> int:
        return sum(1 for item in self.items if not item.isExpired)
