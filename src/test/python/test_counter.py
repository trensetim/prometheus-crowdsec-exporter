"""Unit tests for the always-differential counters (src/main/python/counter.py)."""

from datetime import timedelta
from time import time

import pytest
from prometheus_client.metrics_core import CounterMetricFamily

from counter import TotalCounter, TotalCounterCollection


def _collect(counter: TotalCounter) -> list[tuple[dict, float]]:
    metric = CounterMetricFamily("x", "d", labels=["l"])
    counter.collect(metric)
    return [(s.labels, s.value) for s in metric.samples]


def _values_by_labels(metric: CounterMetricFamily) -> dict[tuple, float]:
    return {tuple(s.labels.values()): s.value for s in metric.samples}


class TestTotalCounter:
    def test_increment_accumulates(self):
        counter = TotalCounter(["a"], reset_at_start=False)
        counter.increment()
        counter.increment(4)
        assert _collect(counter) == [({"l": "a"}, 5)]

    def test_reset_at_start_emits_zero_then_the_real_count(self):
        counter = TotalCounter(["a"], reset_at_start=True)
        counter.increment(5)
        # the first scrape yields a virtual zero sample ...
        assert _collect(counter) == [({"l": "a"}, 0)]
        # ... and subsequent scrapes yield the accumulated value
        assert _collect(counter) == [({"l": "a"}, 5)]

    def test_without_reset_emits_count_immediately(self):
        counter = TotalCounter(["a"], reset_at_start=False)
        counter.increment(5)
        assert _collect(counter) == [({"l": "a"}, 5)]

    def test_hash_and_equality_by_label_values(self):
        assert TotalCounter(["a", "b"], False) == TotalCounter(["a", "b"], True)
        assert hash(TotalCounter(["a", "b"], False)) == hash(TotalCounter(["a", "b"], False))
        assert TotalCounter(["a"], False) != TotalCounter(["b"], False)

    def test_last_increment_timestamp_none(self):
        c = TotalCounter(["a"], False)
        assert c.last_increment_timestamp() is None
        c.increment()
        assert c.last_increment_timestamp() is not None
        c.increment()
        assert c.last_increment_timestamp() is not None


class TestTotalCounterCollection:
    @staticmethod
    def _collection(max_count: int = 1000, max_age_seconds: int = 300) -> TotalCounterCollection:
        return TotalCounterCollection(max_count, timedelta(seconds=max_age_seconds))

    def _set_timestamp(self, collection: TotalCounterCollection, label_values: list[str], ts: float):
        collection._counters[TotalCounter.hash_impl(label_values)]._last_increment_timestamp = ts

    def test_increment_tracks_per_label_and_grand_total(self):
        collection = self._collection()
        collection.increment(["ip1"], ["grand"], amount=3)
        collection.increment(["ip2"], ["grand"], amount=2)

        per_label = _values_by_labels(collection.collect(CounterMetricFamily("c", "d", labels=["l"])))
        assert per_label == {("ip1",): 3.0, ("ip2",): 2.0}

        grand = _values_by_labels(collection.collect_grand_totals(CounterMetricFamily("g", "d", labels=["l"])))
        assert grand == {("grand",): 5.0}  # both increments fold into the single grand-total labelset

    def test_reset_at_start_defers_first_sample_to_zero(self):
        collection = self._collection()
        collection.increment(["ip1"], ["grand"], amount=3, reset_at_start=True)
        first = _values_by_labels(collection.collect(CounterMetricFamily("c", "d", labels=["l"])))
        assert first == {("ip1",): 0.0}
        second = _values_by_labels(collection.collect(CounterMetricFamily("c", "d", labels=["l"])))
        assert second == {("ip1",): 3.0}

    def test_prune_removes_counters_older_than_max_age(self):
        collection = self._collection(max_age_seconds=100)
        collection.increment(["old"], ["g"])
        collection.increment(["fresh"], ["g"])
        self._set_timestamp(collection, ["old"], time() - 10_000)  # well outside the 100s window

        collection.prune()

        remaining = _values_by_labels(collection.collect(CounterMetricFamily("c", "d", labels=["l"])))
        assert set(remaining.keys()) == {("fresh",)}

    def test_prune_trims_to_max_count_evicting_the_oldest(self):
        collection = self._collection(max_count=2, max_age_seconds=10_000)
        base = time()
        for i, name in enumerate(["a", "b", "c"]):
            collection.increment([name], ["g"])
            self._set_timestamp(collection, [name], base - (10 - i))  # a oldest, c newest; all within window

        collection.prune()

        remaining = _values_by_labels(collection.collect(CounterMetricFamily("c", "d", labels=["l"])))
        assert set(remaining.keys()) == {("b",), ("c",)}  # oldest "a" evicted

    def test_prune_never_removes_grand_totals(self):
        collection = self._collection(max_count=1, max_age_seconds=1)

        collection.increment(["ip"], ["grand"])
        collection.increment(["ip2"], ["grand"])
        collection.prune()  # aggressively prunes per-label counters, but must not touch grand totals

        grand = _values_by_labels(collection.collect_grand_totals(CounterMetricFamily("g", "d", labels=["l"])))
        assert grand == {("grand",): 2.0}
