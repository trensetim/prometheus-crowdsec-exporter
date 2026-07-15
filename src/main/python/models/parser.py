from typing import Any

from models.decision import Decision
from models.allowlist import Allowlist
from models.alert import Alert
from logger import getLogger

log = getLogger(__name__)

def parseDecisions(raw_list: list[Any],) -> tuple[list[Decision], int]:
    return _parseList(raw_list, Decision.mapClassFromApiDict, "decisions")

def parseAllowlists(raw_list: list[Any],) -> tuple[list[Allowlist], int]:
    return _parseList(raw_list, Allowlist.mapClassFromApiDict, "allowlists")

def parseAlerts(raw_list: list[Any],) -> tuple[list[Alert], int]:
    return _parseList(raw_list, Alert.mapClassFromApiDict, "alerts")

def _parseList(raw_list, factory, kind: str):
    results = []
    skipped = 0
    for i, raw in enumerate(raw_list):
        obj = factory(raw, index=i)
        if obj is not None:
            results.append(obj)
        else:
            skipped += 1

    if skipped:
        log.warning(
            "parsePartialResult",
            kind = kind,
            total = len(raw_list),
            parsed = len(results),
            skipped = skipped,
        )
    return results, skipped
