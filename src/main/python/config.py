import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Config:
    version: str
    """The current application version"""

    crowdSecLapiURL: str
    apiKey: str
    metricsPort: int
    metricsHost: str
    pollingIntervalInSeconds: int
    logLevel: str

    @classmethod
    def readConfigFromEnv(cls) -> "Config":
        return cls(
            crowdSecLapiURL = _require("CROWDSEC_LAPI_URL"),
            apiKey = _require("CROWDSEC_API_KEY"),
            metricsPort = _getInt("METRICS_PORT", "8000"),
            metricsHost = os.getenv("METRICS_HOST", "0.0.0.0"),
            pollingIntervalInSeconds = _getInt("POLL_INTERVAL_SECONDS", "60"),
            logLevel = os.getenv("LOG_LEVEL", "INFO").upper(),
            version = Config.read_version(),
        )

    @classmethod
    def read_version(cls) -> str:
        """Assumes a version.txt file is present in the same directory as this script"""
        current_file_path = os.path.realpath(__file__)
        current_file_dir = os.path.dirname(current_file_path)
        version_file_path = os.path.join(current_file_dir, "version.txt")
        with open(version_file_path, "r", encoding="utf-8") as version_file:
            return version_file.read().strip()

def _require(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise ValueError(
                f"Required environment variable '{key}' is not set or empty. "
            )
    return value

def _getInt(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except ValueError as exc:
        raise ValueError(
                f"Environment variable '{key}' must be an integer"
            ) from exc
