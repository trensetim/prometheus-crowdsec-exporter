"""Unit tests for the field parsing helpers (src/main/python/models/_parse_utils.py)."""

from datetime import datetime, timezone

import pytest

from models._parse_utils import (
    are_required_fields_present,
    parse_bool_field,
    parse_datetime_field,
    parse_int_field,
    parse_string_field,
)


class TestParseStringField:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ({"k": "value"}, "value"),
            ({"k": "  trimmed  "}, "trimmed"),  # surrounding whitespace is stripped
            ({"k": 123}, "123"),                # non-strings are coerced via str()
            ({"k": ""}, "unknown"),             # empty -> fallback
            ({"k": "   "}, "unknown"),          # whitespace-only -> fallback
            ({"k": None}, "unknown"),           # None -> fallback
            ({}, "unknown"),                    # missing -> fallback
        ],
    )
    def test_default_fallback(self, raw: dict, expected: str):
        assert parse_string_field(raw, "k") == expected

    def test_custom_fallback(self):
        assert parse_string_field({}, "k", "custom") == "custom"


class TestParseBoolField:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ({"k": True}, True),
            ({"k": False}, False),
            ({"k": "true"}, True),
            ({"k": "True"}, True),   # case-insensitive
            ({"k": "false"}, False),
            ({"k": "yes"}, False),   # only "true" is truthy for strings
            ({"k": " true "}, False),  # NOTE: no stripping, so padded "true" is False
            ({"k": 1}, True),        # non-str/bool falls back to bool()
            ({"k": 0}, False),
        ],
    )
    def test_parsing(self, raw: dict, expected: bool):
        assert parse_bool_field(raw, "k") is expected

    def test_missing_uses_fallback(self):
        assert parse_bool_field({}, "k", fallback=True) is True


class TestParseIntField:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ({"k": 42}, 42),
            ({"k": "42"}, 42),
            ({"k": 1.9}, 1),       # float is truncated by int()
            ({"k": "1.5"}, -1),    # non-integer string -> fallback
            ({"k": None}, -1),     # None -> fallback
            ({"k": "abc"}, -1),    # garbage -> fallback
            ({}, -1),              # missing -> fallback
        ],
    )
    def test_parsing(self, raw: dict, expected: int):
        assert parse_int_field(raw, "k", fallback=-1) == expected


class TestParseDatetimeField:
    def test_iso_with_offset(self):
        assert parse_datetime_field({"k": "2026-01-02T03:04:05+00:00"}, "k") == datetime(
            2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc
        )

    def test_zulu_suffix_is_normalized(self):
        assert parse_datetime_field({"k": "2026-01-02T03:04:05Z"}, "k") == datetime(
            2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc
        )

    @pytest.mark.parametrize("raw", [{"k": None}, {"k": ""}, {}, {"k": "not-a-date"}])
    def test_missing_or_invalid_returns_none(self, raw: dict):
        assert parse_datetime_field(raw, "k") is None


class TestAreRequiredFieldsPresent:
    # NOTE: despite its name, this returns the list of *missing* fields (empty == all present).
    def test_all_present_returns_empty(self):
        assert are_required_fields_present({"a": 1, "b": 2}, ["a", "b"]) == []

    def test_returns_missing_fields(self):
        assert are_required_fields_present({"a": 1}, ["a", "b", "c"]) == ["b", "c"]
