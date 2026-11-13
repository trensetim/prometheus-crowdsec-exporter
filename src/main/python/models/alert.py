from collections.abc import Iterable
from typing import Type, Any
from dataclasses import dataclass
from datetime import datetime, timezone

from models._parse_utils import (
    parse_bool_field,
    parse_datetime_field,
    parse_int_field,
    parse_string_field,
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
            scope = parse_string_field(raw, "scope", "unknown"),
            value = parse_string_field(raw, "value", "unknown"),
            ip = parse_string_field(raw, "ip", "unknown"),
            range = parse_string_field(raw, "range", "unknown"),
            as_number= parse_string_field(raw, "as_number", "0"),
            as_name = parse_string_field(raw, "as_name", "unknown"),
            country = parse_string_field(raw, "cn", "unknown"),
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
            timestamp = parse_int_field(raw, "timestamp"),
            meta = _parse_meta(raw.get("meta"))
        )

@dataclass(frozen=True)
class AlertIdentityKey:
    """
    Stable identity of an alert, used to deduplicate alerts across polls and pagination batches.

    Combines the LAPI-local incrementing `id` with the globally-unique `uuid`:
    CAPI update alerts carry an empty `uuid`, so `id` keeps them distinct, while
    normal alerts additionally carry a `uuid`. Using both fields (instead of only
    one) keeps the key type-stable and degrades safely if either identifier is
    unreliable (eg. a mock/buggy LAPI emitting duplicate uuids).

    An alert without any identifier has no identity: use the `of`/`parse` factories,
    which return `None` for that case, rather than constructing an (invalid) empty key.
    """
    id: int
    uuid: str

    def __init__(self, id: int, uuid: str) -> None: # pylint: disable=redefined-builtin
        # frozen dataclass: fields must be assigned via object.__setattr__.
        # Forbid the empty, un-deduplicatable instance so invalid keys cannot exist.
        if id == 0 and uuid == "":
            raise ValueError("AlertIdentityKey requires at least one identifier (id or uuid); use AlertIdentityKey.of() to get None instead")
        object.__setattr__(self, "id", id)
        object.__setattr__(self, "uuid", uuid)

    @staticmethod
    def of(alert_id: int, uuid: str) -> "AlertIdentityKey | None":
        """Build a key, or None when neither identifier is present (ie. the alert cannot be deduplicated)."""
        if alert_id == 0 and uuid == "":
            return None
        return AlertIdentityKey(alert_id, uuid)

    @staticmethod
    def parse(raw: dict[str, Any]) -> "AlertIdentityKey | None":
        """Derive the identity key straight from a raw alert dict, without parsing the whole alert."""
        return AlertIdentityKey.of(
            parse_int_field(raw, "id"),
            parse_string_field(raw, "uuid", ""),
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

        created_at = parse_datetime_field(raw, "created_at") or datetime.fromtimestamp(0, tz=timezone.utc)

        events = raw.get("events") or []
        events = tuple(AlertEvent.parse(re) for re in events)

        decisions = raw.get("decisions") or []
        decisions = tuple(
            item for rd in decisions
            if (item := Decision.parse(rd, created_at)) is not None
        )

        return cls(
            id = parse_int_field(raw, "id"),
            uuid = parse_string_field(raw, "uuid", ""),
            machine_id = parse_string_field(raw, "machine_id", ""),
            created_at = created_at,
            scenario = parse_string_field(raw, "scenario"),
            scenario_hash = parse_string_field(raw, "scenario_hash", ""),
            scenario_version = parse_string_field(raw, "scenario_version", ""),
            message = parse_string_field(raw, "message", ""),
            events_count = parse_int_field(raw, "events_count"),
            start_at = parse_datetime_field(raw, "start_at") or datetime.fromtimestamp(0, tz=timezone.utc),
            stop_at = parse_datetime_field(raw, "stop_at") or datetime.fromtimestamp(0, tz=timezone.utc),
            capacity = parse_int_field(raw, "capacity"),
            leakspeed = parse_string_field(raw, "leakspeed"),
            simulated = parse_bool_field(raw, "simulated"),
            events = events,
            remediation = parse_bool_field(raw, "remediation"),
            decisions = decisions,
            source = AlertSource.parse(raw.get("source")),
            meta = _parse_meta(raw.get("meta")),
            labels = tuple(str(l) for l in (raw.get("labels") or []) if l),
            kind = parse_string_field(raw, "kind"),
        )

    def identity_key(self) -> AlertIdentityKey | None:
        return AlertIdentityKey.of(self.id, self.uuid)

    def __eq__(self, value):
        if not isinstance(value, Alert):
            return False
        return self.identity_key() == value.identity_key()

    def __hash__(self):
        return hash(self.identity_key())

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
    def decisions_count_metric_labels() -> list[str]:
        return Alert.created_metric_labels()
    def decisions_count_metric_label_values(self) -> list[str]:
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

    @staticmethod
    def grand_total_metric_labels() -> list[str]:
        return [
            "scenario",
            "country",
            "as_number",
            "as_name",
        ]
    def grand_total_metric_label_values(self) -> list[str]:
        return [
            self.scenario,
            self.source.country,
            self.source.as_number,
            self.source.as_name,
        ]

    @staticmethod
    def decisions_grand_total_metric_labels() -> list[str]:
        return [
            "scenario",
            "country",
            "as_number",
            "as_name",
            "origin"
        ]

    def decisions_grand_total_metric_label_values(self) -> Iterable[tuple[list[str],int]]:
        decisions_by_origin = {}
        for d in self.decisions:
            origin = d.origin
            if origin not in decisions_by_origin:
                decisions_by_origin[origin] = 0
            decisions_by_origin[origin] += 1

        result : dict[str,tuple[list[str], int]] = {}
        for origin, count in decisions_by_origin.items():
            result[origin] = (
                [
                    self.scenario,
                    self.source.country,
                    self.source.as_number,
                    self.source.as_name,
                    origin
                ],
                count
            )

        return list(result.values())

def _parse_meta(raw: Any) -> dict[str, str]:
    if not isinstance(raw, list):
        return {}

    return {
        str(item["key"]): str(item["value"])
        for item in raw
        if isinstance(item, dict) and "key" in item and "value" in item
    }
