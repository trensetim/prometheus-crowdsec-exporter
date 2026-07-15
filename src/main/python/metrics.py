from prometheus_client.metrics_core import GaugeMetricFamily, CounterMetricFamily, InfoMetricFamily

from models import Decision

# --- Descions ---
def decisions() -> GaugeMetricFamily:
    return GaugeMetricFamily(
        "crowdsec_decisions",
        "Number of currently active CrowdSec decisions",
        labels = Decision.metric_labels(),
    )

def decisions_total(current_total: int) -> CounterMetricFamily:
    m = CounterMetricFamily(
        "crowdsec_decisions_total",
        "Total decisions fetched from /v1/decisions since exporter start"
    )
    m.add_metric([], current_total)
    return m

def createLastSuccessfulDecisionPollTimestamp() -> CounterMetricFamily:
    return GaugeMetricFamily(
        "crowdsec_last_successful_decision_poll_timestamp_seconds",
        "Unix timestamp (UTC) of the last successful poll per endpoint",
        labels=["endpoint"],
    )

def createDecisionPollErrorsTotal() -> CounterMetricFamily:
    return CounterMetricFamily(
        "crowdsec_poll_errors_total",
        "Total failed LAPI poll attempts",
        labels=["endpoint", "error_type"],
    )

# --- Alerts ---
def createActiveAlerts() -> GaugeMetricFamily :
    return GaugeMetricFamily(
        "crowdsec_alerts",
        "Number of currently active CrowdSec alerts",
        labels=["scenario", "simulated", "remediation"],
    )

def createActiveAlertsDetails() -> GaugeMetricFamily :
    return GaugeMetricFamily(
        "crowdsec_alerts_details",
        "Details of currently active CrowdSec alerts",
        labels=["alertId","uuid","machineId","createdAt","startAt","stopAt","scenario","scenarioHash","scenarioVersion","eventsCount","simulated","remediation","ip","subnet","country","asNumber","asName","latitude","longitude","decisionType","decisionScope",],
    )

def createAlertsFetchedTotal() -> CounterMetricFamily:
    return CounterMetricFamily(
        "crowdsec_alerts_fetched_total",
        "Total alerts fetched from /v1/alerts since exporter start. "
        "Use rate() for alert spike detection.",
    )

def createLastSuccessfulAlertsPollTimestamp() -> CounterMetricFamily:
    return GaugeMetricFamily(
        "crowdsec_last_successful_alerts_poll_timestamp_seconds",
        "Unix timestamp (UTC) of the last successful poll per endpoint",
        labels=["endpoint"],
    )

def createAlertsPollErrorsTotal() -> CounterMetricFamily:
    return CounterMetricFamily(
        "crowdsec_poll_errors_total",
        "Total failed LAPI poll attempts",
        labels=["endpoint", "errorType"],
    )

# --- Allowlists ---
def createActiveAllowlists() -> GaugeMetricFamily :
    return GaugeMetricFamily(
        "crowdsec_allowlists_items",
        "Number of active (non-expired) items in each CrowdSec allowlist",
        labels=["name", "allowlistId", "consoleManaged", "description", "createdAt", "updatedAt"],
    )

def createAllowlistItems() -> GaugeMetricFamily:
    return GaugeMetricFamily(
        "crowdsec_allowlist_items_detail",
        "Detail information for each allowlist item",
        labels=["allowlistId", "name", "value", "description", "expiration", "isExpired"],
    )

def createAllowlistsExpiringItems() -> CounterMetricFamily:
    return GaugeMetricFamily(
        "crowdsec_allowlist_expiring_items",
        "Number of allowlist items expiring within the configured threshold window",
        labels=["name", "allowlistId", "consoleManaged"],
    )

def createAllowlistsFetchedTotal() -> CounterMetricFamily:
    return CounterMetricFamily(
        "crowdsec_allowlists_fetched_total",
        "Total allowlists fetched from /v1/allowlists since exporter start. "
        "Use rate() for 'new allowlists per second' - cannot be derived from the Gauge.",
    )

def createLastSuccessfulAllowlistsPollTimestamp() -> CounterMetricFamily:
    return GaugeMetricFamily(
        "crowdsec_last_successful_allowlists_poll_timestamp_seconds",
        "Unix timestamp (UTC) of the last successful poll per endpoint",
        labels=["endpoint"],
    )

# --- Exporter infos ---
def createExporterInfo() -> InfoMetricFamily:
    return InfoMetricFamily(
        "crowdsec_exporter",
        "Static build and version metadata for this exporter instance. "
        "Use in dashboard title: 'Version: {{ crowdsec_exporter_info }}'",
    )

def polls_total(current_total: int) -> CounterMetricFamily:
    c = CounterMetricFamily(
        "crowdsec_polls_total",
        "Total attempted LAPI polls (successes + failures) since exporter start.",
    )
    c.add_metric([], current_total)
    return c

def poll_errors_total(current_total: int) -> CounterMetricFamily:
    c = CounterMetricFamily(
        "crowdsec_poll_errors_total",
        "Total failed LAPI poll attempts",
    )
    c.add_metric([], current_total)
    return c

def last_poll_duration_seconds(value: float) -> GaugeMetricFamily:
    g = GaugeMetricFamily(
        "crowdsec_last_poll_duration_seconds",
        "Duration of the last LAPI poll in seconds (covering all endpoints)",
    )
    g.add_metric([], value)
    return g
