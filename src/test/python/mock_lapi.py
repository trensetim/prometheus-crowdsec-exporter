"""
Mock CrowdSec Local API for local development.

Implements the endpoints used by the prometheus-crowdsec-exporter:
  POST   /v1/watchers/login           - JWT authentication
  GET    /v1/heartbeat                - Machine heartbeat
  GET    /v1/alerts                   - Get alerts
  GET    /v1/allowlists               - Get allowlists (with ?with_content=true)
  GET    /health                      - Health check (unauthenticated)

Auth: JWT Bearer token via /v1/watchers/login endpoint.
"""

import json
import os
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
from dataclasses import dataclass

MACHINE_ID = os.getenv("CROWDSEC_MACHINE_ID", "dev-machine")
MACHINE_PASSWORD = os.getenv("CROWDSEC_MACHINE_PASSWORD", "dev-password-12345")
PORT = int(os.getenv("PORT", "8080"))


@dataclass
class JWTToken:
    token: str
    expiry: datetime

    def is_valid(self) -> bool:
        return datetime.now(tz=timezone.utc) < self.expiry


# Store active JWT tokens (in real implementation, would validate properly)
_jwt_storage: dict[str, JWTToken] = {}


def _rotating_alerts() -> list[dict]:
    """Generate rotating alert data for testing.

    This endpoint is kept for backwards compatibility but is now the primary
    endpoint. Decisions are included within each alert.
    """
    t = int(time.time() // 60)
    now = datetime.now(tz=timezone.utc)

    alerts = [
        {
            "id": 101, "uuid": "a1-uuid",
            "machine_id": "dev-machine-01",
            "created_at": (now - timedelta(minutes=60)).isoformat(),
            "scenario": "crowdsecurity/ssh-bf",
            "scenario_hash": "abc123", "scenario_version": "0.1",
            "message": "Ip 203.0.113.42 triggered crowdsecurity/ssh-bf",
            "events_count": 15,
            "start_at": (now - timedelta(minutes=61)).isoformat(),
            "stop_at":  (now - timedelta(minutes=60)).isoformat(),
            "capacity": 5, "leakspeed": "10s",
            "simulated": False, "remediation": True,
            "kind": "signal", "labels": ["ssh", "bruteforce"],
            "decisions": [
                {
                    "id": 1, "uuid": "d1-uuid",
                    "origin": "crowdsec", "type": "ban",
                    "scope": "Ip", "value": "203.0.113.42",
                    "duration": "24h", "until": (now + timedelta(days=1)).isoformat(),
                    "scenario": "crowdsecurity/ssh-bf", "simulated": False,
                }
            ],
            "source": {
                "scope": "Ip", "value": "203.0.113.42",
                "ip": "203.0.113.42", "range": "",
                "as_number": "64496", "as_name": "EXAMPLE-AS",
                "cn": "CN", "latitude": 39.9042, "longitude": 116.4074,
            },
            "events": [], "meta": [],
        },
        {
            "id": 102, "uuid": "a2-uuid",
            "machine_id": "dev-machine-01",
            "created_at": (now - timedelta(minutes=30)).isoformat(),
            "scenario": "crowdsecurity/http-probing",
            "scenario_hash": "def456", "scenario_version": "0.2",
            "message": "Ip 198.51.100.7 triggered crowdsecurity/http-probing",
            "events_count": 42,
            "start_at": (now - timedelta(minutes=32)).isoformat(),
            "stop_at":  (now - timedelta(minutes=30)).isoformat(),
            "capacity": 10, "leakspeed": "5s",
            "simulated": False, "remediation": True,
            "kind": "signal", "labels": ["http", "scan"],
            "decisions": [],
            "source": {
                "scope": "Ip", "value": "198.51.100.7",
                "ip": "198.51.100.7", "range": "",
                "as_number": "64497", "as_name": "SCAN-AS",
                "cn": "RU", "latitude": 55.7558, "longitude": 37.6173,
            },
            "events": [], "meta": [],
        },
    ]
    if t % 2 == 0:
        alerts.append({
            "id": 103, "uuid": "a3-uuid",
            "machine_id": "dev-machine-02",
            "created_at": (now - timedelta(minutes=15)).isoformat(),
            "scenario": "crowdsecurity/http-bf",
            "scenario_hash": "ghi789", "scenario_version": "0.1",
            "message": "Ip 203.0.113.55 triggered crowdsecurity/http-bf",
            "events_count": 7,
            "start_at": (now - timedelta(minutes=16)).isoformat(),
            "stop_at":  (now - timedelta(minutes=15)).isoformat(),
            "capacity": 3, "leakspeed": "30s",
            "simulated": True, "remediation": False,
            "kind": "signal", "labels": ["http"],
            "decisions": [],
            "source": {
                "scope": "Ip", "value": "203.0.113.55",
                "ip": "203.0.113.55", "range": "",
                "as_number": "64498", "as_name": "OTHER-AS",
                "cn": "DE", "latitude": 52.5200, "longitude": 13.4050,
            },
            "events": [], "meta": [],
        })
    return alerts


def _allowlists() -> list[dict]:
    """Generate allowlist data for testing."""
    now = datetime.now(tz=timezone.utc)
    return [
        {
            "name": "internal-infra",
            "allowlist_id": "al-001",
            "description": "Internal infrastructure IPs – never ban",
            "console_managed": False,
            "created_at": (now - timedelta(days=180)).isoformat(),
            "updated_at": (now - timedelta(days=30)).isoformat(),
            "items": [
                {
                    "value": "10.0.0.0/8",
                    "description": "Private RFC1918",
                    "created_at": (now - timedelta(days=180)).isoformat(),
                    "expiration": None,
                },
                {
                    "value": "192.168.0.0/16",
                    "description": "Local LAN",
                    "created_at": (now - timedelta(days=180)).isoformat(),
                    "expiration": None,
                },
            ],
        },
        {
            "name": "temp-partner-ips",
            "allowlist_id": "al-002",
            "description": "Temporary partner IPs during integration phase",
            "console_managed": True,
            "created_at": (now - timedelta(days=7)).isoformat(),
            "updated_at": now.isoformat(),
            "items": [
                {
                    "value": "203.0.113.100",
                    "description": "Partner X integration server",
                    "created_at": (now - timedelta(days=7)).isoformat(),
                    "expiration": (now + timedelta(days=1)).isoformat(),
                },
            ],
        },
    ]


class MockLAPIHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        """Handle GET requests"""
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        query_params = parse_qs(parsed_url.query)

        # /health is unauthenticated – used by Docker healthcheck
        if path == "/health":
            self._json(200, {"status": "ok", "service": "mock-crowdsec-lapi"})
            return

        if not self._check_auth():
            return

        if path == "/v1/heartbeat":
            self._json(200, {"status": "ok"})
        elif path == "/v1/alerts":
            alerts = _rotating_alerts()
            # Filter by 'since' parameter if provided
            if "since" in query_params:
                try:
                    # Parse 'since' parameter (format: "123s" meaning 123 seconds ago)
                    since_str = query_params["since"][0]
                    seconds = int(since_str.rstrip("s"))
                    cutoff = datetime.now(tz=timezone.utc) - timedelta(seconds=seconds)
                    alerts = [
                        a for a in alerts
                        if datetime.fromisoformat(a["created_at"].replace("Z", "+00:00")) >= cutoff
                    ]
                except (ValueError, IndexError):
                    pass
            self._json(200, alerts)
        elif path == "/v1/allowlists":
            # The ?with_content=true parameter controls whether items are included
            # For our mock, we always return them if available
            self._json(200, _allowlists())
        else:
            self._json(404, {"message": f"unknown path: {path}"})

    def do_POST(self):
        """Handle POST requests"""
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        if path == "/v1/watchers/login":
            self._handle_login()
        else:
            self._json(404, {"message": f"unknown path: {path}"})

    def _handle_login(self) -> None:
        """Handle /v1/watchers/login endpoint"""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode()
            data = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            self._json(400, {"message": "invalid JSON"})
            return

        machine_id = data.get("machine_id")
        password = data.get("password")

        if machine_id != MACHINE_ID or password != MACHINE_PASSWORD:
            self._json(403, {"message": "invalid credentials"})
            return

        # Generate a simple JWT token (not cryptographically valid, just for testing)
        expiry = datetime.now(tz=timezone.utc) + timedelta(hours=1)
        token = f"mock-jwt-{time.time()}"
        _jwt_storage[token] = JWTToken(token, expiry)

        self._json(200, {
            "token": token,
            "expire": expiry.isoformat(),
        })

    def _check_auth(self) -> bool:
        """Check Bearer token authentication"""
        auth_header = self.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            self._json(403, {"message": "access forbidden"})
            return False

        token = auth_header[7:]  # Remove "Bearer " prefix
        if token not in _jwt_storage or not _jwt_storage[token].is_valid():
            self._json(403, {"message": "invalid or expired token"})
            return False

        return True

    def _json(self, status: int, data) -> None:
        """Send a JSON response"""
        body = json.dumps(data, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        """Log request in JSON format"""
        print(
            f'{{"service":"mock-crowdsec","method":"{self.command}",'
            f'"path":"{self.path}","status":"{args[1] if len(args) > 1 else "unknown"}"}}',
            flush=True
        )


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), MockLAPIHandler)
    print(
        f'{{"service":"mock-crowdsec","event":"started","port":{PORT},"machine_id":"{MACHINE_ID}"}}',
        flush=True
    )
    server.serve_forever()
