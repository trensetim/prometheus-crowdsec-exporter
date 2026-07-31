import signal
from socketserver import ThreadingMixIn
import ssl
import threading
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server
from prometheus_client import REGISTRY, CollectorRegistry, make_wsgi_app

import logger
from config import Config, AuthConfig, TlsConfig

log = logger.get_logger("server")

# we have this here to control logging correctly (the default implementation logs all requests to stdout in a custom format)
class _RequestHandler(WSGIRequestHandler):
    # pylint: disable=redefined-builtin
    def log_message(self, format: str, *args: any):
        message = format % args
        addr = self.address_string()
        log.debug("request", client_address=addr, message=message)

def _new_tls_context(config: TlsConfig) -> ssl.SSLContext:
    """Load context supports SSL. Inspired by prometheus_client/exposition.py#_get_ssl_ctx"""
    ssl_cxt = ssl.SSLContext(protocol=ssl.PROTOCOL_TLSv1_2)

    try:
        ssl_cxt.load_cert_chain(certfile=config.get_cert_file_path(), keyfile=config.get_key_file_path(), password=config.consume_key_password())
    except IOError as exc:
        raise type(exc)(f"Cannot load server certificate file {config.get_cert_file_path()!r} or its private key file {config.get_key_file_path()!r}: {str(exc)}") from exc

    return ssl_cxt

def _check_auth(environ, config: AuthConfig | None) -> bool:
    if config is None or config.get_type() == "none":
        return True

    auth_header = environ.get("HTTP_AUTHORIZATION")
    if auth_header is None:
        return False

    if config.get_type() == "basic":
        if not auth_header.startswith("Basic "):
            return False
        return auth_header == config.get_basic_auth_header()

    if config.get_type() == "bearer":
        if not auth_header.startswith("Bearer "):
            return False
        return auth_header == config.get_bearer_auth_header()

    raise ValueError(f"Unsupported authentication type: {config.get_type()}")

# pylint: disable=too-few-public-methods
class MetricsServer:
    wsgi_server: WSGIServer
    thread: threading.Thread

    def __init__(self, config: Config, prometheus_registry: CollectorRegistry = REGISTRY):
        prometheus_wsgi_app = make_wsgi_app(prometheus_registry)

        def _wsgi_execute_app(environ, start_response):
            path = environ.get("PATH_INFO", "")

            # /health is authenticated anonymously
            if path == "/health":
                start_response("200 OK", [("Content-type", "text/plain; charset=utf-8")])
                return [b"OK"]

            if not _check_auth(environ, config.auth):
                headers = [("Content-type", "text/plain; charset=utf-8")]
                if config.auth.get_type() == "basic":
                    headers += [("WWW-Authenticate", 'Basic realm="Prometheus CrowdSec Exporter"')]
                start_response("401 Unauthorized", headers)
                return [b"Unauthorized"]

            if path == "/metrics":
                return prometheus_wsgi_app(environ, start_response)

            # Fallback for unmapped endpoints
            start_response("404 Not Found", [("Content-type", "text/plain; charset=utf-8")])
            return [b"Not Found"]

        class ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
            # copied from prometheus_client/exposition.py#L155 and #L228
            daemon_threads = True

        self.wsgi_server = make_server(
            config.bind_host, config.bind_port,
            _wsgi_execute_app,
            server_class=ThreadingWSGIServer, handler_class=_RequestHandler
            )
        if config.tls is not None:
            context = _new_tls_context(config.tls)
            self.wsgi_server.socket = context.wrap_socket(self.wsgi_server.socket, server_side=True)
        self.thread = threading.Thread(target=self.wsgi_server.serve_forever)
        self.thread.daemon = True
        self.thread.start()

        log.info("started", port = config.bind_port, host = config.bind_host)

    def run_forever(self):
        """Registers SIGINT and SIGTERM handlers and awaits such a signal, while serving in a separate thread"""
        stop_event = threading.Event()

        def handle_stop_signal(signum: int, _: object) -> None:
            signal_name = signal.Signals(signum).name
            log.info("interrupted", signal = signal_name)
            stop_event.set()

        signal.signal(signal.SIGTERM, handle_stop_signal)
        signal.signal(signal.SIGINT, handle_stop_signal)

        log.info("running_forever")

        while not stop_event.is_set():
            stop_event.wait(0.5)
        # interruption logged in the handler already, dont need to repeat it here

    def stop(self):
        """Stops the WSGI server and waits for the thread to finish"""
        log.info("stopping")
        self.wsgi_server.shutdown()
        self.thread.join(timeout=2.0)
        if self.thread.is_alive():
            raise RuntimeError("Metrics server thread did not stop within the timeout period.")
        log.info("stopped")
