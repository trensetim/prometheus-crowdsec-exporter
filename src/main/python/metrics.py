from prometheus_client.metrics_core import GaugeMetricFamily, CounterMetricFamily, InfoMetricFamily

# --- Descions ---
def createActiveDecisions() -> GaugeMetricFamily :
    return GaugeMetricFamily(
        "crowdsec_decisions",
        "Number of currently active CrowdSec decisions",
        labels=["decision_type", "origin", "scenario", "scope"],
    )

def createActiveDecisionsDetails() -> GaugeMetricFamily :
    return GaugeMetricFamily(
        "crowdsec_decisions_details",
        "Details of currently active CrowdSec decisions",
        labels=[ "decision_type", "origin", "scenario", "scope", "val", "decisionId", "uuid", "duration", "until", "simulated"],
    )

def createDecisionsFetchedTotal() -> CounterMetricFamily:
    return CounterMetricFamily(
        "crowdsec_decisions_fetched_total",
        "Total decisions fetched from /v1/decisions since exporter start. "
        "Use rate() for 'new decisions per second' - cannot be derived from the Gauge.",
    )

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

def createAllowlistsPollErrorsTotal() -> CounterMetricFamily:
    return CounterMetricFamily(
        "crowdsec_poll_errors_total",
        "Total failed LAPI poll attempts",
        labels=["endpoint", "errorType"],
    )

# --- Exporter infos ---
def createExporterInfo() -> InfoMetricFamily:
    return InfoMetricFamily(
        "crowdsec_exporter",
        "Static build and version metadata for this exporter instance. "
        "Use in dashboard title: 'Version: {{ crowdsec_exporter_info }}'",
    )

def createPollErrorsTotal() -> InfoMetricFamily:
    return CounterMetricFamily(
        "crowdsec_poll_errors_total",
        "Total failed LAPI poll attempts",
        labels=["endpoint", "error_type"]
    )
