
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from models._base import (
    boolField,
    datetimeField,
    intField,
    strField,
)
from models.decision import Decision
from logger import getLogger

log = getLogger(__name__)

@dataclass(frozen = True)
class AlertSource:
    scope: str
    value: str
    ip: str
    range: str
    asNumber: str
    asName: str
    country: str
    latitude: float
    longitude: float

    @classmethod
    def mapClassFromApiDict(cls, raw: dict[str, Any]) -> "AlertSource":
        if not isinstance(raw, dict):
            return cls(
                scope = "",
                value = "",
                ip = "",
                range = "",
                asNumber = "",
                asName = "",
                country = "",
                latitude = 0.0,
                longitude = 0.0
            )

        return cls(
            scope = strField(raw, "scope", ""),
            value = strField(raw, "value", ""),
            ip = strField(raw, "ip", ""),
            range = strField(raw, "range", ""),
            asNumber= strField(raw, "as_number", ""),
            asName = strField(raw, "as_name", ""),
            country = strField(raw, "cn", ""),
            latitude = float(raw.get("latitude") or 0.0),
            longitude = float(raw.get("longitude") or 0.0),
        )


@dataclass(frozen=True)
class AlertEvent:
    timestamp: int
    meta: dict

    @classmethod
    def mapClassFromApiDict(cls, raw: dict[str, Any]) -> "AlertEvent | None":
        if not isinstance(raw, dict):
            return None

        return cls(
            timestamp = intField(raw, "timestamp"),
            meta = _parseMeta(raw.get("meta"))
        )


@dataclass(frozen=True)
class Alert:
    scenario: str
    simulated: bool
    remediation: bool
    id: int
    uuid: str
    machineId: str
    createdAt: datetime | None
    scenarioHash: str
    scenarioVersion: str
    message: str
    eventsCount: int
    startAt: datetime | None
    stopAt: datetime | None
    capacity: int
    leakspeed: str
    events: tuple[AlertEvent, ...]
    decisions: tuple[Decision, ...]
    source: AlertSource | None
    meta: dict
    labels: tuple[str, ...]
    kind: str

    @classmethod
    def mapClassFromApiDict(cls, raw: dict[str, Any], index: int = 0) -> "Alert | None":
        if not isinstance(raw, dict):
            log.warning(
                "alertParseError",
                reason = "notADict",
                got = type(raw).__name__,
                index = index
            )
            return None


        rawEvents = raw.get("events") or []
        events = tuple(
            item for re in rawEvents
            if (item := AlertEvent.mapClassFromApiDict(re)) is not None
        )

        rawDecisions = raw.get("decisions") or []
        decisions = tuple(
            item for rd in rawDecisions
            if (item := Decision.mapClassFromApiDict(rd)) is not None
        )

        return cls(
            id = intField(raw, "id"),
            uuid = strField(raw, "uuid", ""),
            machineId = strField(raw, "machine_id", ""),
            createdAt = datetimeField(raw, "created_at"),
            scenario = strField(raw, "scenario"),
            scenarioHash = strField(raw, "scenario_hash", ""),
            scenarioVersion = strField(raw, "scenario_version", ""),
            message = strField(raw, "message", ""),
            eventsCount = intField(raw, "events_count"),
            startAt = datetimeField(raw, "start_at"),
            stopAt = datetimeField(raw, "stop_at"),
            capacity = intField(raw, "capacity"),
            leakspeed = strField(raw, "leakspeed"),
            simulated = boolField(raw, "simulated"),
            events = events,
            remediation = boolField(raw, "remediation"),
            decisions = decisions,
            source = AlertSource.mapClassFromApiDict(raw.get("source")),
            meta = _parseMeta(raw.get("meta")),
            labels = tuple(str(l) for l in (raw.get("labels") or []) if l),
            kind = strField(raw, "kind"),
        )

    def metricLabels(self) -> dict[str, str]:
        return {
            "scenario": self.scenario,
            "simulated": str(self.simulated).lower(),
            "remediation": str(self.remediation).lower(),
        }

    def metricDetails(self) -> dict[str, str]:
        return {
            "alertIdentifier": str(self.id),
            "uuid": self.uuid,
            "machineId": self.machineId,
            "createdAt": self.createdAt.isoformat() if self.createdAt else "",
            "startAt": self.startAt.isoformat() if self.startAt else "",
            "stopAt": self.stopAt.isoformat() if self.stopAt else "",
            "scenario": self.scenario,
            "scenarioHash": self.scenarioHash,
            "scenarioVersion": self.scenarioVersion,
            "eventsCount": str(self.eventsCount),
            "simulated": str(self.simulated).lower(),
            "remediation": str(self.remediation).lower(),
            "ip": self.source.ip if self.source else "",
            "subnet": self.source.range if self.source else "",
            "country": self.source.country if self.source else "",
            "asNumber": self.source.asNumber if self.source else "",
            "asName": self.source.asName if self.source else "",
            "latitude": str(self.source.latitude) if self.source else "",
            "longitude": str(self.source.longitude) if self.source else "",
            "decisionType": self.decisions[0].decisionType if self.decisions else "",
            "decisionScope": self.decisions[0].scope if self.decisions else "",
        }

def _parseMeta(rawMeta: Any) -> dict[str, str]:
    if not isinstance(rawMeta, list):
        return {}

    return {
        str(item["key"]): str(item["value"])
        for item in rawMeta
        if isinstance(item, dict) and "key" in item and "value" in item
    }
