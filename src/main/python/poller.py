from typing import Literal
from datetime import datetime, timezone
import requests
from config import Config
from logger import get_logger
from models import Alert, Allowlist, Decision

log = get_logger(__name__)

type _CrowdsecPollEndpoint = Literal["decisions", "alerts", "allowlists"]

class CrowdsecPoller:
    """Abstracts away http api communication"""

    _session: requests.Session

    _lapi_url: str
    _timeout_seconds: float
    _bouncer_api_key: str
    _machine_id: str
    _machine_password: str
    _machine_current_jwt: str
    _machine_current_jwt_expiry: datetime
    _default_headers: dict[str, str]

    def __init__(self, config: Config) -> None:
        self._bouncer_api_key = config.bouncer_api_key
        self._machine_id = config.machine_id
        self._machine_password = config.machine_password
        self._machine_current_jwt = ""
        self._lapi_url = config.local_api_url.rstrip('/')
        self._default_headers = {
            "Accept": "application/json",
            "User-Agent": f"prometheus-crowdsec-exporter/{config.version}",
        }
        self._timeout_seconds = config.http_timeout_seconds
        self._session = requests.Session()
        self._session.headers.update({**self._default_headers})

        self._assert_jwt()

        log.info("poller_initialised", lapi_url=self._lapi_url, timeout_seconds=self._timeout_seconds)


    def _assert_jwt(self) -> None:
        """Refreshes the JWT for the machine session"""

        if self._machine_current_jwt != "" and self._machine_current_jwt_expiry > datetime.now(tz=timezone.utc):
            return

        response = requests.post(
            f"{self._lapi_url}/v1/watchers/login",
            json={"machine_id": self._machine_id, "password": self._machine_password},
            headers={**self._default_headers},
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        self._machine_current_jwt = response.json()["token"]
        self._machine_current_jwt_expiry = datetime.fromisoformat(response.json()["expire"])

        log.info("machine_jwt_refreshed", {"expiry": self._machine_current_jwt_expiry.isoformat()})

    def poll_allowlists(self) -> list:
        raw_list = self._fetch("allowlists", "/v1/allowlists")
        return [Allowlist.parse(i) for i in raw_list]

    def poll_decisions(self) -> list:
        raw_list = self._fetch("decisions", "/v1/decisions")
        return [Decision.parse(i) for i in raw_list]

    def poll_alerts(self) -> list:
        raw_list = self._fetch("alerts", "/v1/alerts") # TODO: add filter since last poll, add limit=unlimited
        return [Alert.parse(i) for i in raw_list]

    def _headers_for_endpoint(self, endpoint: _CrowdsecPollEndpoint) -> dict[str, str]:
        if endpoint in ["decisions"]:
            return {**self._default_headers, "X-Api-Key": self._bouncer_api_key}
        elif endpoint in ["alerts", "allowlists"]:
            self._assert_jwt()
            return {**self._default_headers, "Authorization": f"Bearer {self._machine_current_jwt}"}
        else:
            raise ValueError(f"Unknown endpoint: {endpoint}")

    def _fetch(self, endpoint: _CrowdsecPollEndpoint, path: str) -> list:
        try:
            response = self._session.get(
                f"{self._lapi_url}{path}",
                headers=self._headers_for_endpoint(endpoint),
                timeout=self._timeout_seconds
            )

            if response.status_code == 204: # No Content
                log.debug("poll_empty", endpoint = endpoint)
                return []

            response.raise_for_status()
            data = response.json()

            if not isinstance(data, list):
                raise ValueError(f"Expected list from {path}, got {type(data).__name__}")

            return data
        except requests.exceptions.ConnectionError as exc:
            log.warning("poll_failed", endpoint = endpoint, error_type = "connect", detail = str(exc))
            raise
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "unknown"
            log.warning("poll_failed", endpoint = endpoint, error_type = "http", http_status = status, detail = str(exc))
            raise
        except (ValueError, KeyError) as exc:
            log.warning("poll_failed", endpoint = endpoint, error_type = "parse", detail = str(exc))
            raise
