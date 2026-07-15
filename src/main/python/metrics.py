from prometheus_client.metrics_core import GaugeMetricFamily, CounterMetricFamily, InfoMetricFamily

from models import Decision, Allowlist, AllowlistItem

# --- Decisions ---
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
def allowlists() -> GaugeMetricFamily:
    return GaugeMetricFamily(
        "crowdsec_allowlists",
        "Details about each CrowdSec allowlist",
        labels=Allowlist.metric_labels(),
    )

def allowlist_created() -> GaugeMetricFamily:
    return GaugeMetricFamily(
        "crowdsec_allowlist_created",
        "Timestamp of the creation of each CrowdSec allowlist",
        labels=Allowlist.metric_labels(),
    )

def allowlist_updated() -> GaugeMetricFamily:
    return GaugeMetricFamily(
        "crowdsec_allowlist_updated",
        "Timestamp of the last update of each CrowdSec allowlist",
        labels=Allowlist.metric_labels(),
    )

def allowlist_console_managed() -> GaugeMetricFamily:
    return GaugeMetricFamily(
        "crowdsec_allowlist_console_managed",
        "Indicates whether each CrowdSec allowlist is console managed",
        labels=Allowlist.console_managed_metrics_labels(),
    )

def allowlists_total(current_total: int) -> CounterMetricFamily:
    c = CounterMetricFamily(
        "crowdsec_allowlists_total",
        "Total number of CrowdSec allowlists fetched from /v1/allowlists since exporter start",
        labels=[],
    )
    c.add_metric([], current_total)
    return c

def allowlist_items() -> GaugeMetricFamily:
    return GaugeMetricFamily(
        "crowdsec_allowlist_items",
        "Detail information for each allowlist item",
        labels=AllowlistItem.metric_labels(),
    )
def allowlist_items_total(current_total: int) -> CounterMetricFamily:
    c = CounterMetricFamily(
        "crowdsec_allowlist_items_total",
        "Total number of CrowdSec allowlist items fetched from /v1/allowlists since exporter start",
        labels=[],
    )
    c.add_metric([], current_total)
    return c
def allowlist_item_created() -> GaugeMetricFamily:
    return GaugeMetricFamily(
        "crowdsec_allowlist_item_created",
        "Timestamp of the creation of each CrowdSec allowlist item",
        labels=AllowlistItem.created_metric_labels(),
    )
def allowlist_item_expiration() -> GaugeMetricFamily:
    return GaugeMetricFamily(
        "crowdsec_allowlist_item_expiration",
        "Timestamp of the expiration of each CrowdSec allowlist item (can be in the future or past)",
        labels=AllowlistItem.expiration_metric_labels(),
    )

# --- Exporter infos ---
def exporter_info(version: str) -> InfoMetricFamily:
    m = InfoMetricFamily(
        "crowdsec_exporter",
        "Static build and version metadata for this exporter instance",
    )
    m.add_metric(value={"version": version}, labels=[])
    return m

def polls_total(current_total: int) -> CounterMetricFamily:
    c = CounterMetricFamily(
        "crowdsec_polls_total",
        "Total attempted LAPI polls (successes + failures) since exporter start",
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
