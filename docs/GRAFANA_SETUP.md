# Grafana Dashboard Setup - Dyno-Agent

## Problem: Empty Dashboard

If your Grafana dashboard is empty, follow this guide to configure it correctly.

## Implemented Solution

### 1. Automatic Configuration (Provisioning)

The system now includes **automatic Grafana provisioning**:

```yaml
# docker-compose.yml - Updated configuration
grafana:
  image: grafana/grafana:latest
  environment:
    - GF_PATHS_PROVISIONING=/etc/grafana/provisioning
  volumes:
    - ./monitoring/grafana/provisioning:/etc/grafana/provisioning
    - ./monitoring/grafana/dashboards:/etc/grafana/dashboards
```

### 2. File Structure

```
monitoring/
├── grafana/
│   ├── provisioning/
│   │   ├── datasources/
│   │   │   └── prometheus.yml      # Configures Prometheus automatically
│   │   └── dashboards/
│   │       └── dashboard.yml       # Configures dashboard import
│   └── dashboards/
│       └── dyno-agent.json         # Main dashboard
├── prometheus.yml
└── grafana-dashboard.json          # Old dashboard (kept for compatibility)
```

## How to Use

### Restart with New Configuration

```bash
# Stop services
make stop
# or
docker-compose down

# Remove Grafana volume (to recreate configuration)
docker volume rm dyno-agent_grafana-storage

# Start again
make run
# or
docker-compose up -d
```

### Verify Configuration

```bash
# Access Grafana
open http://localhost:3000
# Login: admin / admin

# Check if Prometheus is configured
# Grafana > Configuration > Data Sources
# Should show "Prometheus" as default

# Check dashboard
# Grafana > Dashboards > Browse
# Should show "Dyno-Agent Production Metrics"
```

## Available Metrics

### Main Dashboard: "Dyno-Agent Production Metrics"

**Included panels:**

1. **Allocation Success Rate** - Success rate of allocations
2. **Response Time (P95)** - 95th percentile response time
3. **Active Users** - Active users in the system
4. **Monthly Cost Savings** - Monthly savings in USD
5. **Request Rate Over Time** - Request rate over time
6. **Response Time Distribution** - Response time distribution (P50, P95, P99)

### Available Prometheus Metrics

```promql
# Request rate by status
rate(dyno_allocation_requests_total[5m])

# Response time (percentiles)
histogram_quantile(0.95, rate(dyno_allocation_duration_seconds_bucket[5m]))

# Active users
dyno_active_users

# Cost savings
dyno_cost_savings_usd

# Monthly hours saved
dyno_monthly_hours_saved
```

## Troubleshooting

### Dashboard Still Empty?

**SOLUTION 1: Fixed Volume Mount Path**

The issue was in the docker-compose.yml configuration. The dashboard volume was mounted to `/var/lib/grafana/dashboards` but the provisioning config was looking at `/etc/grafana/dashboards`.

**SOLUTION 2: Fixed Dashboard JSON Structure**

The dashboard JSON had a nested `{"dashboard": {}}` structure, but Grafana provisioning expects the dashboard object directly.

**Fixed configuration:**
```yaml
# Correct volume mount
- ./monitoring/grafana/dashboards:/etc/grafana/dashboards

# Provisioning config (dashboard.yml)
options:
  path: /etc/grafana/dashboards
```

**To apply both fixes:**
```bash
# Stop services
docker-compose down

# Remove Grafana volume
docker volume rm dyno-agent_grafana-storage

# Start again
docker-compose up -d

# Wait 30 seconds for provisioning
sleep 30

# Access Grafana
open http://localhost:3000
```

**Expected result:** Dashboard "Dyno-Agent Production Metrics" should appear automatically in Grafana > Dashboards > Browse.

1. **Check if Prometheus is collecting metrics:**
```bash
# Access Prometheus
open http://localhost:9090

# Check targets
# Status > Targets
# dyno-agent should be "UP"

# Test query
# Graph > Execute: dyno_allocation_requests_total
```

2. **Check if the application is exposing metrics:**
```bash
# Test metrics endpoint
curl http://localhost:8000/metrics/prometheus

# Should return metrics in Prometheus format
```

3. **Check Grafana logs:**
```bash
docker logs dyno_grafana
```

4. **Check Prometheus logs:**
```bash
docker logs dyno_prometheus
```

### Generate Test Data

To populate the dashboard with data, use the automated script:

```bash
# Complete script to setup dashboard
./scripts/setup_dashboard.sh

# Or manually:
# 1. Update business metrics
curl -X POST "http://localhost:8000/metrics/update-business" \
  -H "Content-Type: application/json" \
  -d '{"hours_saved": 127.5, "cost_savings": 63750, "active_users": 15}'

# 2. Generate request metrics
python3 scripts/populate_metrics.py

# 3. Restart Grafana
docker restart dyno_grafana
```

### Manual Configuration (Fallback)

If automatic provisioning doesn't work:

1. **Add Data Source manually:**
   - Grafana > Configuration > Data Sources > Add data source
   - Select "Prometheus"
   - URL: `http://prometheus:9090`
   - Save & Test

2. **Import Dashboard manually:**
   - Grafana > Dashboards > Import
   - Upload JSON file: `monitoring/grafana/dashboards/dyno-agent.json`
   - Select Prometheus as data source

## Customization

### Add New Panels

Edit `/monitoring/grafana/dashboards/dyno-agent.json`:

```json
{
  "id": 10,
  "title": "Your New Panel",
  "type": "stat",
  "targets": [
    {
      "expr": "your_prometheus_metric",
      "legendFormat": "Label"
    }
  ],
  "gridPos": {"h": 8, "w": 6, "x": 0, "y": 25}
}
```

### Add New Metrics

In Python code, use the decorator:

```python
from core.metrics import track_performance

@track_performance(service_name="YourService")
async def your_method(self):
    # Your logic here
    return result
```

Metrics will automatically appear in Prometheus as:
- `dyno_allocation_requests_total{service="YourService"}`
- `dyno_allocation_duration_seconds{service="YourService"}`

## Next Steps

1. **Alerts**: Configure Grafana alerts for critical metrics
2. **Additional Dashboards**: Create service-specific dashboards
3. **Business Metrics**: Add more ROI and impact metrics
4. **CloudWatch Integration**: For AWS production environments

---

**Expected Result**: Functional dashboard with real-time metrics from the Dyno-Agent system.