from math import ceil
from typing import Sequence

from datetime import datetime, timezone
import requests

from config import Config
from logger import get_logger
from models import Alert, Allowlist

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

        log.info("machine_jwt_refreshed", {"expiry": self._machine_current_jwt_expiry.isoformat()})
        return self._machine_current_jwt

    def __str__(self):
        return f"_CrowdsecCredentials(machine_id={self._machine_id}, machine_password=***, machine_current_jwt=***, machine_current_jwt_expiry={self._machine_current_jwt_expiry.isoformat()})"

class CrowdsecPoller:
    """Abstracts away http api communication"""

    _http_client: _RawHttpClient
    _credentials: _CrowdsecCredentials
    _last_alert_created_at: datetime | None = None

    def __init__(self, config: Config) -> None:
        self._credentials = _CrowdsecCredentials(config.machine_id, config.machine_password)
        self._http_client = _RawHttpClient(
            base_url=config.local_api_url,
            timeout_seconds=config.http_timeout_seconds,
            default_headers={
                "Accept": "application/json",
                "User-Agent": f"prometheus-crowdsec-exporter/{config.version}",
            }
        )

        log.info("poller_initialised", {"http": self._http_client, "credentials": self._credentials})

    def _assert_jwt(self) -> str:
        return self._credentials.jwt(self._http_client)

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

        def since_to_ago(since: datetime, now: datetime = datetime.now(tz=timezone.utc)) -> str:
            diff = now - since
            seconds = ceil(diff.total_seconds())
            return str(seconds) + "s"

        def last_created_at(alerts: list[Alert]) -> datetime | None:
            if len(alerts) == 0:
                return None
            return max(a.created_at for a in alerts)

        ago: str | None = None
        alerts: list[Alert] = []
        if self._last_alert_created_at is not None:
            ago = since_to_ago(self._last_alert_created_at)

        while True:
            raw_batch = self._fetch("/v1/alerts" + query_params(ago))
            if raw_batch is None or len(raw_batch) == 0:
                break
            alerts += [Alert.parse(i) for i in (raw_batch or [])]
            since = last_created_at(alerts)
            ago = since_to_ago(since)

        next_last_created_at = last_created_at(alerts)
        if next_last_created_at is not None and self._last_alert_created_at is None:
            self._last_alert_created_at = next_last_created_at
        elif next_last_created_at is not None and self._last_alert_created_at is not None:
            self._last_alert_created_at = max(self._last_alert_created_at, next_last_created_at)

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
