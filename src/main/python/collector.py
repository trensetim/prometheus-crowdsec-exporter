from collections import defaultdict
from collections.abc import Callable
from typing import TypeVar
import time
from typing import Iterable

from prometheus_client import Metric
from prometheus_client.registry import Collector

import requests

from config import Config
from logger import get_logger
import metrics
from models import (
    Alert,
    Allowlist,
    Decision,
    parse_decisions,
    parse_allowlists,
    parse_alerts
)

log = get_logger(__name__)

_HTTP_TIMEOUT = (5.0, 10.0)

_EXPIRY_THRESHOLD_SECONDS = 86_400  # 24h

class CrowdSecCollector(Collector):

    _session: requests.Session
    _config_version: str

    # parsed responses from the last poll
    _decisions: list[Decision] = []
    _allowlists: list[Allowlist] = []
    _alerts: list[Alert] = []

    _last_decision_ids: set[str] = set()
    """UUIDs of the decisions of last poll, to prevent double-counting"""
    _last_allowlist_ids: set[str] = set()
    """IDs of the allowlists of last poll, to prevent double-counting"""
    _last_allowlist_items: set[str] = set()
    """Values of the allowlist items of last poll, to prevent double-counting (across all allowlists)"""

    _metric_polls_total: int = 0
    _metric_poll_errors_total: int = 0
    _metric_last_poll_duration_seconds: float = 0
    _metric_decisions_total: int = 0
    _metric_allowlists_total: int = 0
    _metric_allowlist_items_total: int = 0

    def __init__(self, config: Config) -> None:
        self._session = _open_session(config.apiKey, config.version)
        self._base_url = config.crowdSecLapiURL.rstrip("/")
        self._config_version = config.version
        self._alertsFetchedCounter = 0
        log.info("collector_initialised", lapi_url=self._base_url)

    def collect(self) -> Iterable[Metric]:
        self.poll()

        yield metrics.exporter_info(self._config_version)
        yield metrics.polls_total(self._metric_polls_total)
        yield metrics.poll_errors_total(self._metric_poll_errors_total)
        yield metrics.last_poll_duration_seconds(self._metric_last_poll_duration_seconds)

        yield self._collect_decisions()
        yield self._collect_decisions_total()
        yield self._collect_allowlists()
        yield self._collect_allowlists_total()
        yield self._collect_allowlist_created()
        yield self._collect_allowlist_updated()
        yield self._collect_allowlist_console_managed()
        yield self._collect_allowlist_items()
        yield self._collect_allowlist_items_total()
        yield self._collect_allowlist_item_created()
        yield self._collect_allowlist_item_expiration()
        yield from self._collectAlerts()


    def poll(self):
        """
        Connects with the CrowdSec LAPI and fetches+parses the relevant data.
        Errors are logged and turned into a ..._poll_errors_total metric.
        """
        self._metric_polls_total += 1

        start = time.monotonic()

        T = TypeVar("T")
        def _poll_single_endpoint(endpoint: str, parser: Callable[[list[any]], list[T]]) -> list[T]:
            raw = self._fetch(endpoint, f"/v1/{endpoint}")
            if raw is None:
                raise requests.exceptions.ConnectionError(f"No {endpoint} returned from LAPI")
            return parser(raw)

        try:
            self._allowlists = _poll_single_endpoint("allowlists", parse_allowlists)
            self._decisions = _poll_single_endpoint("decisions", parse_decisions)
            self._alerts = _poll_single_endpoint("alerts", parse_alerts)
        except Exception as err: # pylint: disable=broad-exception-caught
            log.warning("pollFailed", error = err)
            self._metric_poll_errors_total += 1

        end = time.monotonic()
        self._metric_last_poll_duration_seconds = round(end - start, 3)
        log.info("pollSuccess",
            countAllowlists = len(self._allowlists),
            countDecisions = len(self._decisions),
            countAlerts = len(self._alerts),
            durationSeconds = self._metric_last_poll_duration_seconds
        )

    def _collect_decisions(self) -> Metric:
        decisions = metrics.decisions()
        for d in self._decisions:
            decisions.add_metric(d.metric_label_values(), 1)
        return decisions

    def _collect_decisions_total(self) -> Metric:
        new_decisions = [d for d in self._decisions if d.uuid not in self._last_decision_ids]
        self._metric_decisions_total += len(new_decisions)
        self._last_decision_ids = {d.uuid for d in self._decisions}
        return metrics.decisions_total(self._metric_decisions_total)

    def _collect_allowlists(self) -> Metric:
        allowlists = metrics.allowlists()
        for al in self._allowlists:
            allowlists.add_metric(al.metric_label_values(), 1)
        return allowlists

    def _collect_allowlist_created(self) -> Metric:
        m = metrics.allowlist_created()
        for al in self._allowlists:
            m.add_metric(al.created_metrics_label_values(), al.created_at.timestamp())
        return m

    def _collect_allowlist_updated(self) -> Metric:
        m = metrics.allowlist_updated()
        for al in self._allowlists:
            m.add_metric(al.updated_metrics_label_values(), al.updated_at.timestamp())
        return m

    def _collect_allowlist_console_managed(self) -> Metric:
        m = metrics.allowlist_console_managed()
        for al in self._allowlists:
            m.add_metric(al.console_managed_metrics_label_values(), 1 if al.console_managed else 0)
        return m

    def _collect_allowlists_total(self) -> Metric:
        new_allowlists = [al for al in self._allowlists if al.id not in self._last_allowlist_ids]
        self._metric_allowlists_total += len(new_allowlists)
        self._last_allowlist_ids = {al.id for al in self._allowlists}
        return metrics.allowlists_total(self._metric_allowlists_total)

    def _collect_allowlist_items(self) -> Metric:
        allowlist_items = metrics.allowlist_items()
        for al in self._allowlists:
            for item in al.items:
                allowlist_items.add_metric(item.metric_label_values(al.id), 1)
        return allowlist_items

    def _collect_allowlist_items_total(self) -> Metric:
        allowlist_item_values_flat = [item.value for al in self._allowlists for item in al.items]
        new_allowlist_item_values = [item_value for item_value in allowlist_item_values_flat if item_value not in self._last_allowlist_items]
        self._metric_allowlist_items_total += len(new_allowlist_item_values)
        self._last_allowlist_items = allowlist_item_values_flat
        return metrics.allowlist_items_total(self._metric_allowlist_items_total)

    def _collect_allowlist_item_created(self) -> Metric:
        allowlist_items = metrics.allowlist_item_created()
        for al in self._allowlists:
            for item in al.items:
                allowlist_items.add_metric(item.created_metric_label_values(al.id), item.created_at.timestamp())
        return allowlist_items

    def _collect_allowlist_item_expiration(self) -> Metric:
        allowlist_items = metrics.allowlist_item_expiration()
        for al in self._allowlists:
            for item in al.items:
                allowlist_items.add_metric(item.expiration_metric_label_values(al.id), item.expiration.timestamp())
        return allowlist_items

    def _collectAlerts(self) -> Iterable[Metric]:
        # create new metrics
        # cant use existing metrics cause it would append the new data
        activeAlerts = metrics.createActiveAlerts()
        activeAlertsDetails = metrics.createActiveAlertsDetails()
        alertsFetchedTotal = metrics.createAlertsFetchedTotal()

        self._alertsFetchedCounter += len(self._alerts)
        alertsFetchedTotal.add_metric([], self._alertsFetchedCounter )
        yield alertsFetchedTotal

        # add metric
        labels = self._getAlertsLabels(self._alerts)
        for (scenario, simulated, remediation), count in labels.items():
            activeAlerts.add_metric([scenario, simulated, remediation], count)

        yield activeAlerts
        log.debug(
            "alertsGaugeUpdated",
            labelCombinations = len(labels),
            total = sum(labels.values())
        )

        details = self._getAlertsDetails(self._alerts)
        for (alertId,uuid,machineId,createdAt,startAt,stopAt,scenario,scenarioHash,scenarioVersion,eventsCount,simulated,remediation,ip,subnet,country,asNumber,asName,latitude,longitude,decisionType,decisionScope), count in details.items():
            activeAlertsDetails.add_metric([
                alertId,
                uuid,
                machineId,
                createdAt,
                startAt,
                stopAt,
                scenario,
                scenarioHash,
                scenarioVersion,
                eventsCount,
                simulated,
                remediation,
                ip,
                subnet,
                country,
                asNumber,
                asName,
                latitude,
                longitude,
                decisionType,
                decisionScope
                ],
                count
            )

        yield activeAlertsDetails
        log.debug(
            "alertsDetailsGaugeUpdated",
            labelCombinations = len(details),
            total = sum(details.values())
        )

    def _getAlertsLabels(self, alerts: list[Alert]) -> dict[tuple, int]:
        aggregated: dict[tuple, int] = defaultdict(int)
        for a in alerts:
            aggregated[tuple(a.metricLabels().values())] += 1
            log.debug(
                "alertsObserved",
                **a.metricLabels(),
                alertId = a.id
            )
        return aggregated

    def _getAlertsDetails(self, alerts: list[Alert]) -> dict[tuple, int]:
        aggregated: dict[tuple, int] = defaultdict(int)
        for a in alerts:
            aggregated[tuple(a.metricDetails().values())] += 1
            log.debug(
                "alertsDetailsObserved",
                **a.metricDetails(),
                alertId = a.id
            )
        return aggregated

    def _fetch(self, endpoint: str, path: str) -> list:
        try:
            response = self._session.get(f"{self._base_url}{path}", timeout = _HTTP_TIMEOUT)

            if response.status_code == 204: # No Content
                log.debug("pollEmpty", endpoint = endpoint)
                return []

            response.raise_for_status()
            data = response.json()

            if not isinstance(data, list):
                raise ValueError(f"Expected list from {path}, got {type(data).__name__}")

            return data
        except requests.exceptions.ConnectionError as exc:
            log.warning("pollFailed", endpoint = endpoint, error_type = "connect", detail = str(exc))
            raise
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "unknown"
            log.warning("pollFailed", endpoint = endpoint, error_type = "http", http_status = status, detail = str(exc))
            raise
        except (ValueError, KeyError) as exc:
            log.warning("pollFailed", endpoint = endpoint, error_type = "parse", detail = str(exc))
            raise

def _open_session(api_key: str, version: str) -> requests.Session:
    """Creates an http session object with adequate headers for polling the CrowdSec LAPI."""
    session = requests.Session()
    session.headers.update({
        "X-Api-Key": api_key,
        "Accept": "application/json",
        "User-Agent": f"prometheus-crowdsec-exporter/{version}",
    })
    return session
