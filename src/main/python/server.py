import signal
import threading
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server
from prometheus_client import REGISTRY, CollectorRegistry, make_wsgi_app

import logger
from config import Config

log = logger.get_logger("server")

# we have this here to control logging correctly (the default implementation logs all requests to stdout in a custom format)
class _RequestHandler(WSGIRequestHandler):
    # pylint: disable=redefined-builtin
    def log_message(self, format: str, *args: any):
        message = format % args
        addr = self.address_string()
        log.debug("request", client_address=addr, message=message)

# pylint: disable=too-few-public-methods
class MetricsServer:
    wsgi_server: WSGIServer
    thread: threading.Thread

    def __init__(self, config: Config, prometheus_registry: CollectorRegistry = REGISTRY):
        prometheus_wsgi_app = make_wsgi_app(prometheus_registry)

        def _make_wsgi_app(environ, start_response):
            path = environ.get('PATH_INFO', '')

            if path == '/health':
                status = '200 OK'
                headers = [('Content-type', 'text/plain; charset=utf-8')]
                start_response(status, headers)
                return [b'OK']

            if path == '/metrics':
                return prometheus_wsgi_app(environ, start_response)

            # Fallback for unmapped endpoints
            status = '404 NOT FOUND'
            headers = [('Content-type', 'text/plain; charset=utf-8')]
            start_response(status, headers)
            return [b'Not Found']

        self.wsgi_server = make_server(
            config.bind_host, config.bind_port,
            _make_wsgi_app,
            server_class=WSGIServer, handler_class=_RequestHandler
            )
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
