from typing import Any

from models.decision import Decision
from models.allowlist import Allowlist
from models.alert import Alert
from logger import get_logger

log = get_logger(__name__)

def parse_decisions(raw_list: list[Any]) -> list[Decision]:
    return [Decision.parse(i) for i in raw_list]

def parse_allowlists(raw_list: list[Any]) -> list[Allowlist]:
    return [Allowlist.parse(i) for i in raw_list]

def parse_alerts(raw_list: list[Any]) -> list[Alert]:
    return [Alert.parse(i) for i in raw_list]
