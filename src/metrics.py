from prometheus_client.metrics_core import GaugeMetricFamily, CounterMetricFamily, InfoMetricFamily

""" Descions """
def createActiveDecisions() -> GaugeMetricFamily :
    return GaugeMetricFamily(
        "crowdsec_decisions",
        "Number of currently active CrowdSec decisions",
        labels=["decision_type", "origin", "scenario", "scope"],
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


""" Exporter infos """
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
