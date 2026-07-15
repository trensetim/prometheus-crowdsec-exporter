from dataclasses import dataclass
from datetime import datetime
from typing import Any

from models._base import (
    boolField,
    datetimeField,
    intField,
    requiredFieldsPresent,
    strField,
)

@dataclass(frozen=True)
class Decision:
    decisionType: str
    origin: str
    scenario: str
    scope: str
    value: str
    decisionId: int
    uuid: str
    duration: datetime | None
    until: datetime | None
    simulated: bool

    @classmethod
    def parse(cls, raw: dict[str, Any]) -> "Decision | None":
        if not isinstance(raw, dict):
            raise ValueError("Decision is not a dict")

        missing = requiredFieldsPresent(raw, ["type", "origin", "scenario", "scope"])
        if missing:
            raise ValueError(f"Decision is missing required fields: {missing}")

        return cls(
            decisionType = strField(raw, "type"),
            origin = strField(raw, "origin"),
            scenario = strField(raw, "scenario"),
            scope = strField(raw, "scope"),
            value = strField(raw, "value", fallback=""),
            decisionId = intField(raw, "id"),
            uuid = strField(raw, "uuid", fallback=""),
            duration = strField(raw, "duration", fallback=""),
            until = datetimeField(raw, "until"),
            simulated = boolField(raw, "simulated"),
        )

    def metricLabels(self) -> dict[str, str]:
        return {
            "decisionType": self.decisionType,
            "origin": self.origin,
            "scenario": self.scenario,
            "scope": self.scope,
        }

    def metricDetails(self) -> dict[str, str]:
        return {
            "decisionType": self.decisionType,
            "origin": self.origin,
            "scenario": self.scenario,
            "scope": self.scope,
            "val": self.value,
            "decisionId": str(self.decisionId),
            "uuid": self.uuid,
            "duration": self.duration,
            "until": self.until.isoformat() if self.until else "",
            "simulated": str(self.simulated).lower(),
        }

