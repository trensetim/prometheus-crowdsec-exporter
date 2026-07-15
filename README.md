# prometheus-crowdsec-exporter

A Prometheus exporter for [CrowdSec](https://www.crowdsec.net/) that polls the CrowdSec Local API (LAPI) and exposes decisions, alerts, and allowlists as Prometheus metrics for visualization in Grafana.

---

## Architecture

```
CrowdSec LAPI (:8080)
       │
       │  GET /v1/decisions
       │  GET /v1/alerts
       │  GET /v1/allowlists
       │  (X-Api-Key: bouncer, read-only)
       ▼
 [ Exporter Pod ]  ──►  /metrics (:8000)  ──►  Prometheus  ──►  Grafana
       │
       └─ stdout (structured JSON)  ──►  Loki  ──►  Grafana (logs panel)
```

The exporter is triggered by Prometheus scrapes (pull model) – it polls the LAPI on every `/metrics` request and yields fresh metrics each time.

---

## Metrics

### Decisions (`GET /v1/decisions`)

| Metric                                                     | Type    | Labels                                                                                                       | Description                                    |
| ---------------------------------------------------------- | ------- | ------------------------------------------------------------------------------------------------------------ | ---------------------------------------------- |
| `crowdsec_decisions`                                       | Gauge   | `decisionType`, `origin`, `scenario`, `scope`                                                                | Currently active decisions aggregated by type  |
| `crowdsec_decisions_details`                               | Gauge   | `decisionType`, `origin`, `scenario`, `scope`, `val`, `decisionId`, `uuid`, `duration`, `until`, `simulated` | One entry per active decision with full detail |
| `crowdsec_decisions_fetched_total`                         | Counter | –                                                                                                            | Total decisions fetched since exporter start   |
| `crowdsec_last_successful_decision_poll_timestamp_seconds` | Gauge   | `endpoint`                                                                                                   | Unix timestamp of last successful poll         |

### Alerts (`GET /v1/alerts`)

| Metric                                                   | Type    | Labels                                                                                                        | Description                                         |
| -------------------------------------------------------- | ------- | ------------------------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| `crowdsec_alerts`                                        | Gauge   | `scenario`, `simulated`, `remediation`                                                                        | Currently active alerts aggregated by scenario      |
| `crowdsec_alerts_details`                                | Gauge   | `alertIdentifier`, `uuid`, `machineId`, `createdAt`, `scenario`, `country`, `ip`, `asName`, `decisionType`, … | One entry per alert with full geo and source detail |
| `crowdsec_alerts_fetched_total`                          | Counter | –                                                                                                             | Total alerts fetched since exporter start           |
| `crowdsec_last_successful_alerts_poll_timestamp_seconds` | Gauge   | `endpoint`                                                                                                    | Unix timestamp of last successful poll              |

### Allowlists (`GET /v1/allowlists`)

| Metric                                                       | Type    | Labels                                                                   | Description                                        |
| ------------------------------------------------------------ | ------- | ------------------------------------------------------------------------ | -------------------------------------------------- |
| `crowdsec_allowlists_items`                                  | Gauge   | `name`, `allowlistId`, `consoleManaged`                                  | Number of active (non-expired) items per allowlist |
| `crowdsec_allowlist_items_detail`                            | Gauge   | `allowlistId`, `name`, `value`, `description`, `expiration`, `isExpired` | One entry per allowlist item with expiry state     |
| `crowdsec_allowlist_expiring_items`                          | Gauge   | `name`, `allowlistId`, `consoleManaged`                                  | Items expiring within 24 hours                     |
| `crowdsec_allowlists_fetched_total`                          | Counter | –                                                                        | Total allowlists fetched since exporter start      |
| `crowdsec_last_successful_allowlists_poll_timestamp_seconds` | Gauge   | `endpoint`                                                               | Unix timestamp of last successful poll             |

### Exporter health

| Metric                       | Type    | Labels                   | Description               |
| ---------------------------- | ------- | ------------------------ | ------------------------- |
| `crowdsec_poll_errors_total` | Counter | `endpoint`, `error_type` | Failed LAPI poll attempts |
| `crowdsec_exporter_info`     | Info    | `version`, `git_commit`  | Build metadata            |

---

## Environment variables

| Variable                | Required | Default   | Description                                                       |
| ----------------------- | -------- | --------- | ----------------------------------------------------------------- |
| `CROWDSEC_LAPI_URL`     | ✓        | –         | e.g. `http://crowdsec.crowdsec-monitoring.svc.cluster.local:8080` |
| `CROWDSEC_API_KEY`      | ✓        | –         | Bouncer API key – read-only, injected via Kubernetes Secret       |
| `METRICS_PORT`          |          | `8000`    | Port for the `/metrics` HTTP endpoint                             |
| `METRICS_HOST`          |          | `0.0.0.0` | Bind address (NetworkPolicy restricts inbound)                    |
| `POLL_INTERVAL_SECONDS` |          | `60`      | Polling interval in seconds                                       |
| `LOG_LEVEL`             |          | `INFO`    | `DEBUG` / `INFO` / `WARNING` / `ERROR`                            |
| `APP_VERSION`           |          | `unknown` | Injected via `--build-arg` at image build time                    |
| `GIT_COMMIT`            |          | `unknown` | Injected via `--build-arg` at image build time                    |

---

## Logging

All log output is structured JSON to `stdout` – compatible with Kubernetes log collection and Loki.

Every log line contains at minimum:

| Field       | Example                | Description                                              |
| ----------- | ---------------------- | -------------------------------------------------------- |
| `timestamp` | `2026-07-14T09:40:46Z` | ISO 8601 UTC                                             |
| `level`     | `info`                 | `debug` / `info` / `warning` / `error`                   |
| `logger`    | `src.collector`        | Python module                                            |
| `event`     | `pollSuccess`          | Machine-readable event type (stable – use as Loki label) |

Sensitive fields (`apiKey`, `token`, `secret`, `password`) are automatically masked with `***` before serialisation.

### Key log events

| `event`                  | Level | Description                                           |
| ------------------------ | ----- | ----------------------------------------------------- |
| `startup`                | info  | Process started, config loaded                        |
| `collector_initialised`  | info  | HTTP session created, LAPI URL confirmed              |
| `metricsServerStarted`   | info  | `/metrics` endpoint is listening                      |
| `pollStart`              | debug | Beginning a LAPI request                              |
| `pollSuccess`            | info  | LAPI request completed successfully                   |
| `pollFailed`             | error | LAPI request failed – check `error_type` and `detail` |
| `pollEmpty`              | debug | LAPI returned 204 (no active items)                   |
| `decision_observed`      | debug | Individual decision seen during aggregation           |
| `alertsObserved`         | debug | Individual alert seen during aggregation              |
| `allowlistsGaugeUpdated` | debug | Allowlist metrics written                             |
| `shutdownSignalReceived` | info  | SIGTERM or SIGINT received                            |
| `shutdownComplete`       | info  | Clean exit                                            |

---

## Build

### Production image (distroless)

```bash
docker build \
  --secret id=corporate_ca,src=/etc/ssl/certs/ca-certificates.crt \
  --build-arg APP_VERSION=1.0.0 \
  --build-arg GIT_COMMIT=$(git rev-parse --short HEAD) \
  -t crowdsec-exporter:1.0.0 \
  .
```

The production image uses `gcr.io/distroless/python3-debian12:nonroot`:
- No shell, no package manager → minimal attack surface
- Runs as uid 65532 (nonroot) → satisfies `runAsNonRoot: true`
- Multi-stage build → only application code and locked dependencies in final image

### Validate the build

```bash
# Config validation fires (expected: FATAL config error – no env vars set)
docker run --rm crowdsec-exporter:1.0.0

# No shell available (expected: error)
docker run --rm crowdsec-exporter:1.0.0 sh

# Check image size
docker images crowdsec-exporter
```

---

## Local development

The `dev/` directory contains a complete local stack with a mock CrowdSec LAPI, Prometheus, and Grafana.

### Prerequisites

- Docker with BuildKit enabled (`export DOCKER_BUILDKIT=1` or set in `/etc/docker/daemon.json`)
- Corporate CA registered: `sudo cp your-ca.crt /usr/local/share/ca-certificates/ && sudo update-ca-certificates`

### Start the dev stack

```bash
cd dev/
docker compose up --build
```

| URL                                | Service                              |
| ---------------------------------- | ------------------------------------ |
| http://localhost:3000              | Grafana (`admin` / `dev-grafana-pw`) |
| http://localhost:9090              | Prometheus                           |
| http://localhost:8000/metrics      | Exporter metrics (direct)            |
| http://localhost:8080/v1/decisions | Mock CrowdSec LAPI                   |

### Iteration workflow

```bash
# Code changed (src/) → restart only, no rebuild needed
docker compose restart exporter

# requirements.txt changed → rebuild
docker compose up --build exporter

# View live logs
docker compose logs -f exporter

# Manual LAPI test
curl -H "X-Api-Key: dev-bouncer-key-12345" http://localhost:8080/v1/decisions | jq .

# Check metrics
curl -s http://localhost:8000/metrics | grep crowdsec

# Tear down and clean volumes
docker compose down -v
```

---

## Security

**Secrets:** The bouncer API key (`CROWDSEC_API_KEY`) is a read-only credential. In Kubernetes, inject it via an `ExternalSecret` (External Secrets Operator) referencing Vault or a similar secret store. Never put it in `values.yaml` or commit it to Git.

**Container hardening (Kubernetes):**
```yaml
securityContext:
  runAsNonRoot: true
  readOnlyRootFilesystem: true
  allowPrivilegeEscalation: false
  capabilities:
    drop: ["ALL"]
automountServiceAccountToken: false
```

**Network:** The exporter requires only two network paths:
- Egress to CrowdSec LAPI on port 8080
- Ingress from Prometheus on port 8000

All other traffic should be denied via `NetworkPolicy`.

---

## Dependency management

Direct dependencies are listed in `requirements.in`. Locked, hashed versions are in `requirements.txt` (generated by `pip-compile`).

```bash
pip-compile --generate-hashes requirements.in
```

### Dependencies

| Package             | Purpose                   | Maintained by     |
| ------------------- | ------------------------- | ----------------- |
| `prometheus_client` | Metrics exposition        | Prometheus / CNCF |
| `requests`          | CrowdSec LAPI HTTP client | Python community  |
| `structlog`         | Structured JSON logging   | Hynek Schlawack   |

---

## Project structure

```
.
├── src/
│   ├── main.py           # Entry point – startup, signal handling, HTTP server
│   ├── config.py         # Configuration from environment variables
│   ├── collector.py      # Prometheus Collector – polls LAPI, yields metrics
│   ├── logger.py         # structlog JSON logging setup
│   ├── metrics.py        # Prometheus MetricFamily definitions
│   └── models/
│       ├── _base.py      # Shared parse helpers (strField, boolField, …)
│       ├── decision.py   # Decision dataclass + metricLabels/metricDetails
│       ├── alert.py      # Alert, AlertSource, AlertEvent dataclasses
│       ├── allowlist.py  # Allowlist, AllowlistItem dataclasses
│       ├── parser.py     # parseDecisions / parseAlerts / parseAllowlists
│       └── __init__.py   # Public re-exports
├── dev/
│   ├── docker-compose.yaml
│   ├── .env              # Dev secrets (never commit)
│   ├── mock-crowdsec/    # Stdlib Python mock LAPI server
│   ├── prometheus/       # Minimal scrape config
│   └── grafana/          # Auto-provisioned Prometheus datasource
├── Dockerfile            # Production – distroless, multi-stage
├── Dockerfile.dev        # Development – python:slim, volume-mounted source
├── requirements.in       # Direct dependencies
├── requirements.txt      # Locked + hashed (generated by pip-compile)
└── .dockerignore
```
