import time
from typing import Optional, Dict, Any
from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest
from prometheus_client.core import CollectorRegistry
import boto3
import logging

logger = logging.getLogger(__name__)

# Prometheus Registry
REGISTRY = CollectorRegistry()

# Business Metrics
allocation_requests_total = Counter(
    'dyno_allocation_requests_total',
    'Total allocation requests',
    ['status', 'service', 'method'],
    registry=REGISTRY
)

allocation_duration_seconds = Histogram(
    'dyno_allocation_duration_seconds',
    'Allocation request duration in seconds',
    ['service', 'method'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
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

# Business Intelligence Metrics
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

# CloudWatch Client
try:
    cloudwatch = boto3.client('cloudwatch', region_name='us-east-1')
except Exception as e:
    logger.warning(f"CloudWatch client initialization failed: {e}")
    cloudwatch = None

class PrometheusMetricsCollector:
    """Enhanced metrics collector with Prometheus and CloudWatch integration"""
    
    def __init__(self):
        # Initialize system info
        system_info.info({
            'version': '1.0.0',
            'environment': 'production',
            'service': 'dyno-agent'
        })
    
    def record_allocation_request(
        self,
        service_name: str,
        method_name: str,
        duration_seconds: float,
        success: bool,
        user_id: Optional[int] = None
    ):
        """Record allocation metrics to Prometheus and CloudWatch"""
        
        status = 'success' if success else 'error'
        
        # Prometheus metrics
        allocation_requests_total.labels(
            status=status,
            service=service_name,
            method=method_name
        ).inc()
        
        allocation_duration_seconds.labels(
            service=service_name,
            method=method_name
        ).observe(duration_seconds)
        
        # CloudWatch metrics
        if cloudwatch:
            try:
                self._send_to_cloudwatch([
                    {
                        'MetricName': 'AllocationRequests',
                        'Value': 1,
                        'Unit': 'Count',
                        'Dimensions': [
                            {'Name': 'Status', 'Value': status},
                            {'Name': 'Service', 'Value': service_name}
                        ]
                    },
                    {
                        'MetricName': 'AllocationDuration',
                        'Value': duration_seconds * 1000,  # Convert to ms
                        'Unit': 'Milliseconds',
                        'Dimensions': [
                            {'Name': 'Service', 'Value': service_name},
                            {'Name': 'Method', 'Value': method_name}
                        ]
                    }
                ])
            except Exception as e:
                logger.error(f"Failed to send metrics to CloudWatch: {e}")
    
    def update_business_metrics(self, hours_saved: float, cost_savings: float):
        """Update business intelligence metrics"""
        
        monthly_hours_saved.set(hours_saved)
        cost_savings_usd.set(cost_savings)
        
        # CloudWatch business metrics
        if cloudwatch:
            try:
                self._send_to_cloudwatch([
                    {
                        'MetricName': 'MonthlySavingsHours',
                        'Value': hours_saved,
                        'Unit': 'Count'
                    },
                    {
                        'MetricName': 'MonthlySavingsUSD',
                        'Value': cost_savings,
                        'Unit': 'None'
                    }
                ])
            except Exception as e:
                logger.error(f"Failed to send business metrics to CloudWatch: {e}")
    
    def update_active_users(self, count: int):
        """Update active users gauge"""
        active_users_gauge.set(count)
    
    def _send_to_cloudwatch(self, metric_data: list):
        """Send metrics to CloudWatch"""
        if not cloudwatch:
            return
            
        cloudwatch.put_metric_data(
            Namespace='DynoAgent/Production',
            MetricData=metric_data
        )
    
    def get_prometheus_metrics(self) -> str:
        """Get Prometheus metrics in text format"""
        return generate_latest(REGISTRY)

# Global instance
prometheus_collector = PrometheusMetricsCollector()