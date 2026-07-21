from typing import Type

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from models._base import (
    boolField,
    datetimeField,
    intField,
    strField,
)
from models.decision import Decision

# pylint: disable=too-many-instance-attributes
@dataclass(frozen = True)
class AlertSource:
    scope: str
    value: str
    ip: str
    range: str
    as_number: str
    as_name: str
    country: str
    latitude: float
    longitude: float

    @classmethod
    def parse(cls, raw: dict[str, Any]) -> "AlertSource":
        if not isinstance(raw, dict):
            return cls(
                scope = "",
                value = "",
                ip = "",
                range = "",
                as_number = "",
                as_name = "",
                country = "",
                latitude = 0.0,
                longitude = 0.0
            )

        return cls(
            scope = strField(raw, "scope", ""),
            value = strField(raw, "value", ""),
            ip = strField(raw, "ip", ""),
            range = strField(raw, "range", ""),
            as_number= strField(raw, "as_number", ""),
            as_name = strField(raw, "as_name", ""),
            country = strField(raw, "cn", ""),
            latitude = float(raw.get("latitude") or 0.0),
            longitude = float(raw.get("longitude") or 0.0),
        )


@dataclass(frozen=True)
class AlertEvent:
    timestamp: int
    meta: dict

    @classmethod
    def parse(cls, raw: dict[str, Any]) -> "AlertEvent | None":
        if not isinstance(raw, dict):
            return None

        return cls(
            timestamp = intField(raw, "timestamp"),
            meta = _parse_meta(raw.get("meta"))
        )

# pylint: disable=too-many-instance-attributes
@dataclass(frozen=True)
class Alert:
    scenario: str
    simulated: bool
    remediation: bool
    id: int
    uuid: str
    machine_id: str
    created_at: datetime
    scenario_hash: str
    scenario_version: str
    message: str
    events_count: int
    start_at: datetime
    stop_at: datetime
    capacity: int
    leakspeed: str
    events: tuple[AlertEvent, ...]
    decisions: tuple[Decision, ...]
    source: AlertSource
    meta: dict
    labels: tuple[str, ...]
    kind: str

    @classmethod
    def parse(cls: Type["Alert"], raw: dict[str, Any]) -> "Alert | None":
        if not isinstance(raw, dict):
            raise ValueError("Alert is not a dict")

        events = raw.get("events") or []
        events = tuple(AlertEvent.parse(re) for re in events)

        decisions = raw.get("decisions") or []
        decisions = tuple(
            item for rd in decisions
            if (item := Decision.parse(rd)) is not None
        )

        return cls(
            id = intField(raw, "id"),
            uuid = strField(raw, "uuid", ""),
            machine_id = strField(raw, "machine_id", ""),
            created_at = datetimeField(raw, "created_at") or datetime.fromtimestamp(0, tz=timezone.utc),
            scenario = strField(raw, "scenario"),
            scenario_hash = strField(raw, "scenario_hash", ""),
            scenario_version = strField(raw, "scenario_version", ""),
            message = strField(raw, "message", ""),
            events_count = intField(raw, "events_count"),
            start_at = datetimeField(raw, "start_at") or datetime.fromtimestamp(0, tz=timezone.utc),
            stop_at = datetimeField(raw, "stop_at") or datetime.fromtimestamp(0, tz=timezone.utc),
            capacity = intField(raw, "capacity"),
            leakspeed = strField(raw, "leakspeed"),
            simulated = boolField(raw, "simulated"),
            events = events,
            remediation = boolField(raw, "remediation"),
            decisions = decisions,
            source = AlertSource.parse(raw.get("source")),
            meta = _parse_meta(raw.get("meta")),
            labels = tuple(str(l) for l in (raw.get("labels") or []) if l),
            kind = strField(raw, "kind"),
        )

    def __eq__(self, value):
        if not isinstance(value, Alert):
            return False
        return self.uuid == value.uuid

    def __hash__(self):
        return hash(self.uuid)

    @staticmethod
    def metric_labels() -> list[str]:
        return [
            "id",
            "uuid",
            "machine_id",
            "scenario",
            "scenario_hash",
            "scenario_version",
            "simulated",
            "remediation",
            "ip",
            "subnet",
            "country",
            "as_number",
            "as_name",
            "latitude",
            "longitude",
            "decision_type",
            "decision_scope",
        ]

    def metric_label_values(self) -> list[str]:
        return [
            str(self.id),
            self.uuid,
            self.machine_id,
            self.scenario,
            self.scenario_hash,
            self.scenario_version,
            str(self.simulated).lower(),
            str(self.remediation).lower(),
            self.source.ip,
            self.source.range,
            self.source.country,
            self.source.as_number,
            self.source.as_name,
            str(self.source.latitude),
            str(self.source.longitude),
            self.decisions[0].type if self.decisions else "",
            self.decisions[0].scope if self.decisions else "",
        ]

    @staticmethod
    def created_metric_labels() -> list[str]:
        return ["id", "uuid"]
    def created_metric_label_values(self) -> list[str]:
        return [str(self.id), self.uuid]
    @staticmethod
    def start_metric_labels() -> list[str]:
        return Alert.created_metric_labels()
    def start_metric_label_values(self) -> list[str]:
        return self.created_metric_label_values()
    @staticmethod
    def stop_metric_labels() -> list[str]:
        return Alert.created_metric_labels()
    def stop_metric_label_values(self) -> list[str]:
        return self.created_metric_label_values()
    @staticmethod
    def events_count_metric_labels() -> list[str]:
        return Alert.created_metric_labels()
    def events_count_metric_label_values(self) -> list[str]:
        return self.created_metric_label_values()

    @staticmethod
    def total_metric_labels() -> list[str]:
        return [
            "scenario",
            "scenario_hash",
            "scenario_version",
            "simulated",
            "remediation",
            "ip",
            "subnet",
            "country",
            "as_number",
            "as_name",
            "latitude",
            "longitude",
            "decision_type",
            "decision_scope",
        ]
    def total_metric_label_values(self) -> list[str]:
        return [
            self.scenario,
            self.scenario_hash,
            self.scenario_version,
            str(self.simulated).lower(),
            str(self.remediation).lower(),
            self.source.ip,
            self.source.range,
            self.source.country,
            self.source.as_number,
            self.source.as_name,
            str(self.source.latitude),
            str(self.source.longitude),
            self.decisions[0].type if self.decisions else "",
            self.decisions[0].scope if self.decisions else "",
        ]

def _parse_meta(raw: Any) -> dict[str, str]:
    if not isinstance(raw, list):
        return {}

    return {
        str(item["key"]): str(item["value"])
        for item in raw
        if isinstance(item, dict) and "key" in item and "value" in item
    }
