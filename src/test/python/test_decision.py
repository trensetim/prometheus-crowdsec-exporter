"""Unit tests for Decision parsing, duration and origin handling (models/decision.py)."""

from datetime import datetime, timedelta, timezone

import pytest

from models.decision import CommonDecisionOrigin, Decision

CREATED_AT = datetime(2026, 11, 13, 12, 0, 0, tzinfo=timezone.utc)


def _raw(**overrides) -> dict:
    base = {
        "id": 7,
        "uuid": "d-uuid",
        "type": "ban",
        "origin": "crowdsec",
        "scenario": "crowdsecurity/ssh-bf",
        "scope": "Ip",
        "value": "1.2.3.4",
        "duration": "24h",
        "simulated": False,
    }
    base.update(overrides)
    return base


class TestParseDuration:
    @pytest.mark.parametrize(
        "duration, expected",
        [
            ("", timedelta(0)),
            ("100s", timedelta(seconds=100)),
            ("90m", timedelta(minutes=90)),
            ("4h30m", timedelta(hours=4, minutes=30)),
            ("1d", timedelta(days=1)),
            # components beyond their usual range are summed, not clamped
            ("7d24h60m20s", timedelta(days=7, hours=24, minutes=60, seconds=20)),
            # a non-matching string yields zero (fullmatch fails)
            ("garbage", timedelta(0)),
        ],
    )
    def test_parse_duration(self, duration: str, expected: timedelta):
        assert Decision._parse_duration(duration) == expected


class TestParseOrigin:
    @pytest.mark.parametrize(
        "origin, expected",
        [
            ("crowdsec", CommonDecisionOrigin.CROWDSEC),
            ("CAPI", CommonDecisionOrigin.CAPI),   # matched case-insensitively
            ("capi", CommonDecisionOrigin.CAPI),
            ("cscli", CommonDecisionOrigin.CSCLI),
        ],
    )
    def test_known_origins(self, origin: str, expected: CommonDecisionOrigin):
        decision = Decision.parse(_raw(origin=origin), CREATED_AT)
        assert decision is not None
        assert decision.parse_origin() is expected

    def test_unknown_origin_returns_none(self):
        decision = Decision.parse(_raw(origin="some-custom-origin"), CREATED_AT)
        assert decision is not None
        assert decision.parse_origin() is None


class TestParse:
    def test_parses_all_fields(self):
        decision = Decision.parse(_raw(), CREATED_AT)
        assert decision is not None
        assert decision.decision_id == 7
        assert decision.type == "ban"
        assert decision.scope == "Ip"
        assert decision.value == "1.2.3.4"

    def test_until_is_taken_from_the_field_when_present(self):
        decision = Decision.parse(_raw(until="2030-01-01T00:00:00Z"), CREATED_AT)
        assert decision is not None
        assert decision.until == datetime(2030, 1, 1, tzinfo=timezone.utc)

    def test_until_is_derived_from_created_at_plus_duration_when_absent(self):
        decision = Decision.parse(_raw(duration="2h", until=None), CREATED_AT)
        assert decision is not None
        assert decision.until == CREATED_AT + timedelta(hours=2)

    @pytest.mark.parametrize("missing", ["type", "origin", "scenario", "scope"])
    def test_missing_required_field_raises(self, missing: str):
        raw = _raw()
        del raw[missing]
        with pytest.raises(ValueError, match="missing required fields"):
            Decision.parse(raw, CREATED_AT)

    def test_non_dict_raises(self):
        with pytest.raises(ValueError, match="not a dict"):
            Decision.parse(["not", "a", "dict"], CREATED_AT)
