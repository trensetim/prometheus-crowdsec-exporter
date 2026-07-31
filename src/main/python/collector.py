from typing import Iterable
import time

from prometheus_client import Metric
from prometheus_client.registry import Collector
from counter import TotalCounterCollection

import metrics
from config import Config
from logger import get_logger
from poller import CrowdsecPoller
from models import Alert, Allowlist

log = get_logger(__name__)

# pylint: disable=too-many-instance-attributes
# pylint: disable=too-few-public-methods
class CrowdsecCollector(Collector):

    _poller: CrowdsecPoller

    _last_allowlist_names: set[str] = set()
    """Names of the allowlists of last poll, to prevent double-counting"""
    _last_allowlist_items: set[str] = set()
    """Values of the allowlist items of last poll, to prevent double-counting (across all allowlists)"""

    _metric_polls_total: int = 0
    _metric_poll_errors_total: int = 0
    _metric_last_poll_duration_seconds: float = 0
    _metric_last_heartbeat_duration_seconds: float = 0
    _metric_decisions_total: TotalCounterCollection
    _metric_alerts_total: TotalCounterCollection
    _metric_events_total: TotalCounterCollection
    _metric_allowlists_total: int = 0
    _metric_allowlist_items_total: int = 0

    def __init__(self, config: Config) -> None:
        self._config_version = config.version
        self._poller = CrowdsecPoller(config)
        self._metric_decisions_total = TotalCounterCollection(config.metrics_counter_max_count, config.metrics_counter_max_age)
        self._metric_alerts_total = TotalCounterCollection(config.metrics_counter_max_count, config.metrics_counter_max_age)
        self._metric_events_total = TotalCounterCollection(config.metrics_counter_max_count, config.metrics_counter_max_age)
        log.info("collector_initialised")

        if not config.metrics_retain_counter_startup_increments:
            # this is the "default" behavior, to avoid counter resets after exporter restarts
            log.info("initial_poll_running")
            first_poll_result = self._poll()
            if first_poll_result is None:
                raise RuntimeError("initial poll failed, cannot start exporter")
            (alerts, _) = first_poll_result
            self._update_totals(
                alerts,
                self._metric_alerts_total,
                self._metric_events_total,
                self._metric_decisions_total,
                reset_at_start=False
            )
            log.info("collector_startup_increment_discarded", alerts_count=len(alerts))

    def collect(self) -> Iterable[Metric]:
        yield metrics.exporter_info(self._config_version)

        poll_result: tuple[list[Alert], list[Allowlist]] | None
        try:
            self._beat_the_heart()
            poll_result = self._poll()
        except Exception as _: # pylint: disable=broad-exception-caught
            poll_result = None
        finally:
            yield metrics.crowdsec_up(poll_result is not None)

        (alerts, allowlists) = poll_result or ([], [])

        self._update_totals(
            alerts,
            self._metric_alerts_total,
            self._metric_events_total,
            self._metric_decisions_total,
            reset_at_start=True
        )

        yield metrics.polls_total(self._metric_polls_total)
        yield metrics.poll_errors_total(self._metric_poll_errors_total)
        yield metrics.last_poll_duration_seconds(self._metric_last_poll_duration_seconds)
        yield metrics.last_heartbeat_duration_seconds(self._metric_last_heartbeat_duration_seconds)

        yield self._collect_decisions(alerts)
        yield self._collect_alerts(alerts)
        yield self._collect_alert_created(alerts)
        yield self._collect_alert_start(alerts)
        yield self._collect_alert_stop(alerts)
        yield self._collect_alert_events_count(alerts)
        yield self._collect_alert_decisions_count(alerts)
        yield self._collect_allowlists(allowlists)
        yield self._collect_allowlists_total(allowlists)
        yield self._collect_allowlist_created(allowlists)
        yield self._collect_allowlist_updated(allowlists)
        yield self._collect_allowlist_console_managed(allowlists)
        yield self._collect_allowlist_items(allowlists)
        yield self._collect_allowlist_items_total(allowlists)
        yield self._collect_allowlist_item_created(allowlists)
        yield self._collect_allowlist_item_expiration(allowlists)

        yield from self._collect_totals(
            self._metric_decisions_total,
            self._metric_alerts_total,
            self._metric_events_total
        )

        self._last_allowlist_names = {a.name for a in allowlists}
        self._last_allowlist_items = {item.value for allowlist in allowlists for item in allowlist.items}

    def _beat_the_heart(self) -> None:
        start = time.monotonic()
        self._poller.beat_the_heart()
        end = time.monotonic()
        self._metric_last_heartbeat_duration_seconds = round(end - start, 3)
        log.info("heartbeat_success", duration_seconds = self._metric_last_heartbeat_duration_seconds)

    def _poll(self) -> tuple[list[Alert], list[Allowlist]] | None:
        """
        Connects with the CrowdSec LAPI and fetches+parses the relevant data.
        Errors are logged and turned into a ..._poll_errors_total metric.
        """
        self._metric_polls_total += 1

        start = time.monotonic()

        try:
            allowlists = self._poller.poll_allowlists()
            alerts = self._poller.poll_alerts()

            end = time.monotonic()
            self._metric_last_poll_duration_seconds = round(end - start, 3)
            log.info("poll_success", duration_seconds = self._metric_last_poll_duration_seconds, new_alerts_count = len(alerts), allowlists_count = len(allowlists))
            return (alerts, allowlists)
        except Exception as err: # pylint: disable=broad-exception-caught
            self._metric_poll_errors_total += 1

            end = time.monotonic()
            self._metric_last_poll_duration_seconds = round(end - start, 3)
            log.warning("poll_failed", error = err, duration_seconds = self._metric_last_poll_duration_seconds)
            return None

    def _collect_decisions(self, alerts: list[Alert]) -> Metric:
        m = metrics.decisions()
        for alert in alerts:
            for decision in alert.decisions:
                m.add_metric(decision.metric_label_values(alert_id=alert.id, alert_uuid=alert.uuid), 1, alert.created_at.timestamp())
        return m

    def _collect_allowlists(self, allowlists: list[Allowlist]) -> Metric:
        m = metrics.allowlists()
        for al in allowlists:
            m.add_metric(al.metric_label_values(), 1)
        return m

    def _collect_allowlist_created(self, allowlists: list[Allowlist]) -> Metric:
        m = metrics.allowlist_created()
        for al in allowlists:
            m.add_metric(al.created_metric_label_values(), al.created_at.timestamp())
        return m

    def _collect_allowlist_updated(self, allowlists: list[Allowlist]) -> Metric:
        m = metrics.allowlist_updated()
        for al in allowlists:
            m.add_metric(al.updated_metric_label_values(), al.updated_at.timestamp())
        return m

    def _collect_allowlist_console_managed(self, allowlists: list[Allowlist]) -> Metric:
        m = metrics.allowlist_console_managed()
        for al in allowlists:
            m.add_metric(al.console_managed_metric_label_values(), 1 if al.console_managed else 0)
        return m

    def _collect_allowlists_total(self, allowlists: list[Allowlist]) -> Metric:
        new_allowlists = [al for al in allowlists if al.name not in self._last_allowlist_names]
        self._metric_allowlists_total += len(new_allowlists)
        return metrics.allowlists_total(self._metric_allowlists_total)

    def _collect_allowlist_items(self, allowlists: list[Allowlist]) -> Metric:
        m = metrics.allowlist_items()
        for al in allowlists:
            for item in al.items:
                m.add_metric(item.metric_label_values(al.name), 1)
        return m

    def _collect_allowlist_items_total(self, allowlists: list[Allowlist]) -> Metric:
        allowlist_item_values_flat = [item.value for al in allowlists for item in al.items]
        new_allowlist_item_values = [item_value for item_value in allowlist_item_values_flat if item_value not in self._last_allowlist_items]
        self._metric_allowlist_items_total += len(new_allowlist_item_values)
        return metrics.allowlist_items_total(self._metric_allowlist_items_total)

    def _collect_allowlist_item_created(self, allowlists: list[Allowlist]) -> Metric:
        m = metrics.allowlist_item_created()
        for al in allowlists:
            for item in al.items:
                m.add_metric(item.created_metric_label_values(al.name), item.created_at.timestamp())
        return m

    def _collect_allowlist_item_expiration(self, allowlists: list[Allowlist]) -> Metric:
        m = metrics.allowlist_item_expiration()
        for al in allowlists:
            for item in al.items:
                m.add_metric(item.expiration_metric_label_values(al.name), item.expiration.timestamp())
        return m

    def _collect_alerts(self, alerts: list[Alert]) -> Metric:
        m = metrics.alerts()
        for a in alerts:
            m.add_metric(a.metric_label_values(), 1, a.created_at.timestamp())
        return m

    def _collect_alert_created(self, alerts: list[Alert]) -> Metric:
        m = metrics.alert_created()
        for a in alerts:
            m.add_metric(a.created_metric_label_values(), a.created_at.timestamp())
        return m

    def _collect_alert_start(self, alerts: list[Alert]) -> Metric:
        m = metrics.alert_start()
        for a in alerts:
            m.add_metric(a.start_metric_label_values(), a.start_at.timestamp())
        return m

    def _collect_alert_stop(self, alerts: list[Alert]) -> Metric:
        m = metrics.alert_stop()
        for a in alerts:
            m.add_metric(a.stop_metric_label_values(), a.stop_at.timestamp())
        return m

    def _collect_alert_events_count(self, alerts: list[Alert]) -> Metric:
        m = metrics.alert_events_count()
        for a in alerts:
            m.add_metric(a.events_count_metric_label_values(), a.events_count)
        return m

    def _collect_alert_decisions_count(self, alerts: list[Alert]) -> Metric:
        m = metrics.alert_decisions_count()
        for a in alerts:
            m.add_metric(a.decisions_count_metric_label_values(), len(a.decisions))
        return m

    def _collect_totals(self,
            decisions_totals: TotalCounterCollection,
            alerts_totals: TotalCounterCollection,
            events_totals: TotalCounterCollection
        ) -> Iterable[Metric]:
        yield decisions_totals.collect(metrics.decisions_total())
        yield alerts_totals.collect(metrics.alerts_total())
        yield events_totals.collect(metrics.events_total())

        yield decisions_totals.collect_grand_totals(metrics.decisions_grand_total())
        yield alerts_totals.collect_grand_totals(metrics.alerts_grand_total())
        yield events_totals.collect_grand_totals(metrics.events_count_grand_total())

    def _update_totals(self,
            alerts: list[Alert],
            alerts_totals: TotalCounterCollection,
            events_totals: TotalCounterCollection,
            decisions_totals: TotalCounterCollection,
            reset_at_start: bool = False
        ) -> None:

        # prune old counters to save memory
        for counter_collection in (alerts_totals, events_totals, decisions_totals):
            counter_collection.prune()

        for alert in alerts:
            label_values = alert.total_metric_label_values()
            grand_total_label_values = alert.grand_total_metric_label_values()
            alerts_totals.increment(label_values, grand_total_label_values, 1, reset_at_start)
            events_totals.increment(label_values, grand_total_label_values, alert.events_count, reset_at_start)
            for (decision_grand_total_label_values, count) in alert.decisions_grand_total_metric_label_values():
                decisions_totals.increment(label_values, decision_grand_total_label_values, count, reset_at_start)
