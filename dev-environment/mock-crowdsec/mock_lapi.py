"""
Mock CrowdSec Local API for local development.

Implements the three endpoints used by the exporter:
  GET /v1/decisions
  GET /v1/alerts
  GET /v1/allowlists

Auth: validates X-Api-Key header against DEV_API_KEY env var.
/health is unauthenticated - used by Docker healthcheck.
"""

import json
import os
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

API_KEY = os.getenv("DEV_API_KEY", "dev-bouncer-key-12345")
PORT    = int(os.getenv("PORT", "8080"))


def _rotating_decisions() -> list[dict]:
    t = int(time.time() // 30)
    base = [
        {
            "id": 1, "uuid": "d1-uuid",
            "origin": "crowdsec", "type": "ban",
            "scope": "Ip", "value": "203.0.113.42",
            "duration": "23h59m00s", "until": "2099-01-01T00:00:00Z",
            "scenario": "crowdsecurity/ssh-bf", "simulated": False,
        },
        {
            "id": 2, "uuid": "d2-uuid",
            "origin": "crowdsec", "type": "ban",
            "scope": "Ip", "value": "198.51.100.7",
            "duration": "23h59m00s", "until": "2099-01-01T00:00:00Z",
            "scenario": "crowdsecurity/http-probing", "simulated": False,
        },
        {
            "id": 3, "uuid": "d3-uuid",
            "origin": "CAPI", "type": "ban",
            "scope": "Ip", "value": "192.0.2.99",
            "duration": "11h00m00s", "until": "2099-01-01T00:00:00Z",
            "scenario": "crowdsecurity/portscan", "simulated": False,
        },
        {
            "id": 4, "uuid": "d4-uuid",
            "origin": "lists", "type": "captcha",
            "scope": "Ip", "value": "203.0.113.55",
            "duration": "1h00m00s", "until": "2099-01-01T00:00:00Z",
            "scenario": "crowdsecurity/http-bf", "simulated": False,
        },
    ]
    if t % 2 == 0:
        base.append({
            "id": 5, "uuid": "d5-uuid",
            "origin": "crowdsec", "type": "ban",
            "scope": "Range", "value": "10.20.30.0/24",
            "duration": "6h00m00s", "until": "2099-01-01T00:00:00Z",
            "scenario": "crowdsecurity/ssh-bf", "simulated": False,
        })
    return base


def _rotating_alerts() -> list[dict]:
    t = int(time.time() // 60)
    alerts = [
        {
            "id": 101, "uuid": "a1-uuid",
            "machine_id": "dev-machine-01",
            "created_at": "2026-07-08T08:00:00Z",
            "scenario": "crowdsecurity/ssh-bf",
            "scenario_hash": "abc123", "scenario_version": "0.1",
            "message": "Ip 203.0.113.42 triggered crowdsecurity/ssh-bf",
            "events_count": 15,
            "start_at": "2026-07-08T07:59:00Z",
            "stop_at":  "2026-07-08T08:00:00Z",
            "capacity": 5, "leakspeed": "10s",
            "simulated": False, "remediation": True,
            "kind": "signal", "labels": ["ssh", "bruteforce"],
            "decisions": [
                {
                    "id": 1, "uuid": "d1-uuid",
                    "origin": "crowdsec", "type": "ban",
                    "scope": "Ip", "value": "203.0.113.42",
                    "duration": "24h", "until": "2099-01-01T00:00:00Z",
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
            "created_at": "2026-07-08T07:30:00Z",
            "scenario": "crowdsecurity/http-probing",
            "scenario_hash": "def456", "scenario_version": "0.2",
            "message": "Ip 198.51.100.7 triggered crowdsecurity/http-probing",
            "events_count": 42,
            "start_at": "2026-07-08T07:28:00Z",
            "stop_at":  "2026-07-08T07:30:00Z",
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
            "created_at": "2026-07-08T08:15:00Z",
            "scenario": "crowdsecurity/http-bf",
            "scenario_hash": "ghi789", "scenario_version": "0.1",
            "message": "Ip 203.0.113.55 triggered crowdsecurity/http-bf",
            "events_count": 7,
            "start_at": "2026-07-08T08:14:00Z",
            "stop_at":  "2026-07-08T08:15:00Z",
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
    return [
        {
            "name": "internal-infra",
            "allowlist_id": "al-001",
            "description": "Internal infrastructure IPs – never ban",
            "console_managed": False,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-06-01T00:00:00Z",
            "items": [
                {
                    "value": "10.0.0.0/8",
                    "description": "Private RFC1918",
                    "created_at": "2026-01-01T00:00:00Z",
                    "expiration": None,
                },
                {
                    "value": "192.168.0.0/16",
                    "description": "Local LAN",
                    "created_at": "2026-01-01T00:00:00Z",
                    "expiration": None,
                },
            ],
        },
        {
            "name": "temp-partner-ips",
            "allowlist_id": "al-002",
            "description": "Temporary partner IPs during integration phase",
            "console_managed": True,
            "created_at": "2026-07-01T00:00:00Z",
            "updated_at": "2026-07-08T00:00:00Z",
            "items": [
                {
                    "value": "203.0.113.100",
                    "description": "Partner X integration server",
                    "created_at": "2026-07-01T00:00:00Z",
                    "expiration": "2026-07-09T08:00:00Z",
                },
            ],
        },
    ]


class MockLAPIHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        path = urlparse(self.path).path

        # /health is unauthenticated – used by Docker healthcheck
        if path == "/health":
            self._json(200, {"status": "ok", "service": "mock-crowdsec-lapi"})
            return

        if not self._check_auth():
            return

        if path == "/v1/decisions":
            self._json(200, _rotating_decisions())
        elif path == "/v1/alerts":
            self._json(200, _rotating_alerts())
        elif path == "/v1/allowlists":
            self._json(200, _allowlists())
        else:
            self._json(404, {"message": f"unknown path: {path}"})

    def _check_auth(self) -> bool:
        if self.headers.get("X-Api-Key") != API_KEY:
            self._json(403, {"message": "access forbidden"})
            return False
        return True

    def _json(self, status: int, data) -> None:
        body = json.dumps(data, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print(
            f'{{"service":"mock-crowdsec","method":"{self.command}",'
            f'"path":"{self.path}","status":"{args[1]}"}}',
            flush=True
        )


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), MockLAPIHandler)
    print(
        f'{{"service":"mock-crowdsec","event":"started","port":{PORT}}}',
        flush=True
    )
    server.serve_forever()
