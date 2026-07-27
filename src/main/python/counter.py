from prometheus_client.metrics_core import CounterMetricFamily

class TotalCounter:
    _hash: int
    _label_values: list[str]
    _count: int = 0
    _reset: bool

    _last_increment_timestamp: float
    """When this counter was incremented last, as UNIX seconds."""

    def __init__(self, label_values: list[str], reset_at_start: bool) -> None:
        self._label_values = label_values
        self._hash = TotalCounter.hash_impl(label_values)
        self._reset = reset_at_start

    def __hash__(self) -> int:
        return self._hash

    def __eq__(self, value) -> bool:
        if not isinstance(value, TotalCounter):
            return False
        return self._hash == value._hash

    def increment(self, amount: int = 1) -> None:
        self._count += amount
        self._last_increment_timestamp = time()

    def last_increment_timestamp(self) -> float:
        return self._last_increment_timestamp

    def _release_reset(self) -> None:
        self._reset = False
        # if a second increment happens during the reset offset,
        # we just take the then-later timestamp and discard the first-actual sample,
        # retaining only the virtual/reset/zero sample and the second sample -->
        # still yielding a correct increment.
        # This has the same effect as if prometheus just had not scraped
        # the exporter in the meantime

    def collect(self, m: CounterMetricFamily) -> None:
        if self._reset:
            # reset to 0 before incrementing: we know that this total metric is
            # always-differential and want to treat the first sample as an "increment" as well
            m.add_metric(self._label_values, 0)
            self._release_reset()
            return

        m.add_metric(self._label_values, self._count)

    @staticmethod
    def hash_impl(label_values: list[str]) -> int:
        return hash(",".join(label_values))

class TotalCounterCollection:
    """
    Contains the current counter values for a counter metric that is created per labelset adhoc (ie. the labels have a high cardinality and are not known in advance).
    This is useful for metrics that are always-differential, ie. they are always incremented and never reset to 0,
    and we want to treat the first sample as an "increment" as well, so that Prometheus increment()-queries see the initial poll as full increments.
    """
    _counters: dict[int, TotalCounter]

    _max_count: int
    """Maximum number of counters to keep in memory. If this is exceeded, the oldest counters will be pruned."""
    _max_age: timedelta
    """Maximum age for a non-incremented counter to be kept in memory. If this is exceeded, the counter will be pruned."""

    def __init__(self, max_count: int, max_age: timedelta) -> None:
        self._counters = {}
        self._max_count = max_count
        self._max_age = max_age
    def increment(self, label_values: list[str], amount: int = 1, reset_at_start: bool = False) -> None:
        counter = self._get_or_create(label_values, reset_at_start)
        counter.increment(amount)
    def _get_or_create(self, label_values: list[str], reset_at_start: bool) -> TotalCounter:
        """
        Return the current counter value for the given labelset, creating a new counter if it does not exist yet.
        If reset_at_start is True, the first sample will get delayed by one scrape and a virtual zero-value is inserted instead.
        This should be set for labelsets that are newly-discovered during runtime (such that Prometheus will eventually see them starting at zero).
        It should be carefully considered whether this is desired for the initial scrape after a restart of the exporter (setting False is most-commonly better to avoid double-counting).
        """

        key = TotalCounter.hash_impl(label_values)
        if key not in self._counters:
            self._counters[key] = TotalCounter(label_values, reset_at_start)
        return self._counters[key]

    def collect(self, m: CounterMetricFamily) -> CounterMetricFamily:
        for counter in self._counters.values():
            counter.collect(m)
        return m
    def prune(self) -> None:
        """
        Remove all counters that have not been incremented since the last prune() call.
        This is useful to avoid memory leaks for labelsets that are no longer used.
        """
        prune_age_threshold = (datetime.now(tz=timezone.utc) - self._max_age).timestamp()
        for (key, counter) in self._counters.items():
            if counter.last_increment_timestamp() < prune_age_threshold:
                del self._counters[key]

        while len(self._counters) > self._max_count:
            # remove the oldest counter
            oldest_key = min(self._counters.keys(), key=lambda k: self._counters[k].last_increment_timestamp())
            del self._counters[oldest_key]
