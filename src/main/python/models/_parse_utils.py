from datetime import datetime
from typing import Any

def parse_string_field(raw: dict[str, Any], key: str, fallback: str = "unknown") -> str:
    v = raw.get(key)
    s = str(v).strip() if v is not None else ""
    return s if s else fallback

def parse_bool_field(raw: dict[str, Any], key: str, fallback: bool = False) -> bool:
    v = raw.get(key, fallback)
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.lower() == "true"
    return bool(v)

def parse_int_field(raw: dict[str, Any], key: str, fallback: int = 0) -> int:
    try:
        return int(raw.get(key, fallback))
    except (TypeError, ValueError):
        return fallback

def parse_datetime_field(raw: dict[str, Any], key: str) -> datetime | None:
    v = raw.get(key)
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None

def are_required_fields_present(raw: dict[str, Any], fields: set[str]) -> list[str]:
    return [f for f in fields if f not in raw]
