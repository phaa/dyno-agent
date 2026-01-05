# Quick Start Guide - Monitoring Stack

## One-Command Setup

```bash
# Clone and start everything
git clone https://github.com/phaa/dyno-agent.git
cd dyno-agent
cp .env.example .env
# Edit .env with your API keys
make run
```

## Access Dashboards

```bash
# Grafana Dashboard (Business + Performance Metrics)
make grafana-url  # http://localhost:3000 (admin/admin)

# Prometheus (Raw Metrics)
make prometheus-url  # http://localhost:9090

# Check metrics endpoint
make metrics
```

## Troubleshooting

```bash
# Check if all services are running
make status

# View logs
make logs-app
make logs-prometheus
make logs-grafana

# Restart monitoring
docker-compose restart prometheus grafana
```