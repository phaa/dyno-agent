import time
from typing import Optional, Any
from dataclasses import dataclass
from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest  
from prometheus_client.core import CollectorRegistry
import logging


@dataclass
class MetricsConfig:
    """Configuration for metrics storer"""
    registry: CollectorRegistry
    system_info: Info
    allocation_requests_total: Counter
    allocation_duration_seconds: Histogram
    active_users_gauge: Gauge
    monthly_hours_saved: Gauge
    cost_savings_usd: Gauge
    logger: logging.Logger
    cloudwatch: Optional[Any] = None
    

class MetricsStorer:
    """Enhanced metrics collector which stores metrics to Prometheus and CloudWatch backends"""
    
    def __init__(self, config: MetricsConfig):
        self.registry = config.registry
        self.system_info = config.system_info
        self.allocation_requests_total = config.allocation_requests_total
        self.allocation_duration_seconds = config.allocation_duration_seconds  
        self.active_users_gauge = config.active_users_gauge
        self.monthly_hours_saved = config.monthly_hours_saved
        self.cost_savings_usd = config.cost_savings_usd
        self.cloudwatch = config.cloudwatch
        self.logger = config.logger

        self.system_info.info({ 
            'version': '1.0.0',
            'environment': 'production',
            'service': 'dyno-agent'
        })
    
    def record_method_execution(
        self,
        service_name: str,
        method_name: str,
        duration_seconds: float,
        success: bool,
        user_id: Optional[int] = None
    ):
        """Record method execution metrics to Prometheus and CloudWatch"""
        
        status = 'success' if success else 'error'  
        
        # Add values to Prometheus
        self.allocation_requests_total.labels(  
            status=status, 
            service=service_name,
            method=method_name
        ).inc()
        
        self.allocation_duration_seconds.labels( 
            service=service_name,
            method=method_name
        ).observe(duration_seconds)  
        
        # Add values to CloudWatch - if configured
        if self.cloudwatch:
            try:
                self._send_to_cloudwatch([ 
                    { 
                        'MetricName': 'MethodExecutions',
                        'Value': 1, 
                        'Unit': 'Count',
                        'Dimensions': [  
                            {'Name': 'Status', 'Value': status},
                            {'Name': 'Service', 'Value': service_name}
                        ]
                    },
                    { 
                        'MetricName': 'MethodDuration',
                        'Value': duration_seconds * 1000,  # Convert to ms for CloudWatch
                        'Unit': 'Milliseconds',
                        'Dimensions': [
                            {'Name': 'Service', 'Value': service_name},
                            {'Name': 'Method', 'Value': method_name}
                        ]
                    }
                ])
            except Exception as e:
                self.logger.error(f"Failed to send metrics to CloudWatch: {e}")
    
    def update_business_metrics(self, hours_saved: float, cost_savings: float):
        """Update business intelligence metrics"""
        
        self.monthly_hours_saved.set(hours_saved)  
        self.cost_savings_usd.set(cost_savings) 
        
        # CloudWatch ROI metrics
        if self.cloudwatch:
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
                self.logger.error(f"Failed to send business metrics to CloudWatch: {e}")
    
    def update_active_users(self, count: int):
        """Update active users gauge"""
        self.active_users_gauge.set(count)
        
        # CloudWatch active users metric
        if self.cloudwatch:
            try:
                self._send_to_cloudwatch([
                    {
                        'MetricName': 'ActiveUsers',
                        'Value': count,
                        'Unit': 'Count'
                    }
                ])
            except Exception as e:
                self.logger.error(f"Failed to send active users metric to CloudWatch: {e}") 
    
    def _send_to_cloudwatch(self, metric_data: list):
        """Send metrics to CloudWatch"""
        if not self.cloudwatch: 
            return
            
        self.cloudwatch.put_metric_data(  
            Namespace='DynoAgent/Production',  # Namespace for metrics organizing
            MetricData=metric_data  
        )
    
    def get_prometheus_metrics(self) -> str:
        """Get Prometheus metrics in text format"""
        return generate_latest(self.registry) 