from dataclasses import dataclass
from datetime import datetime
from typing import Any

from src.models._base import (
    boolField,
    datetimeField,
    intField,
    requiredFieldsPresent,
    strField,
)
from src.logger import getLogger

log = getLogger(__name__)

# Fields that must be present for a decision to be processable
_REQUIRED = ("type", "origin", "scenario", "scope")

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
    def mapClassFromApiDict(cls, raw: dict[str, Any], index: int = 0) -> "Decision | None":
        if not isinstance(raw, dict):
            log.warning(
                "decisionParseError",
                reason = "notADict",
                got = type(raw).__name__,
                index = index
            )
            return None

        missing = requiredFieldsPresent(raw, _REQUIRED)
        if missing:
            log.warning(
                "decisionParseError",
                reason = "missingRequiredFields",
                missing = missing,
                index = index,
                raw_keys = list(raw.keys())
            )
            return None

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

