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

class _ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
    # copied from prometheus_client/exposition.py#L155 and #L228
    daemon_threads = True

# pylint: disable=too-few-public-methods
class MetricsServer:
    _wsgi_server: WSGIServer
    _thread: threading.Thread | None
    _config: Config

    def __init__(self, config: Config, prometheus_registry: CollectorRegistry = REGISTRY):
        self.prometheus_wsgi_app = make_wsgi_app(prometheus_registry)
        self._config = config
        self._thread = None
        log.info("configured", port = config.bind_port, host = config.bind_host)

    def _wsgi_execute_app(self, environ, start_response):
        path = environ.get("PATH_INFO", "")

        # /health is authenticated anonymously
        if path == "/health":
            start_response("200 OK", [("Content-type", "text/plain; charset=utf-8")])
            return [b"OK"]

        if not _check_auth(environ, self._config.auth):
            headers = [("Content-type", "text/plain; charset=utf-8")]
            if self._config.auth.get_type() == "basic":
                headers += [("WWW-Authenticate", 'Basic realm="Prometheus CrowdSec Exporter"')]
            start_response("401 Unauthorized", headers)
            return [b"Unauthorized"]

        if path == "/metrics":
            return self.prometheus_wsgi_app(environ, start_response)

        # Fallback for unmapped endpoints
        start_response("404 Not Found", [("Content-type", "text/plain; charset=utf-8")])
        return [b"Not Found"]

    def start(self):
        """Fires off a daemon thread to run the http server."""
        if self.is_running():
            raise RuntimeError("Metrics server is already running.")

        self._wsgi_server = make_server(
            self._config.bind_host, self._config.bind_port,
            self._wsgi_execute_app,
            server_class=_ThreadingWSGIServer, handler_class=_RequestHandler
        )
        if self._config.tls is not None:
            context = _new_tls_context(self._config.tls)
            self._wsgi_server.socket = context.wrap_socket(self._wsgi_server.socket, server_side=True)

        self._thread = threading.Thread(target=self._wsgi_server.serve_forever)
        self._thread.daemon = True
        self._thread.start()

        log.info("started")

    def stop(self):
        """Stops the WSGI server and waits for the thread to finish"""
        if self.is_running() is False:
            raise RuntimeError("Metrics server is not running.")

        log.info("stopping")
        self._wsgi_server.shutdown()
        self._wsgi_server.server_close()
        self._thread.join(timeout=2.0)
        if self._thread.is_alive():
            raise RuntimeError("Metrics server thread did not stop within the timeout period.")
        self._thread = None
        log.info("stopped")

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()
