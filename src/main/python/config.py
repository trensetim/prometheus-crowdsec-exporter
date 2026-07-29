import os
from dataclasses import dataclass
from datetime import timedelta

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

# pylint: disable=too-many-instance-attributes
@dataclass
class Config:
    """The application-wide configuration, read from environment variables"""

    version: str
    """The current application version"""

    local_api_url: str
    machine_id: str
    machine_password: str
    http_timeout_seconds: float

    bind_port: int
    bind_host: str
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

    def __init__(self) -> None:
        self.version = _read_version()
        self.local_api_url = _read_required_env("CROWDSEC_LAPI_URL")
        self.machine_id = _read_required_env("CROWDSEC_MACHINE_ID")
        self.machine_password = _read_required_env("CROWDSEC_MACHINE_PASSWORD")
        self.http_timeout_seconds = float(os.getenv("CROWDSEC_LAPI_HTTP_TIMEOUT_SECONDS", "10"))
        self.bind_port = _read_bind_port()
        self.bind_host = os.getenv("BIND_HOST", "0.0.0.0")
        self.log_level = os.getenv("LOG_LEVEL", "INFO").upper()

        self.metrics_retain_counter_startup_increments = os.getenv("METRICS_RETAIN_COUNTER_STARTUP_INCREMENTS", "false").lower() in ("true", "1", "yes")
        self.metrics_counter_max_count = int(os.getenv("METRICS_COUNTER_MAX_COUNT", "10000"))

        metrics_counter_max_age_seconds = int(os.getenv("METRICS_COUNTER_MAX_AGE_SECONDS", str(5*60))) # 5min
        self.metrics_counter_max_age = timedelta(seconds=metrics_counter_max_age_seconds)

        if self.machine_id.startswith("file:"):
            self.machine_id = _read_file_content(self.machine_id[5:])
        if self.machine_password.startswith("file:"):
            self.machine_password = _read_file_content(self.machine_password[5:])
