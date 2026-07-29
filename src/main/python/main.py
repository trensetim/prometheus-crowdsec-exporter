import logging

from prometheus_client.core import REGISTRY
from server import MetricsServer

from config import Config
from collector import CrowdsecCollector
import logger

CONFIG: Config
LOGGER: logging.Logger

def _log_startup_info():
    LOGGER.info("startup",
        version = CONFIG.version,
        log_level = CONFIG.log_level,
        port = CONFIG.bind_port,
        host = CONFIG.bind_host,
        crowdSecLapiURL = CONFIG.local_api_url,
    )

def _init_logging() -> logging.Logger:
    logger.configure(CONFIG.log_level)
    return logger.get_logger("main")

def _start_metrics_server() -> MetricsServer:
    REGISTRY.register(CrowdsecCollector(CONFIG))
    server = MetricsServer(CONFIG, REGISTRY)
    return server

if __name__ == "__main__":
    CONFIG = Config()
    LOGGER = _init_logging()
    _log_startup_info()

    metrics_server = _start_metrics_server()
    metrics_server.run_forever()
    metrics_server.stop()

    LOGGER.info("goodbye")
