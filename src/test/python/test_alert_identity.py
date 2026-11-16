"""Unit tests for AlertIdentityKey (models/alert.py)."""

import dataclasses

import pytest

from models import AlertIdentityKey


class TestFactories:
    def test_of_builds_a_key_when_an_identifier_is_present(self):
        assert AlertIdentityKey.of(187187, "") == AlertIdentityKey(187187, "")
        assert AlertIdentityKey.of(0, "u") == AlertIdentityKey(0, "u")

    def test_of_returns_none_without_any_identifier(self):
        assert AlertIdentityKey.of(0, "") is None

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ({"id": 5, "uuid": "x"}, AlertIdentityKey(5, "x")),
            ({"id": 187187, "uuid": ""}, AlertIdentityKey(187187, "")),  # CAPI alert
            ({}, None),
            ({"id": 0, "uuid": ""}, None),
        ],
    )
    def test_parse(self, raw: dict, expected):
        assert AlertIdentityKey.parse(raw) == expected


class TestConstruction:
    def test_direct_empty_construction_is_rejected(self):
        with pytest.raises(ValueError, match="at least one identifier"):
            AlertIdentityKey(0, "")

    def test_is_frozen(self):
        key = AlertIdentityKey(1, "a")
        with pytest.raises(dataclasses.FrozenInstanceError):
            key.id = 2  # type: ignore[misc]


class TestEqualityAndHashing:
    def test_equality_and_hash_by_id_and_uuid(self):
        assert AlertIdentityKey(1, "a") == AlertIdentityKey(1, "a")
        assert hash(AlertIdentityKey(1, "a")) == hash(AlertIdentityKey(1, "a"))

    def test_distinct_capi_keys_with_empty_uuid_stay_distinct(self):
        # CAPI update alerts have an empty uuid, so the id keeps them apart
        a, b = AlertIdentityKey(187187, ""), AlertIdentityKey(187188, "")
        assert a != b
        assert len({a, b}) == 2

    def test_usable_as_dict_keys(self):
        seen = {AlertIdentityKey(1, "a"): 1, AlertIdentityKey(2, "b"): 2}
        assert AlertIdentityKey(1, "a") in seen
        assert AlertIdentityKey(3, "c") not in seen
