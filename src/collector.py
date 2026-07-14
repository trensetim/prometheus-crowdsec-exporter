from collections import defaultdict
import time
from typing import Iterable

from prometheus_client import Metric
from prometheus_client.metrics_core import CounterMetricFamily
from prometheus_client.registry import Collector

import requests

from src.config import Config
from src.logger import getLogger
import src.metrics as metrics
from src.models import (
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
        yield self._pollErrorsTotal

    def _collectDecisions(self) -> Iterable[Metric]:
        decisionsPollErrorsCounter = 0
        # create new metrics
        # cant use existing metrics cause it would append the new data
        activeDecisions = metrics.createActiveDecisions()
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

        # add metric
        labels = self._getDecisionLabels(decisions)
        for (dType, origin, scenario, scope), count in labels.items():
            activeDecisions.add_metric([dType, origin, scenario, scope], count)

        yield activeDecisions
        log.debug(
            "decisionsGaugeUpdated",
            labelCombinations = len(labels),
            total = sum(labels.values())
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
                value=d.value
            )
        return aggregated

def _buildSession(api_key: str) -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "X-Api-Key": api_key,
        "Accept": "application/json",
        "User-Agent": "prometheus-crowdsec-exporter",
    })
    return session

