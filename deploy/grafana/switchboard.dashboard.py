from grafanalib.core import Dashboard, GridPos, Target, Time, TimeSeries

request_rate = TimeSeries(
    title="Request rate by route",
    targets=[
        Target(
            expr="sum(rate(sb_requests_total[5m])) by (route)",
            legendFormat="{{route}}",
        )
    ],
    gridPos=GridPos(h=8, w=12, x=0, y=0),
    unit="reqps",
)

error_rate = TimeSeries(
    title="5xx error rate by route",
    targets=[
        Target(
            expr='sum(rate(sb_requests_total{status_class="5xx"}[5m])) by (route)',
            legendFormat="{{route}}",
        )
    ],
    gridPos=GridPos(h=8, w=12, x=12, y=0),
    unit="reqps",
)

# Deliberately NOT avg(p99 per instance). Percentiles don't average - an instance
# with 10 slow requests and one with 10,000 fast ones would count equally in a
# naive average, when the true fleet-wide p99 should be dominated by request
# volume, not instance count. This sums the raw histogram bucket RATES across
# every instance first (dropping the instance label via "by (le, route)"), then
# computes the quantile once from that combined distribution.
latency_p99 = TimeSeries(
    title="Request duration p50 / p95 / p99 by route (aggregated across instances)",
    targets=[
        Target(
            expr=(
                "histogram_quantile(0.50, sum(rate(sb_request_duration_seconds_bucket[5m])) "
                "by (le, route))"
            ),
            legendFormat="p50 {{route}}",
        ),
        Target(
            expr=(
                "histogram_quantile(0.95, sum(rate(sb_request_duration_seconds_bucket[5m])) "
                "by (le, route))"
            ),
            legendFormat="p95 {{route}}",
        ),
        Target(
            expr=(
                "histogram_quantile(0.99, sum(rate(sb_request_duration_seconds_bucket[5m])) "
                "by (le, route))"
            ),
            legendFormat="p99 {{route}}",
        ),
    ],
    gridPos=GridPos(h=8, w=12, x=0, y=8),
    unit="s",
)

cache_hit_ratio = TimeSeries(
    title="Cache hit ratio",
    targets=[
        Target(
            expr=(
                "sum(rate(sb_cache_hits_total[5m])) "
                "/ (sum(rate(sb_cache_hits_total[5m])) + sum(rate(sb_cache_misses_total[5m])))"
            ),
            legendFormat="hit ratio",
        )
    ],
    gridPos=GridPos(h=8, w=12, x=12, y=8),
    unit="percentunit",
)

cascade_escalation_ratio = TimeSeries(
    title="Cascade escalation ratio",
    targets=[
        Target(
            expr=(
                "sum(rate(sb_cascade_escalations_total[5m])) "
                "/ sum(rate(sb_cascade_requests_total[5m]))"
            ),
            legendFormat="escalation ratio",
        )
    ],
    gridPos=GridPos(h=8, w=12, x=0, y=16),
    unit="percentunit",
)

dashboard = Dashboard(
    title="Switchboard",
    description="RED metrics and cache performance for the Switchboard LLM gateway",
    tags=["switchboard"],
    timezone="utc",
    panels=[request_rate, error_rate, latency_p99, cache_hit_ratio, cascade_escalation_ratio],
    time=Time(start="now-6h", end="now"),
).auto_panel_ids()