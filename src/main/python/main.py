import signal
import sys
import threading
import time

from prometheus_client import start_http_server
from prometheus_client.core import REGISTRY

from config import Config
from collector import CrowdSecCollector
from logger import getLogger, configure

def main() -> None:
    # --- Load Configuration ---
    try:
        config = Config.readConfigFromEnv()
    except EnvironmentError as exc:
        # log to sys.stderr cause logger is not initialized yet -> we need log-level from env to initialize the logger
        print(f"FATAL config error: {exc}", file=sys.stderr, flush=True)
        sys.exit(1)

    # --- Initialize and configure logger ---
    configure(config.logLevel)
    log = getLogger("main")

    log.info(
        "startup",
        version = config.version,
        logLevel = config.logLevel,
        metricsPort = config.metricsPort,
        pollingIntervalInSeconds = config.pollingIntervalInSeconds,
        crowdSecLapiURL = config.crowdSecLapiURL,
    )

    # --- Register custom collector for prometheus_client ---
    REGISTRY.register(CrowdSecCollector(config))

    # --- Start Prometheus/metrics HTTP server ---
    try:
        start_http_server(port = config.metricsPort, addr = config.metricsHost)
    except OSError as exc:
        log.error(
            "metricsServerFailedToStart",
            port = config.metricsPort,
            detail = str(exc),
        )
        sys.exit(1)

    log.info(
        "metricsServerStarted",
        port = config.metricsPort
    )

    # --- Set up graceful shutdown via SIGTERM / SIGINT ---
    stopEvent = threading.Event()

    def _handleSignal(signum: int, _frame: object) -> None:
        sigName = signal.Signals(signum).name
        log.info(
            "shutdownSignalReceived",
            signal = sigName
        )
        stopEvent.set()

    signal.signal(signal.SIGTERM, _handleSignal)
    signal.signal(signal.SIGINT, _handleSignal)

    # --- Polling loop ---
    log.info("pollingLoopStarted")
    while not stopEvent.is_set():
        _interruptibleSleep(config.pollingIntervalInSeconds, stopEvent)

    log.info("shutdownComplete")
    sys.exit(0)

def _interruptibleSleep(seconds: int, stopEvent: threading.Event) -> None:
    deadline = time.monotonic() + seconds
    while not stopEvent.is_set():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        stopEvent.wait(timeout = min(0.5, remaining))

if __name__ == "__main__":
    main()
