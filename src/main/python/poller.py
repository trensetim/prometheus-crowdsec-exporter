from math import ceil
import sys
from typing import Callable, Sequence

from collections import OrderedDict
from datetime import datetime, timezone
import requests
import time

from config import Config
from logger import get_logger
from models import Alert, AlertIdentityKey, Allowlist

log = get_logger(__name__)

class _RawHttpClient:
    _session: requests.Session
    _base_url: str
    _timeout_seconds: float
    _default_headers: dict[str, str]

    def __init__(self, base_url: str, timeout_seconds: float, default_headers: dict[str, str]) -> None:
        self._base_url = base_url.rstrip('/')
        self._timeout_seconds = timeout_seconds
        self._default_headers = default_headers
        self._session = requests.Session()
        self._default_headers = default_headers

    def post(self, path: str, json: dict[str, any], headers: dict[str, str] | None = None) -> requests.Response:
        if headers is None:
            headers = {}
        while path.startswith("/"):
            path = path[1:]
        return self._session.post(
            url=f"{self._base_url}/{path}",
            json=json,
            headers={**self._default_headers, **headers},
            timeout=self._timeout_seconds
        )

    def get(self, path: str, headers: dict[str, str] | None = None) -> requests.Response:
        if headers is None:
            headers = {}
        while path.startswith("/"):
            path = path[1:]
        return self._session.get(
            url=f"{self._base_url}/{path}",
            headers={**self._default_headers, **headers},
            timeout=self._timeout_seconds
        )

    def __str__(self):
        return f"_RawHttpClient(base_url={self._base_url}, timeout_seconds={self._timeout_seconds}, default_headers={self._default_headers})"

# pylint: disable=too-few-public-methods
class _CrowdsecCredentials:
    _machine_id: str
    _machine_password: str
    _machine_current_jwt: str
    _machine_current_jwt_expiry: datetime
    def __init__(self, machine_id: str, machine_password: str) -> None:
        self._machine_id = machine_id
        self._machine_password = machine_password
        self._machine_current_jwt = ""
        self._machine_current_jwt_expiry = datetime.fromtimestamp(0, tz=timezone.utc)

    def jwt(self, http: _RawHttpClient) -> str:
        """Refreshes the JWT for the machine session"""
        if self._machine_current_jwt != "" and self._machine_current_jwt_expiry > datetime.now(tz=timezone.utc):
            return self._machine_current_jwt

        response = http.post(
            "v1/watchers/login",
            json={"machine_id": self._machine_id, "password": self._machine_password}
        )
        response.raise_for_status()
        self._machine_current_jwt = response.json()["token"]
        self._machine_current_jwt_expiry = datetime.fromisoformat(response.json()["expire"])

        log.info("machine_jwt_refreshed", expiry = self._machine_current_jwt_expiry.isoformat())
        return self._machine_current_jwt

    def __str__(self):
        return f"_CrowdsecCredentials(machine_id={self._machine_id}, machine_password=***, machine_current_jwt=***, machine_current_jwt_expiry={self._machine_current_jwt_expiry.isoformat()})"

class AlertDeduplicator:
    """
    Suppresses duplicate alerts seen across polls and pagination batches.

    Keeps a bounded, insertion-ordered set of recently-seen alert identities (an LRU):
    membership is O(1) and, once `capacity` is exceeded, the oldest identity is evicted.
    This is capacity-based rather than time-based, so deduplication does not depend on
    wall-clock timestamps.

    `capacity` must comfortably exceed the number of alerts re-fetched across the poll(s)
    before the `since`-watermark advances past them (ie. at least a few times the LAPI
    batch size); otherwise an identity could be evicted while still being re-fetched and
    thus be counted twice.

    `process` stages changes into an uncommitted working copy. Call `commit` after a poll
    fully succeeds, or `rollback` to discard a partial poll's state (eg. after an error).
    """
    _capacity: int
    _seen_alerts: "OrderedDict[AlertIdentityKey, None]"
    _uncommitted: "OrderedDict[AlertIdentityKey, None]"
    _parse_func: Callable[[dict], Alert | None]

    def __init__(self,
            capacity: int = 50_000,
            parse_func: Callable[[dict], Alert | None] = lambda raw_alert: Alert.parse(raw_alert, None)
        ) -> None:
        self._capacity = capacity
        self._parse_func = parse_func
        self._seen_alerts = OrderedDict()
        self._uncommitted = OrderedDict()

    def process(self, raw_alert: dict) -> Alert | None:
        key = AlertIdentityKey.parse(raw_alert)
        if key is None:
            # no identity -> cannot deduplicate, always emit (and never store)
            return self._parse_func(raw_alert)
        if key in self._uncommitted:
            self._uncommitted.move_to_end(key) # keep actively re-fetched keys warm (LRU)
            return None
        alert = self._parse_func(raw_alert)
        if alert is not None:
            self._uncommitted[key] = None
            if len(self._uncommitted) > self._capacity:
                self._uncommitted.popitem(last=False) # evict the oldest identity
        return alert

    def commit(self) -> None:
        self._seen_alerts = OrderedDict(self._uncommitted)

    def rollback(self) -> None:
        self._uncommitted = OrderedDict(self._seen_alerts)

class CrowdsecPoller:
    """Abstracts away http api communication"""

    _http_client: _RawHttpClient
    _credentials: _CrowdsecCredentials
    _last_alert_created_at: datetime | None = None
    _deduplicator: AlertDeduplicator
    _batch_size: int

    def __init__(self, config: Config) -> None:
        self._credentials = _CrowdsecCredentials(config.machine_id, config.machine_password)
        self._http_client = _RawHttpClient(
            base_url=config.lapi_url,
            timeout_seconds=config.http_timeout_seconds,
            default_headers={
                "Accept": "application/json",
                "User-Agent": f"prometheus-crowdsec-exporter/{config.version}",
            }
        )

        self._deduplicator = AlertDeduplicator(
            capacity=config.alert_dedup_window_size,
            parse_func=lambda raw_alert: Alert.parse(raw_alert, config.scenario_rewriter)
        )
        self._batch_size = config.batch_size

        log.info("poller_initialised", http=str(self._http_client), credentials=str(self._credentials))

    def _assert_jwt(self) -> str:
        return self._credentials.jwt(self._http_client)

    def beat_the_heart(self) -> None:
        jwt = self._assert_jwt()
        response = self._http_client.get(
            "/v1/heartbeat",
            headers={"Authorization": f"Bearer {jwt}"},
        )
        response.raise_for_status()

    def poll_allowlists(self) -> list:
        # https://www.reddit.com/r/CrowdSec/comments/1rj3459/allowlist_items_not_appearing_on_lapi_response/
        # the `with_content=true` query param is not yet documented on https://crowdsecurity.github.io/api_doc/#/watchers/getAllowlists
        raw_list = self._fetch("/v1/allowlists?with_content=true")
        allowlists = [Allowlist.parse(i) for i in raw_list]
        return allowlists

    def poll_alerts(self) -> Sequence[Alert]:
        def query_params(ago: str | None = None, limit: int = 1000) -> str:
            params = f"?limit={limit}"
            params += "&sort=ASC" # automatically sorts by created_at: see https://github.com/crowdsecurity/crowdsec/blob/d3b1c0ba8c19384a72c30fc83f80161329baeb21/pkg/database/alerts.go#L850
            if ago is not None:
                params += f"&since={ago}"
            return params

        def since_to_ago(since: datetime, now: datetime | None = None) -> str:
            now = now or datetime.now(tz=timezone.utc)
            diff = now - since
            seconds = max(1, ceil(diff.total_seconds()))
            return str(seconds) + "s"

        def last_created_at(alerts: list[Alert]) -> datetime | None:
            if len(alerts) == 0:
                return None
            return max(a.created_at for a in alerts)

        ago: str | None = None
        alerts: list[Alert] = []
        if self._last_alert_created_at is not None:
            ago = since_to_ago(self._last_alert_created_at, None)

        self._deduplicator.rollback()
        safe_max_batch_count = 100 # firing off more http requests per poll seems broken
        batch_size = self._batch_size
        for batch_no in range(safe_max_batch_count + 1):
            raw_batch = self._fetch("/v1/alerts" + query_params(ago, batch_size))
            reached_end = len(raw_batch) < batch_size

            raw_batch = [s for a in (raw_batch or []) if (s:=self._deduplicator.process(a)) is not None]
            alerts += raw_batch

            if reached_end:
                break # stop early: next batch will not yield any more results

            if len(raw_batch) == 0:
                # Received a full page of duplicates: widen window to try progressing.
                # This may lead to being OOM-Killed: acceptable.
                #   - We assume that the server generates the response in a streaming fashion.
                #     A request for "infinite data" should not overwhelm the server, if it accepts it.
                #     So we assume we are safe to request such.
                #   - We cannot easily predict the actual memory usage of the response: any single alert may have
                #     unpredictably many decisions inside it. (eg. many thousands for CAPI-poll-alerts).
                #     Thus, we do not even try to limit the batch size. If we dont have enough memory to hold it,
                #     we better die on OOM to highlight that failure condition.
                #   - That this even happens is ultra-rare: it requires receiving a a big multiple of full pages of duplicates
                #     (ie. many tens of thousands with realisitic config).

                # Possible optimization: Instead of doing `parseJson(httpbody)` for the entire response, we
                #    can request a streaming response and sequentially parse each element of the contained JSON-Array and
                #    return a generator of parsed, raw JSON-Objects (containing the alerts).
                #    This would sidestep the entire pagination problem, yet requires using a streaming JSON parser.
                #    Maybe https://pypi.org/project/json-stream/ can do.
                #    Implementing this idea is postponed until proven necessary.

                batch_size *= 2
                continue

            since = last_created_at(alerts)
            ago = since_to_ago(since, None)

            if batch_no > 5:
                # ease off the load during huge polls (eg. startup)
                time.sleep(0.5 + max(batch_no * 0.1, 1))

            if batch_no >= safe_max_batch_count:
                log.warning("poll_alerts_max_batch_count_reached", max_batch_count = safe_max_batch_count)
                # this realistically never happens: we have probably a broken LAPI. Better we slow down as much as possible to avoid hammering the LAPI in a CrashLoop
                time.sleep(10)
                sys.exit(1) # better we die and enter a CrashLoopBackoff, than accepting the next scrape and continue hammering

        next_last_created_at = last_created_at(alerts)
        if next_last_created_at is not None and self._last_alert_created_at is None:
            self._last_alert_created_at = next_last_created_at
        elif next_last_created_at is not None and self._last_alert_created_at is not None:
            self._last_alert_created_at = max(self._last_alert_created_at, next_last_created_at)

        self._deduplicator.commit()
        return alerts

    def _fetch(self, path: str) -> any:
        try:
            jwt = self._assert_jwt()
            response = self._http_client.get(
                path,
                headers={"Authorization": f"Bearer {jwt}"},
            )

            if response.status_code == 204: # No Content
                return []

            response.raise_for_status()
            data = response.json()

            return data
        except requests.exceptions.ConnectionError as exc:
            log.warning("poll_failed", path = path, error_type = "connect", detail = str(exc))
            raise
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "unknown"
            log.warning("poll_failed", path = path, error_type = "http", http_status = status, detail = str(exc))
            raise
        except (ValueError, KeyError) as exc:
            log.warning("poll_failed", path = path, error_type = "parse", detail = str(exc))
            raise
