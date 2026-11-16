"""Shared pytest fixtures for the unit tests."""

import pytest


@pytest.fixture
def raw_alert():
    """
    Factory for a raw CrowdSec LAPI alert dict (as returned by /v1/alerts), with sensible
    defaults that every field-parser accepts. Override any field via keyword arguments.
    `decisions_count` generates that many CAPI `ban` decisions.
    """
    def _make(
        alert_id: int = 1,
        uuid: str = "u1",
        created_at: str = "2026-11-13T12:00:00+00:00",
        scenario: str = "crowdsecurity/ssh-bf",
        decisions_count: int = 0,
    ) -> dict:
        return {
            "id": alert_id,
            "uuid": uuid,
            "machine_id": "m1",
            "created_at": created_at,
            "scenario": scenario,
            "scenario_hash": "h",
            "scenario_version": "0.1",
            "message": "msg",
            "events_count": 1,
            "start_at": created_at,
            "stop_at": created_at,
            "capacity": 5,
            "leakspeed": "10s",
            "simulated": False,
            "remediation": True,
            "kind": "signal",
            "labels": [],
            "events": [],
            "meta": [],
            "source": {
                "scope": "Ip", "value": "1.2.3.4", "ip": "1.2.3.4", "range": "1.2.3.0/24",
                "as_number": "1", "as_name": "AS1", "cn": "DE", "latitude": 1.0, "longitude": 2.0,
            },
            "decisions": [
                {
                    "id": i, "uuid": "", "origin": "CAPI", "type": "ban", "scope": "Ip",
                    "value": f"10.0.0.{i}", "duration": "24h", "until": None,
                    "scenario": scenario, "simulated": False,
                }
                for i in range(decisions_count)
            ],
        }

    return _make
