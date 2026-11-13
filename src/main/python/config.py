import os
import base64
from dataclasses import dataclass
from datetime import timedelta
from typing import Literal

from inotify_simple import INotify, flags

from scenario import ScenarioRewriter

def _read_required_env(key: str) -> str:
    value = os.getenv(key)
    if not value or value == "":
        raise ValueError(f"Required environment variable '{key}' is not set or empty.")
    return value

def _read_bind_port() -> int:
    """Reads the bind port from the environment variable BIND_PORT, or returns the default value of 8000 if not set"""
    try:
        return int(os.getenv("BIND_PORT", "8000"))
    except ValueError as exc:
        raise ValueError("Environment variable 'BIND_PORT' must be an integer") from exc

def _read_version() -> str:
    """Assumes a version.txt file is present in the same directory as this script"""
    return _read_file_content("version.txt")

def _read_file_content(file_path: str) -> str:
    """Reads the content of a file and returns it as a string"""
    if not file_path.startswith("/"):
        script_path = os.path.realpath(__file__)
        script_dir = os.path.dirname(script_path)
        file_path = os.path.join(script_dir, file_path)
    with open(file_path, "r", encoding="utf-8") as file:
        return file.read().strip()

@dataclass
class TlsConfig:
    """TLS configuration for the server. The paths must point to PEM-encoded files."""
    _cert_file_path: str
    _key_file_path: str
    _key_password: str | None
    # TODO: maybe allow client cert validation as well, for X509-based authentication

    def get_cert_file_path(self) -> str:
        return self._cert_file_path

    def get_key_file_path(self) -> str:
        return self._key_file_path

    def consume_key_password(self) -> str | None:
        # we dont want to hold it in memory longer than necessary, so we drop the value as early as possible
        password = self._key_password
        self._key_password = None
        return password

    def register_inotify(self) -> INotify:
        """Registers a watcher for changes in the directory of the certificate and key files."""
        dirs = {os.path.dirname(self._cert_file_path), os.path.dirname(self._key_file_path)}
        inotify = INotify()
        for d in dirs:
            inotify.add_watch(d, flags.CREATE | flags.DELETE | flags.MODIFY)
        return inotify

    @staticmethod
    def from_env() -> 'TlsConfig | None':
        cert_file = os.getenv("TLS_CERT_FILE", None)
        key_file = os.getenv("TLS_KEY_FILE", None)
        password = os.getenv("TLS_KEY_PASSWORD", None)

        if (cert_file is not None) != (key_file is not None):
            raise ValueError("Both TLS_CERT_FILE and TLS_KEY_FILE must be set together, or neither.")

        try:
            if cert_file: # try reading such that we can fail early if the files are not readable
                txt_cert = _read_file_content(cert_file)
                txt_key = _read_file_content(key_file)
                if "-----BEGIN CERTIFICATE-----" not in txt_cert:
                    raise ValueError(f"TLS certificate file {cert_file!r} does not contain a valid PEM-encoded certificate.")
                if "-----BEGIN " not in txt_key or not "PRIVATE KEY-----" in txt_key:
                    raise ValueError(f"TLS key file {key_file!r} does not contain a valid PEM-encoded private key.")
        except Exception as exc:
            raise ValueError(f"Error reading TLS certificate or key file: {exc}") from exc

        if password is not None and password.startswith("file:"):
            password = _read_file_content(password[5:])

        if cert_file:
            return TlsConfig(
                _cert_file_path=cert_file,
                _key_file_path=key_file,
                _key_password=password
            )
        return None

@dataclass
class AuthConfig:
    """Client L7-Authentication (TLS-based authentication is configured in TlsConfig)"""
    username: str | None
    password: str | None
    bearer_token: str | None = None

    _cached_basic_auth_header: str | None = None
    _cached_bearer_auth_header: str | None = None

    def get_basic_auth(self) -> tuple[str, str] | None:
        if self.username is not None and self.password is not None:
            return (self.username, self.password)
        return None

    def get_basic_auth_header(self) -> str | None:
        """Returns the value for the HTTP Authorization header, or None if no auth is configured"""
        if self.username is None:
            return None
        if self._cached_basic_auth_header is not None:
            return self._cached_basic_auth_header
        user_pass = f"{self.username}:{self.password}"
        encoded = base64.b64encode(user_pass.encode("utf-8")).decode("utf-8")
        self._cached_basic_auth_header = f"Basic {encoded}"
        return self._cached_basic_auth_header

    def get_bearer_auth_header(self) -> str | None:
        """Returns the value for the HTTP Authorization header, or None if no auth is configured"""
        if self.bearer_token is None:
            return None
        if self._cached_bearer_auth_header is not None:
            return self._cached_bearer_auth_header
        self._cached_bearer_auth_header = f"Bearer {self.bearer_token}"
        return self._cached_bearer_auth_header

    def get_type(self) -> Literal["basic", "bearer", "none"]:
        if self.username is not None and self.password is not None:
            return "basic"
        if self.bearer_token is not None:
            return "bearer"
        return "none"

    @staticmethod
    def from_env() -> "AuthConfig | None":
        username = os.getenv("AUTH_USERNAME", None)
        password = os.getenv("AUTH_PASSWORD", None)
        bearer_token = os.getenv("AUTH_BEARER_TOKEN", None)

        if (username is not None) != (password is not None):
            raise ValueError("Both AUTH_USERNAME and AUTH_PASSWORD must be set together, or neither.")

        if (username is not None) and (bearer_token is not None):
            raise ValueError("AUTH_USERNAME/AUTH_PASSWORD and AUTH_BEARER_TOKEN are mutually exclusive.")

        if username is not None and username.startswith("file:"):
            username = _read_file_content(username[5:])
        if password is not None and password.startswith("file:"):
            password = _read_file_content(password[5:])
        if bearer_token is not None and bearer_token.startswith("file:"):
            bearer_token = _read_file_content(bearer_token[5:])
        return AuthConfig(username=username, password=password, bearer_token=bearer_token)

type MetricSet = Literal["exporter", "grand_totals", "totals", "instances", "details", "allowlist_totals", "allowlist_instances", "allowlist_details"]

def _parse_metric_set(raw: str) -> MetricSet:
    raw = raw.strip().lower()
    if raw not in ("exporter", "grand_totals", "totals", "instances", "details", "allowlist_totals", "allowlist_instances", "allowlist_details"):
        raise ValueError(f"Invalid metric set: {raw}")
    return raw

# pylint: disable=too-many-instance-attributes
@dataclass
class Config:
    """The application-wide configuration, read from environment variables"""

    version: str
    """The current application version"""

    lapi_url: str
    machine_id: str
    machine_password: str
    http_timeout_seconds: float
    batch_size: int

    bind_port: int
    bind_host: str
    tls: TlsConfig | None
    auth: AuthConfig | None
    log_level: str

    metrics_retain_counter_startup_increments: bool
    """
    Whether the initial poll shall be prefixed with zero values,
    such that PromQL increment()-queries see the initial poll
    as full increments.
    This is helpful when the exporter is newly-introduced, to get the first scrape.
    But afterwards it is better disabled, to avoid double-counting upon exporter restarts.
    """
    metrics_counter_max_count: int
    """
    Maximum number of counters to keep in memory. If this is exceeded, the oldest counters will be pruned.
    """
    metrics_counter_max_age: timedelta
    """
    Maximum age for a non-incremented counter to be kept in memory. If this is exceeded, the counter will be pruned.
    """
    metrics_retain_capi_decisions: bool
    """
    Whether to retain CAPI-originated decisions in the metrics. This is disabled by default, as it can explode the cardinality of the metrics and overload Prometheus.
    Only use this for testing!
    """

    alert_dedup_window_size: int
    """
    Maximum number of recently-seen alert identities kept in memory to deduplicate alerts
    across polls. Once exceeded, the oldest identity is evicted. Must comfortably exceed the
    number of alerts re-fetched before the poll watermark advances past them (ie. at least a
    few times the LAPI batch size) to avoid counting the same alert twice.
    """

    scenario_rewriter: ScenarioRewriter | None
    """
    Ordered, sed-style regex substitutions applied to each alert's scenario during parsing,
    used to collapse high-cardinality dynamic scenario names into a bounded set of labels.
    """

    metric_sets: set[MetricSet]
    """Which kinds of metrics to export."""

    def __init__(self) -> None:
        self.version = _read_version()
        self.lapi_url = _read_required_env("CROWDSEC_LAPI_URL")
        self.machine_id = _read_required_env("CROWDSEC_MACHINE_ID")
        self.machine_password = _read_required_env("CROWDSEC_MACHINE_PASSWORD")
        self.http_timeout_seconds = float(os.getenv("CROWDSEC_LAPI_HTTP_TIMEOUT_SECONDS", "10"))
        self.batch_size = int(os.getenv("CROWDSEC_LAPI_BATCH_SIZE", "10000"))
        self.bind_port = _read_bind_port()
        self.bind_host = os.getenv("BIND_HOST", "0.0.0.0")
        self.log_level = os.getenv("LOG_LEVEL", "INFO").upper()

        self.metrics_retain_counter_startup_increments = os.getenv("METRICS_RETAIN_COUNTER_STARTUP_INCREMENTS", "false").lower() in ("true", "1", "yes")
        self.metrics_retain_capi_decisions = os.getenv("METRICS_RETAIN_CAPI_DECISIONS", "false").lower() in ("true", "1", "yes")
        self.metrics_counter_max_count = int(os.getenv("METRICS_COUNTER_MAX_COUNT", "10000"))

        self.alert_dedup_window_size = int(os.getenv("ALERT_DEDUP_WINDOW_SIZE", "50000"))

        self.scenario_rewriter = ScenarioRewriter.parse(os.getenv("SCENARIO_REWRITES", ""))

        metrics_counter_max_age_seconds = int(os.getenv("METRICS_COUNTER_MAX_AGE_SECONDS", str(5*60))) # 5min
        self.metrics_counter_max_age = timedelta(seconds=metrics_counter_max_age_seconds)

        if self.machine_id.startswith("file:"):
            self.machine_id = _read_file_content(self.machine_id[5:])
        if self.machine_password.startswith("file:"):
            self.machine_password = _read_file_content(self.machine_password[5:])

        self.tls = TlsConfig.from_env()
        self.auth = AuthConfig.from_env()

        metric_sets_env = os.getenv("METRIC_SETS", "default")
        if metric_sets_env.lower() == "default":
            metric_sets_env = "exporter, grand_totals, totals, instances, allowlist_totals, allowlist_instances"
        elif metric_sets_env.lower() == "basic":
            metric_sets_env = "exporter, grand_totals, allowlist_totals"
        elif metric_sets_env.lower() == "all":
            metric_sets_env = "exporter, grand_totals, totals, instances, details, allowlist_totals, allowlist_instances"

        self.metric_sets = {_parse_metric_set(s) for s in metric_sets_env.split(",") if s.strip() != ""}
