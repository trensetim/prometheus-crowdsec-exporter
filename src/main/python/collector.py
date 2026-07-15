from collections import defaultdict
import time
from typing import Iterable

from prometheus_client import Metric
from prometheus_client.registry import Collector

import requests

from config import Config
from logger import getLogger
import metrics as metrics
from models import (
    Alert,
    Decision,
    parseDecisions,
    parseAllowlists,
    parseAlerts
)

log = getLogger(__name__)

_DECISIONS_PATH  = "/v1/decisions"
_ALERTS_PATH     = "/v1/alerts"
_ALLOWLISTS_PATH = "/v1/allowlists"

_HTTP_TIMEOUT = (5.0, 10.0)

_EXPIRY_THRESHOLD_SECONDS = 86_400  # 24h

class CrowdSecCollector(Collector):
    def __init__(self, config: Config) -> None:
        self._config = config
        self._session = _buildSession(config.apiKey)
        self._base_url = config.crowdSecLapiURL.rstrip("/")
        self._decisionsFetchedCounter = 0
        self._allowlistsFetchedCounter = 0
        self._alertsFetchedCounter = 0
        self._pollErrorsTotal = metrics.createPollErrorsTotal()
        log.info(
            "collector_initialised",
            lapi_url=self._base_url
        )

    def collect(self) -> Iterable[Metric]:
        self._pollErrorsTotal = metrics.createPollErrorsTotal()
        yield metrics.createExporterInfo()

        yield from self._collectDecisions()
        yield from self._collectAllowlists()
        yield from self._collectAlerts()
        yield self._pollErrorsTotal

    def _collectDecisions(self) -> Iterable[Metric]:
        decisionsPollErrorsCounter = 0
        # create new metrics
        # cant use existing metrics cause it would append the new data
        activeDecisions = metrics.createActiveDecisions()
        activeDecisionsDetails = metrics.createActiveDecisionsDetails()
        decisionsFetchedTotal = metrics.createDecisionsFetchedTotal()
        lastSuccessfulDecisionsPollTimestamp = metrics.createLastSuccessfulDecisionPollTimestamp()
        decisionsPollErrorsTotal = metrics.createDecisionPollErrorsTotal()

        # fetch decisions from LAPI
        endpoint = "decisions"
        t = time.monotonic()

        try:
            raw = self._fetch(endpoint, _DECISIONS_PATH)
        except requests.exceptions.ConnectionError:
            self._pollErrorsTotal.add_metric([endpoint, "connectionError"], 1)
            return

        if raw is None:
            return

        # parse data
        decisions, skipped = parseDecisions(raw)

        # check for parse errors and in case of errors send metric
        if skipped:
            decisionsPollErrorsCounter = skipped
            decisionsPollErrorsTotal.add_metric([endpoint, "parseError"], decisionsPollErrorsCounter)
            yield decisionsPollErrorsTotal

        self._decisionsFetchedCounter += len(decisions)
        decisionsFetchedTotal.add_metric([], self._decisionsFetchedCounter )
        yield decisionsFetchedTotal

        # add metrics
        labels = self._getDecisionLabels(decisions)
        for (dType, origin, scenario, scope), count in labels.items():
            activeDecisions.add_metric([dType, origin, scenario, scope], count)

        yield activeDecisions

        log.debug(
            "activeDecisionsGaugeUpdated",
            labelCombinations = len(labels),
            total = sum(labels.values())
        )

        details = self._getDecisionDetails(decisions)
        for (dType, origin, scenario, scope, val, decisionId, uuid, duration, until, simulated), count in details.items():
            activeDecisionsDetails.add_metric([dType, origin, scenario, scope, val, decisionId, uuid, duration, until, simulated], count)

        yield activeDecisionsDetails

        log.debug(
            "activeDecisionsDetailsGaugeUpdated",
            labelCombinations = len(details),
            total = sum(details.values())
        )


        elapsed = time.monotonic() - t
        lastSuccessfulDecisionsPollTimestamp.add_metric([endpoint], time.time())
        yield lastSuccessfulDecisionsPollTimestamp
        log.info(
            "pollSuccess",
            endpoint = endpoint,
            count = len(decisions),
            durationSeconds = round(elapsed, 3)
        )

    def _getDecisionLabels(self, decisions: list[Decision]) -> dict[tuple, int]:
        aggregated: dict[tuple, int] = defaultdict(int)
        for d in decisions:
            aggregated[tuple(d.metricLabels().values())] += 1
            log.debug(
                "decision_observed",
                **d.metricLabels(),
                value = d.value
            )
        return aggregated

    def _getDecisionDetails(self, decisions: list[Decision]) -> dict[tuple, int]:
        aggregated: dict[tuple, int] = defaultdict(int)
        for d in decisions:
            aggregated[tuple(d.metricDetails().values())] += 1
            log.debug(
                "decision_details_observed",
                **d.metricDetails(),
                value = d.value
            )
        return aggregated

    def _collectAllowlists(self) -> Iterable[Metric]:
        allowlistsPollErrorsCounter = 0
        # create new metrics
        # cant use existing metrics cause it would append the new data
        activeAllowlists = metrics.createActiveAllowlists()
        activeAllowlistItems = metrics.createAllowlistItems()
        expiringItems = metrics.createAllowlistsExpiringItems()
        allowlistsFetchedTotal = metrics.createAllowlistsFetchedTotal()
        lastSuccessfulAllowlistsPollTimestamp = metrics.createLastSuccessfulAllowlistsPollTimestamp()
        allowlistsPollErrorsTotal = metrics.createAllowlistsPollErrorsTotal()

        # fetch decisions from LAPI
        endpoint = "allowlists"
        t = time.monotonic()

        try:
            raw = self._fetch(endpoint, _ALLOWLISTS_PATH)
        except requests.exceptions.ConnectionError:
            self._pollErrorsTotal.add_metric([endpoint, "connectionError"], 1)
            return

        if raw is None:
            return

        # parse data
        allowlists, skipped = parseAllowlists(raw)

        # check for parse errors and in case of errors send metric
        if skipped:
            allowlistsPollErrorsCounter = skipped
            allowlistsPollErrorsTotal.add_metric([endpoint, "parseError"], allowlistsPollErrorsCounter)
            yield allowlistsPollErrorsTotal

        self._allowlistsFetchedCounter += len(allowlists)
        allowlistsFetchedTotal.add_metric([], self._allowlistsFetchedCounter )
        yield allowlistsFetchedTotal

        # add metric
        for al in allowlists:
            labels = list(al.metricLabels().values())
            activeAllowlists.add_metric(labels, al.countActive())
            expiringItems.add_metric(labels, al.countExpiringWithin(_EXPIRY_THRESHOLD_SECONDS))

            for item in al.metricItems():
                activeAllowlistItems.add_metric(
                    [
                        item["allowlistId"],
                        item["name"],
                        item["value"],
                        item["description"],
                        item["expiration"],
                        item["isExpired"],
                    ],
                    1.0   # Gauge-Wert is always 1
                )

        yield activeAllowlists
        yield activeAllowlistItems
        yield expiringItems

        log.debug(
            "allowlistsGaugeUpdated",
            total = len(allowlists)
        )

        elapsed = time.monotonic() - t
        lastSuccessfulAllowlistsPollTimestamp.add_metric([endpoint], time.time())
        yield lastSuccessfulAllowlistsPollTimestamp
        log.info(
            "pollSuccess",
            endpoint = endpoint,
            count = len(allowlists),
            durationSeconds = round(elapsed, 3)
        )

    def _collectAlerts(self) -> Iterable[Metric]:
        alertsPollErrorsCounter = 0
        # create new metrics
        # cant use existing metrics cause it would append the new data
        activeAlerts = metrics.createActiveAlerts()
        activeAlertsDetails = metrics.createActiveAlertsDetails()
        alertsFetchedTotal = metrics.createAlertsFetchedTotal()
        lastSuccessfulAlertsPollTimestamp = metrics.createLastSuccessfulAlertsPollTimestamp()
        alertsPollErrorsTotal = metrics.createAlertsPollErrorsTotal()

        # fetch decisions from LAPI
        endpoint = "alerts"
        t = time.monotonic()

        try:
            raw = self._fetch(endpoint, _ALERTS_PATH)
        except requests.exceptions.ConnectionError:
            self._pollErrorsTotal.add_metric([endpoint, "connectionError"], 1)
            return

        if raw is None:
            return

        # parse data
        alerts, skipped = parseAlerts(raw)

        # check for parse errors and in case of errors send metric
        if skipped:
            alertsPollErrorsCounter = skipped
            alertsPollErrorsTotal.add_metric([endpoint, "parseError"], alertsPollErrorsCounter)
            yield alertsPollErrorsTotal

        self._alertsFetchedCounter += len(alerts)
        alertsFetchedTotal.add_metric([], self._alertsFetchedCounter )
        yield alertsFetchedTotal

        # add metric
        labels = self._getAlertsLabels(alerts)
        for (scenario, simulated, remediation), count in labels.items():
            activeAlerts.add_metric([scenario, simulated, remediation], count)

        yield activeAlerts
        log.debug(
            "alertsGaugeUpdated",
            labelCombinations = len(labels),
            total = sum(labels.values())
        )

        details = self._getAlertsDetails(alerts)
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

        elapsed = time.monotonic() - t
        lastSuccessfulAlertsPollTimestamp.add_metric([endpoint], time.time())
        yield lastSuccessfulAlertsPollTimestamp
        log.info(
            "pollSuccess",
            endpoint = endpoint,
            count = len(alerts),
            durationSeconds = round(elapsed, 3)
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

    def _fetch(self, endpoint: str, path: str, params: dict | None = None) -> list | None:
        url = f"{self._base_url}{path}"
        log.debug(
            "pollStart",
            endpoint=endpoint
        )
        try:
            response = self._session.get(url, params = params, timeout = _HTTP_TIMEOUT)

            if response.status_code == 204:
                log.debug(
                    "pollEmpty",
                    endpoint=endpoint
                )
                return []

            response.raise_for_status()
            data = response.json()

            if not isinstance(data, list):
                raise ValueError(
                    f"Expected list from {path}, got {type(data).__name__}"
                )
            return data

        except requests.exceptions.ConnectionError as exc:
            log.error(
                "pollFailed",
                endpoint = endpoint,
                error_type = "connectionError",
                detail = str(exc)
            )
            raise
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "unknown"
            log.error(
                "pollFailed",
                endpoint = endpoint,
                error_type="httpError",
                http_status=status,
                detail=str(exc)
            )
            raise
        except (ValueError, KeyError) as exc:
            log.error(
                "pollFailed",
                endpoint = endpoint,
                error_type = "parseError",
                detail = str(exc)
            )
            raise

def _buildSession(api_key: str) -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "X-Api-Key": api_key,
        "Accept": "application/json",
        "User-Agent": "prometheus-crowdsec-exporter",
    })
    return session

