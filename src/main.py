import sys
from src.config import Config
from src import logger as log_module

def main() -> None:
    """ Load Configuration """
    try:
        config = Config.readConfigFromEnv()
    except EnvironmentError as exc:
        # f is a string prefix in python used to embed variables direct into the string
        # log to sys.stderr cause logger is not initialized yet -> we need log-level from env to initialize the logger
        print(f"FATAL config error: {exc}", file=sys.stderr, flush=True)
        sys.exit(1)

    """ Initialize and configure logger """
    log_module.configure(config.logLevel)
    log = log_module.getLogger("main")

    log.info(
        "startup",
        appVersion = config.appVersion,
        gitCommit = config.gitCommit,
        logLevel = config.logLevel,
        metricsPort = config.metricsPort,
        pollingIntervalInSeconds = config.pollingIntervalInSeconds,
        crowdSecLapiURL = config.crowdSecLapiURL,
    )

if __name__ == "__main__":
    main()
