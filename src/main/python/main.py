import signal
import logging
import threading

from prometheus_client.core import REGISTRY
from server import MetricsServer

from config import Config
from collector import CrowdsecCollector
import logger

from urllib3 import connectionpool

CONFIG: Config
LOGGER: logging.Logger

def _log_startup_info():
    LOGGER.info("startup",
        version = CONFIG.version,
        log_level = CONFIG.log_level,
        bind_port = CONFIG.bind_port,
        bind_host = CONFIG.bind_host,
        lapi_url = CONFIG.lapi_url,
        lapi_batch_size = CONFIG.batch_size,
        lapi_timeout = CONFIG.http_timeout_seconds,
        tls_enabled = str(CONFIG.tls is not None),
        auth_type = CONFIG.auth.get_type() if CONFIG.auth is not None else "null",
        metric_sets = CONFIG.metric_sets
    )

def _init_logging() -> logging.Logger:
    logger.configure(CONFIG.log_level)
    connectionpool.log = logger.get_logger("urllib3.connectionpool")
    return logger.get_logger("main")

def _register_interrupt_signal(log: logging.Logger) -> threading.Event:
    stop = threading.Event()
    def _signal_handler(signum, _):
        signal_name = signal.Signals(signum).name
        log.info("interrupted", signal = signal_name)
        stop.set()
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)
    return stop

def _register_tls_cert_change(log: logging.Logger) -> threading.Event:
    stop = threading.Event()
    if CONFIG.tls is None:
        return stop # will never get set
    def _watch_loop():
        inotify = CONFIG.tls.register_inotify()
        while not stop.is_set():
            if len(inotify.read(timeout=1000)) > 0:
                break
        log.info("tls_cert_changed")
        stop.set()
        inotify.close()
    thread = threading.Thread(target=_watch_loop, daemon=True)
    thread.start()
    return stop

def _run_forever(stops: set[threading.Event]) -> None:
    while not any(stop.is_set() for stop in stops):
        stops[0].wait(0.5)

if __name__ == "__main__":
    CONFIG = Config()
    LOGGER = _init_logging()
    _log_startup_info()

    collector = CrowdsecCollector(CONFIG)
    REGISTRY.register(collector)
    server = MetricsServer(CONFIG, REGISTRY)
    stop_by_signal = _register_interrupt_signal(LOGGER)

    while not stop_by_signal.is_set():
        stop_by_tls_cert_change = _register_tls_cert_change(LOGGER)
        server.start()
        _run_forever([stop_by_signal, stop_by_tls_cert_change])
        server.stop()

    LOGGER.info("goodbye")
