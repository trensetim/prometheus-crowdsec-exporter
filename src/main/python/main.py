import logging
import signal
import threading
from typing import Tuple
from wsgiref.simple_server import WSGIServer

from prometheus_client import start_http_server
from prometheus_client.core import REGISTRY

from config import Config
from collector import CrowdSecCollector
import logger

CONFIG: Config
LOGGER: logging.Logger

def _log_startup_info():
    LOGGER.info("startup",
        version = CONFIG.version,
        logLevel = CONFIG.logLevel,
        port = CONFIG.bindPort,
        host = CONFIG.bindHost,
        crowdSecLapiURL = CONFIG.crowdSecLapiURL,
    )

def _init_logging() -> logging.Logger:
    logger.configure(CONFIG.logLevel)
    return logger.getLogger("main")

def _start_metrics_server() -> Tuple[WSGIServer, threading.Thread]:
    REGISTRY.register(CrowdSecCollector(CONFIG))
    result = start_http_server(port = CONFIG.bindPort, addr = CONFIG.bindHost)
    LOGGER.info("metricsServerStarted", port = CONFIG.bindPort, host = CONFIG.bindHost)
    return result

def _stop_metrics_server(server: Tuple[WSGIServer, threading.Thread]):
    server[0].shutdown()
    server[1].join(timeout=2.0)

def _run_forever(log: logging.Logger):
    stop_event = threading.Event()

    def handle_stop_signal(log: logging.Logger, signum: int, _frame: object) -> None:
        signal_name = signal.Signals(signum).name
        log.info("shutdownSignalReceived", signal = signal_name)
        stop_event.set()
    signal.signal(signal.SIGTERM, lambda signum, _frame: handle_stop_signal(log, signum, _frame))
    signal.signal(signal.SIGINT, lambda signum, _frame: handle_stop_signal(log, signum, _frame))

    while not stop_event.is_set():
        stop_event.wait(0.5)

if __name__ == "__main__":
    CONFIG = Config()
    LOGGER = _init_logging()
    _log_startup_info()

    metrics_server = _start_metrics_server()
    _run_forever(LOGGER)
    _stop_metrics_server(metrics_server)

    LOGGER.info("goodbye")
