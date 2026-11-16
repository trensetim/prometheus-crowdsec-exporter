"""Unit tests for AlertDeduplicator and CrowdsecPoller.poll_alerts (src/main/python/poller.py)."""

import dataclasses
import re
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
import requests

import poller as poller_mod
from models import Alert, AlertIdentityKey
from poller import AlertDeduplicator, CrowdsecPoller
from scenario import ScenarioRewriter

_NOW = datetime.now(tz=timezone.utc)
T1 = (_NOW - timedelta(minutes=5)).isoformat()
T2 = (_NOW - timedelta(minutes=4)).isoformat()
T3 = (_NOW - timedelta(minutes=3)).isoformat()


@dataclasses.dataclass
class DummyConfig:
    version: str = "1.4.2"
    lapi_url: str = "http://localhost:8080"
    machine_id: str = "m1"
    machine_password: str = "pw"
    http_timeout_seconds: float = 5.0
    batch_size: int = 2
    alert_dedup_window_size: int = 50_000
    scenario_rewriter: ScenarioRewriter | None = None


def _poller(batch_size: int = 2, window: int = 50_000, scenario_rewriter: ScenarioRewriter | None = None) -> CrowdsecPoller:
    return CrowdsecPoller(DummyConfig(batch_size=batch_size, alert_dedup_window_size=window, scenario_rewriter=scenario_rewriter))


def _fetch_sequence(pages: list[list]):
    """Return a fake `_fetch` that yields each page in turn, then empty pages."""
    remaining = list(pages)

    def _fetch(_path: str):
        return remaining.pop(0) if remaining else []

    return _fetch


class TestAlertDeduplicator:
    def test_duplicate_is_suppressed_before_reparsing(self, raw_alert):
        dedup = AlertDeduplicator(capacity=100)
        alert = raw_alert(alert_id=1, uuid="u1")
        assert dedup.process(alert) is not None
        with patch.object(poller_mod.Alert, "parse", wraps=poller_mod.Alert.parse) as spy:
            assert dedup.process(alert) is None  # same identity -> suppressed
            spy.assert_not_called()              # ... and not re-parsed

    def test_capacity_evicts_the_oldest(self, raw_alert):
        dedup = AlertDeduplicator(capacity=2)
        for i in (1, 2, 3):
            assert dedup.process(raw_alert(alert_id=i, uuid=f"u{i}")) is not None
        dedup.commit()
        dedup.rollback()
        # id=1 was evicted when id=3 arrived -> seen as new again; id=3 is still resident
        assert dedup.process(raw_alert(alert_id=1, uuid="u1")) is not None
        assert dedup.process(raw_alert(alert_id=3, uuid="u3")) is None

    def test_hit_refreshes_recency_so_the_cold_key_is_evicted(self, raw_alert):
        dedup = AlertDeduplicator(capacity=2)
        dedup.process(raw_alert(alert_id=1, uuid="u1"))
        dedup.process(raw_alert(alert_id=2, uuid="u2"))
        dedup.process(raw_alert(alert_id=1, uuid="u1"))  # hit on 1 refreshes its recency
        dedup.process(raw_alert(alert_id=3, uuid="u3"))  # inserting 3 evicts the coldest (2)
        assert AlertIdentityKey(1, "u1") in dedup._uncommitted
        assert AlertIdentityKey(3, "u3") in dedup._uncommitted
        assert AlertIdentityKey(2, "u2") not in dedup._uncommitted

    def test_commit_and_rollback_are_isolated_snapshots(self, raw_alert):
        dedup = AlertDeduplicator(capacity=100)
        dedup.process(raw_alert(alert_id=1, uuid="u1"))
        dedup.commit()
        dedup.process(raw_alert(alert_id=2, uuid="u2"))  # staged, not committed
        dedup.rollback()
        assert AlertIdentityKey(2, "u2") not in dedup._uncommitted
        assert AlertIdentityKey(1, "u1") in dedup._uncommitted
        # a post-commit edit must not retroactively mutate the committed snapshot
        dedup.process(raw_alert(alert_id=5, uuid="u5"))
        dedup.commit()
        dedup.process(raw_alert(alert_id=6, uuid="u6"))
        assert AlertIdentityKey(6, "u6") not in dedup._seen_alerts
        assert dedup._seen_alerts is not dedup._uncommitted

    def test_identity_less_alert_is_emitted_and_not_stored(self, raw_alert):
        dedup = AlertDeduplicator(capacity=100)
        first = dedup.process(raw_alert(alert_id=0, uuid=""))
        second = dedup.process(raw_alert(alert_id=0, uuid=""))
        assert first is not None and second is not None  # both pass through
        assert dedup._uncommitted == OrderedDict()        # nothing stored (no identity)

    def test_delegates_parsing_to_the_injected_parse_func(self, raw_alert):
        # the deduplicator parses via an injected callable; here it applies a scenario rewriter
        rewriter = ScenarioRewriter.parse(";^update : .*;capi-update;")
        dedup = AlertDeduplicator(capacity=100, parse_func=lambda raw: Alert.parse(raw, rewriter))
        alert = dedup.process(raw_alert(alert_id=1, uuid="u1", scenario="update : +14999/-0 IPs"))
        assert alert is not None
        assert alert.scenario == "capi-update"


class TestPollAlerts:
    def test_returns_new_alerts_across_pages(self, raw_alert):
        poller = _poller(batch_size=2)
        poller._fetch = _fetch_sequence([
            [raw_alert(alert_id=1, uuid="u1", created_at=T1), raw_alert(alert_id=2, uuid="u2", created_at=T2)],
            [raw_alert(alert_id=3, uuid="u3", created_at=T3)],
            [],
        ])
        assert sorted(a.id for a in poller.poll_alerts()) == [1, 2, 3]

    def test_boundary_duplicate_is_suppressed_on_the_next_poll(self, raw_alert):
        poller = _poller(batch_size=2)
        poller._fetch = _fetch_sequence([[raw_alert(alert_id=1, uuid="u1", created_at=T1), raw_alert(alert_id=2, uuid="u2", created_at=T2)], []])
        assert sorted(a.id for a in poller.poll_alerts()) == [1, 2]
        # next poll re-sends the boundary alert (2) plus a genuinely new one (3)
        poller._fetch = _fetch_sequence([[raw_alert(alert_id=2, uuid="u2", created_at=T2), raw_alert(alert_id=3, uuid="u3", created_at=T3)], []])
        assert [a.id for a in poller.poll_alerts()] == [3]

    def test_idle_poll_returns_empty_and_skips_reparsing(self, raw_alert):
        poller = _poller(batch_size=2)
        poller._fetch = _fetch_sequence([[raw_alert(alert_id=1, uuid="u1", created_at=T1), raw_alert(alert_id=187187, uuid="", created_at=T2, decisions_count=5)], []])
        poller.poll_alerts()
        poller._fetch = _fetch_sequence([[raw_alert(alert_id=187187, uuid="", created_at=T2, decisions_count=5)], []])
        with patch.object(poller_mod.Alert, "parse", wraps=poller_mod.Alert.parse) as spy:
            assert poller.poll_alerts() == []
            spy.assert_not_called()  # the duplicate CAPI alert is not re-parsed

    def test_all_duplicate_full_batch_does_not_crash(self, raw_alert):
        poller = _poller(batch_size=2)
        page = [raw_alert(alert_id=1, uuid="u1", created_at=T1), raw_alert(alert_id=2, uuid="u2", created_at=T2)]
        poller._fetch = _fetch_sequence([list(page), []])
        poller.poll_alerts()
        poller._fetch = _fetch_sequence([list(page), []])  # a full page where everything is already seen
        assert poller.poll_alerts() == []

    def test_identity_less_alert_is_always_returned(self, raw_alert):
        poller = _poller(batch_size=2)
        poller._fetch = _fetch_sequence([[raw_alert(alert_id=0, uuid="", created_at=T1)], []])
        assert [a.id for a in poller.poll_alerts()] == [0]
        assert poller._deduplicator._seen_alerts == OrderedDict()

    def test_watermark_advances_to_latest_created_at(self, raw_alert):
        poller = _poller(batch_size=10)
        poller._fetch = _fetch_sequence([[raw_alert(alert_id=1, uuid="u1", created_at=T1), raw_alert(alert_id=2, uuid="u2", created_at=T3)], []])
        poller.poll_alerts()
        assert poller._last_alert_created_at == datetime.fromisoformat(T3)

    def test_mid_poll_failure_rolls_back_and_recovers_without_undercounting(self, raw_alert):
        poller = _poller(batch_size=2)
        calls = {"n": 0}

        def failing(_path: str):
            calls["n"] += 1
            if calls["n"] == 1:
                return [raw_alert(alert_id=200, uuid="u200", created_at=T1), raw_alert(alert_id=201, uuid="u201", created_at=T2)]
            raise requests.exceptions.ConnectionError("boom")

        poller._fetch = failing
        with pytest.raises(requests.exceptions.ConnectionError):
            poller.poll_alerts()
        assert poller._deduplicator._seen_alerts == OrderedDict()  # nothing committed on failure
        assert poller._last_alert_created_at is None                # watermark not advanced

        poller._fetch = _fetch_sequence([
            [raw_alert(alert_id=200, uuid="u200", created_at=T1), raw_alert(alert_id=201, uuid="u201", created_at=T2)],
            [raw_alert(alert_id=300, uuid="u300", created_at=T3)],
            [],
        ])
        assert sorted(a.id for a in poller.poll_alerts()) == [200, 201, 300]

    def test_full_boundary_duplicate_page_does_not_shadow_a_newer_alert(self, raw_alert):
        # Regression for the boundary-page stall: when a full page (== batch_size) of
        # already-seen alerts shares the boundary timestamp, the poller widens the window
        # (doubling the limit) to reach genuinely newer alerts behind them, instead of stalling.
        class _LimitServer:
            """Minimal LAPI stub that honours `limit` so a wider window returns more rows."""
            def __init__(self, store: list[dict]):
                self.store = store

            def fetch(self, path: str):
                limit = int(re.search(r"limit=(\d+)", path).group(1))
                return self.store[:limit]

        poller = _poller(batch_size=2)
        boundary = [raw_alert(alert_id=10, uuid="u10", created_at=T1), raw_alert(alert_id=11, uuid="u11", created_at=T1)]

        # first poll: only the two boundary alerts exist; they become the watermark
        poller._fetch = _LimitServer(list(boundary)).fetch
        assert sorted(a.id for a in poller.poll_alerts()) == [10, 11]

        # second poll: a full page of those two duplicates precedes a newer alert (12)
        poller._fetch = _LimitServer(boundary + [raw_alert(alert_id=12, uuid="u12", created_at=T2)]).fetch
        second = [a.id for a in poller.poll_alerts()]
        assert second == [12]  # newer alert reached, boundary duplicates not re-emitted
