from datetime import datetime
from typing import Any

def strField(raw: dict[str, Any], key: str, fallback: str = "unknown") -> str:
    v = raw.get(key)
    s = str(v).strip() if v is not None else ""
    return s if s else fallback

def boolField(raw: dict[str, Any], key: str, fallback: bool = False) -> bool:
    v = raw.get(key, fallback)
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.lower() == "true"
    return bool(v)

def intField(raw: dict[str, Any], key: str, fallback: int = 0) -> int:
    try:
        return int(raw.get(key, fallback))
    except (TypeError, ValueError):
        return fallback

def datetimeField(raw: dict[str, Any], key: str) -> datetime | None:
    v = raw.get(key)
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None

def requiredFieldsPresent(raw: dict[str, Any], fields: tuple[str, ...]) -> list[str]:
    return [f for f in fields if not raw.get(f)]
