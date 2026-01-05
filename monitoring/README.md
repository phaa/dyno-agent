# 📊 Monitoring Setup Guide

## Quick Start

```bash
# Start all services including monitoring
make run

# Check if metrics are being collected
make metrics

# Access dashboards
make grafana-url    # http://localhost:3000 (admin/admin)
make prometheus-url # http://localhost:9090
```

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI App   │───▶│   Prometheus    │───▶│    Grafana      │
│  (Port 8000)    │    │  (Port 9090)    │    │  (Port 3000)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │
         ▼
┌─────────────────┐
│   CloudWatch    │
│     (AWS)       │
└─────────────────┘
```

## Metrics Available

### Business Metrics
- `dyno_allocation_requests_total` - Total allocation requests by status
- `dyno_allocation_duration_seconds` - Request duration histogram
- `dyno_monthly_hours_saved` - Hours saved vs manual process
- `dyno_cost_savings_usd` - Monthly cost savings in USD
- `dyno_active_users` - Currently active users

### System Metrics
- Request rate and latency percentiles
- Success/error rates
- Active user count
- Business impact metrics

## Grafana Dashboard

The dashboard includes:
- **Request Rate**: Real-time allocation requests per second
- **Response Time**: 95th and 50th percentile latencies
- **Success Rate**: Percentage of successful requests
- **Active Users**: Current active user count
- **Cost Savings**: Monthly savings in USD
- **Request Volume**: Time series of request volume

## CloudWatch Integration

Metrics are automatically sent to AWS CloudWatch under namespace `DynoAgent/Production`:
- AllocationRequests (Count)
- AllocationDuration (Milliseconds)
- MonthlySavingsHours (Count)
- MonthlySavingsUSD (None)

## Prometheus Queries

```promql
# Request rate
rate(dyno_allocation_requests_total[5m])

# 95th percentile latency
histogram_quantile(0.95, rate(dyno_allocation_duration_seconds_bucket[5m]))

# Success rate
rate(dyno_allocation_requests_total{status="success"}[5m]) / rate(dyno_allocation_requests_total[5m]) * 100

# Error rate
rate(dyno_allocation_requests_total{status="error"}[5m]) / rate(dyno_allocation_requests_total[5m]) * 100
```

## Alerting (Future)

Recommended alerts:
- High error rate (>5%)
- High latency (>2s p95)
- Low success rate (<95%)
- Service down

## Troubleshooting

```bash
# Check if metrics endpoint is working
curl http://localhost:8000/metrics/prometheus

# Check Prometheus targets
curl http://localhost:9090/api/v1/targets

# View service logs
make logs-app
make logs-prometheus
make logs-grafana

# Restart monitoring stack
docker-compose restart prometheus grafana
```