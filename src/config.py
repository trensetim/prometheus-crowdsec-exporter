import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Config:
    crowdSecLapiURL: str
    apiKey: str
    metricsPort: int
    metricsHost: str
    pollingIntervalInSeconds: int
    logLevel: str
    appVersion: str
    gitCommit: str

    @classmethod
    def readConfigFromEnv(cls) -> "Config":
        return cls(
            crowdSecLapiURL = _require("CROWDSEC_LAPI_URL"),
            apiKey = _require("CROWDSEC_API_KEY"),
            metricsPort = int(os.getenv("METRICS_PORT", "8000")),
            metricsHost = os.getenv("METRICS_HOST", "0.0.0.0"),
            pollingIntervalInSeconds = int(os.getenv("POLL_INTERVAL_SECONDS", "60")),
            logLevel = os.getenv("LOG_LEVEL", "INFO").upper(),
            appVersion = os.getenv("APP_VERSION", "unknown"),
            gitCommit = os.getenv("GIT_COMMIT", "unknown"),
        )

def _require(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise EnvironmentError(
            f"Required environment variable '{key}' is not set or empty. "
        )
    return value
