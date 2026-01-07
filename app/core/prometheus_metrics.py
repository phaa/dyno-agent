from core.metrics_storer import MetricsStorer, MetricsConfig
from prometheus_client import Counter, Histogram, Gauge, Info
from prometheus_client.core import CollectorRegistry  
import boto3  
import logging

logger = logging.getLogger(__name__)

# Prometheus container for all metrics
REGISTRY = CollectorRegistry()

# Business Metrics
allocation_requests_total = Counter(  
    'dyno_allocation_requests_total', 
    'Total allocation requests',  
    ['status', 'service', 'method'],  # Labels for filtering (success/error, AllocationService, etc)
    registry=REGISTRY  # REgister on our container
)

allocation_duration_seconds = Histogram( 
    'dyno_allocation_duration_seconds', 
    'Allocation request duration in seconds', 
    ['service', 'method'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0],  # Buckets for P50, P95, etc
    registry=REGISTRY
)

active_users_gauge = Gauge( 
    'dyno_active_users',
    'Currently active users',
    registry=REGISTRY
)

system_info = Info(
    'dyno_agent_info',
    'System information',
    registry=REGISTRY
)

# Business Intelligence Metrics - ROI
monthly_hours_saved = Gauge(
    'dyno_monthly_hours_saved',
    'Monthly hours saved vs manual process',
    registry=REGISTRY
)

cost_savings_usd = Gauge(
    'dyno_cost_savings_usd',
    'Monthly cost savings in USD',
    registry=REGISTRY
)

# CloudWatch Client - for enterprise metrics
try:
    #cloudwatch = boto3.client('cloudwatch', region_name='us-east-1')
    pass
except Exception as e:
    logger.warning(f"CloudWatch client initialization failed: {e}")
    cloudwatch = None
finally:
    cloudwatch = None

metrics_storer = MetricsStorer(
    MetricsConfig(
        registry=REGISTRY,
        system_info=system_info,
        allocation_requests_total=allocation_requests_total,
        allocation_duration_seconds=allocation_duration_seconds,
        active_users_gauge=active_users_gauge,
        monthly_hours_saved=monthly_hours_saved,
        cost_savings_usd=cost_savings_usd,
        cloudwatch=cloudwatch,
        logger=logger
    )
)