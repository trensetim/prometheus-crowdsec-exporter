import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Config:
    version: str
    """The current application version"""

    crowdSecLapiURL: str
    apiKey: str
    bindPort: int
    bindHost: str
    logLevel: str

    @classmethod
    def readConfigFromEnv(cls) -> "Config":
        return cls(
            crowdSecLapiURL = Config._read_required_env("CROWDSEC_LAPI_URL"),
            apiKey = Config._read_required_env("CROWDSEC_API_KEY"),
            bindPort = Config._read_bind_port(),
            bindHost = os.getenv("BIND_HOST", "0.0.0.0"),
            logLevel = os.getenv("LOG_LEVEL", "INFO").upper(),
            version = Config._read_version(),
        )

    @staticmethod
    def _read_bind_port() -> int:
        """Reads the bind port from the environment variable BIND_PORT, or returns the default value of 8000 if not set"""
        try:
            return int(os.getenv("BIND_PORT", "8000"))
        except ValueError as exc:
            raise ValueError("Environment variable 'BIND_PORT' must be an integer") from exc

    @staticmethod
    def _read_version() -> str:
        """Assumes a version.txt file is present in the same directory as this script"""
        current_file_path = os.path.realpath(__file__)
        current_file_dir = os.path.dirname(current_file_path)
        version_file_path = os.path.join(current_file_dir, "version.txt")
        with open(version_file_path, "r", encoding="utf-8") as version_file:
            return version_file.read().strip()

    @staticmethod
    def _read_required_env(key: str) -> str:
        value = os.getenv(key)
        if not value or value == "":
            raise ValueError(f"Required environment variable '{key}' is not set or empty.")
        return value
