from prometheus_client.metrics_core import GaugeMetricFamily, CounterMetricFamily, InfoMetricFamily

from models import Decision, Allowlist, AllowlistItem, Alert

# --- Decisions ---
def decisions() -> GaugeMetricFamily:
    return GaugeMetricFamily(
        "crowdsec_decisions",
        "Number of currently active CrowdSec decisions",
        labels=Decision.metric_labels(),
    )

def decisions_total() -> CounterMetricFamily:
    return CounterMetricFamily(
        "crowdsec_decisions_total",
        "Total decisions by offender",
        labels=Alert.total_metric_labels()
    )

# --- Alerts ---
def alerts() -> GaugeMetricFamily :
    return GaugeMetricFamily(
        "crowdsec_alerts",
        "Details of currently active CrowdSec alerts",
        labels=Alert.metric_labels(),
    )

def alerts_total() -> CounterMetricFamily:
    return CounterMetricFamily(
        "crowdsec_alerts_total",
        "Total alerts fetched from /v1/alerts since exporter start",
        labels=Alert.total_metric_labels()
    )

def alert_created() -> GaugeMetricFamily:
    return GaugeMetricFamily(
        "crowdsec_alert_created",
        "Timestamp of the creation of each CrowdSec alert",
        labels=Alert.created_metric_labels(),
    )

def alert_start() -> GaugeMetricFamily:
    return GaugeMetricFamily(
        "crowdsec_alert_start",
        "Timestamp of the start of each CrowdSec alert",
        labels=Alert.start_metric_labels(),
    )

def alert_stop() -> GaugeMetricFamily:
    return GaugeMetricFamily(
        "crowdsec_alert_stop",
        "Timestamp of the stop of each CrowdSec alert",
        labels=Alert.stop_metric_labels(),
    )
def alert_events_count() -> GaugeMetricFamily:
    return GaugeMetricFamily(
        "crowdsec_alert_events_count",
        "Number of events for each CrowdSec alert",
        labels=Alert.events_count_metric_labels(),
    )
def alert_decisions_count() -> GaugeMetricFamily:
    return GaugeMetricFamily(
        "crowdsec_alert_decisions_count",
        "Number of decisions for each CrowdSec alert",
        labels=Alert.decisions_count_metric_labels(),
    )
# --- Events ---
def alert_events_count_total() -> CounterMetricFamily:
    return CounterMetricFamily(
        "crowdsec_events_total",
        "Total number of events for each CrowdSec alert",
        labels=Alert.total_metric_labels(),
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
        labels=Allowlist.created_metric_labels(),
    )

def allowlist_updated() -> GaugeMetricFamily:
    return GaugeMetricFamily(
        "crowdsec_allowlist_updated",
        "Timestamp of the last update of each CrowdSec allowlist",
        labels=Allowlist.updated_metric_labels(),
    )

def allowlist_console_managed() -> GaugeMetricFamily:
    return GaugeMetricFamily(
        "crowdsec_allowlist_console_managed",
        "Indicates whether each CrowdSec allowlist is console managed",
        labels=Allowlist.console_managed_metric_labels(),
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
