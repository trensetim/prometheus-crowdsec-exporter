import os
from dataclasses import dataclass

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
    current_file_path = os.path.realpath(__file__)
    current_file_dir = os.path.dirname(current_file_path)
    version_file_path = os.path.join(current_file_dir, "version.txt")
    with open(version_file_path, "r", encoding="utf-8") as version_file:
        return version_file.read().strip()


@dataclass(frozen=True)
class Config:
    """The application-wide configuration, read from environment variables"""

    version: str = _read_version()
    """The current application version"""

    crowdSecLapiURL: str = _read_required_env("CROWDSEC_LAPI_URL")
    apiKey: str = _read_required_env("CROWDSEC_API_KEY")
    bindPort: int = _read_bind_port()
    bindHost: str = os.getenv("BIND_HOST", "0.0.0.0")
    logLevel: str = os.getenv("LOG_LEVEL", "INFO").upper()
