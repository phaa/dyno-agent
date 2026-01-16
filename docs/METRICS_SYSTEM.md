# Metrics & Observability System

## Overview

The Dyno-Agent metrics system provides comprehensive instrumentation for production monitoring, business intelligence, and performance optimization. This system demonstrates enterprise-grade observability practices essential for senior-level AI engineering roles.

## Production Monitoring Architecture

### Deployment Options

The system offers **two production monitoring strategies** to accommodate different organizational needs and budgets:

**Option 1: Prometheus + Grafana (Cost-Effective)**
- **Deployment**: ECS Fargate containers with EFS persistent storage
- **Cost**: ~$50/month (ECS + EFS)
- **Access**: `http://your-alb.amazonaws.com/grafana` and `/prometheus`
- **Benefits**: Full customization, advanced PromQL queries, cost-effective

**Option 2: AWS CloudWatch (Enterprise)**
- **Deployment**: Native AWS integration via boto3
- **Cost**: ~$1,500/month (high-frequency metrics)
- **Access**: AWS Console CloudWatch dashboards
- **Benefits**: Enterprise integration, native AWS features, managed service

**Option 3: Hybrid Approach (Recommended)**
- **Strategy**: Prometheus for operational metrics + CloudWatch for business metrics
- **Cost**: ~$200/month
- **Benefits**: Best of both worlds - cost optimization + enterprise features

### Production Infrastructure

The code below is a simplified version of the actual code.
>  For more detailed implementation see: ``infra/monitoring.tf``

```hcl
# EFS for persistent monitoring data
resource "aws_efs_file_system" "monitoring" {
  creation_token = "${var.project_name}-monitoring-efs"
  performance_mode = "generalPurpose"
  encrypted = true
}

# Prometheus ECS service with persistent storage
resource "aws_ecs_task_definition" "prometheus" {
  family = "${var.project_name}-prometheus"
  
  volume {
    name = "prometheus-data"
    efs_volume_configuration {
      file_system_id     = aws_efs_file_system.monitoring.id
      access_point_id    = aws_efs_access_point.prometheus.id
      transit_encryption = "ENABLED"
    }
  }
  
  container_definitions = jsonencode([{
    name  = "prometheus"
    image = "prom/prometheus:latest"
    command = [
      "--web.route-prefix=/prometheus",
      "--storage.tsdb.retention.time=30d"
    ]
    # ... mount points and configuration
  }])
}

# ALB routing for secure access
resource "aws_lb_listener_rule" "prometheus" {
  condition {
    path_pattern {
      values = ["/prometheus*"]
    }
  }
}
```

### Access Production Monitoring

```bash
# After Terraform deployment
terraform output grafana_url
terraform output prometheus_url

# Direct access
open http://your-alb-endpoint.amazonaws.com/grafana    # admin/admin
open http://your-alb-endpoint.amazonaws.com/prometheus

# CloudWatch alternative
# AWS Console > CloudWatch > Dashboards > DynoAgent/Production
```

---

## Business Value Demonstration

### Quantified Impact Metrics

The metrics system enables precise measurement of business value:

```python
# Real production metrics from Ford deployment
{
  "total_successful_allocations": 2847,
  "avg_allocation_time_ms": 156.7,
  "estimated_time_saved_hours": 189.8,
  "monthly_cost_savings": 47500,
  "conflict_elimination_rate": 100.0,
  "user_adoption_rate": 95.2
}
```

### ROI Calculation Framework

Althoug not implemented yet in my personal version, the ROI calculation framework already exists in real the life project. 
For now I'll keep it here for demonstration purposes until I finish this part.

```python
async def calculate_roi_metrics(self) -> Dict[str, float]:
    """
    Automated ROI calculation based on real usage data:
    
    Before: 4-6 hours/week manual Excel work per engineer
    After: 2 minutes automated allocation per request
    
    Savings: ~4 hours × 25 engineers × $50/hour = $5,000/week
    Annual: $260,000 in labor cost savings
    Development cost: $50,000
    ROI: 520% first year
    """
    
    # Query actual usage metrics
    total_allocations = await self.get_successful_allocations_count()
    avg_time_saved_per_allocation = 4 * 60  # 4 minutes in seconds
    engineer_hourly_rate = 50 # Due to compliance reasons, I will use just an example value.
    
    total_time_saved_hours = (total_allocations * avg_time_saved_per_allocation) / 3600
    cost_savings = total_time_saved_hours * engineer_hourly_rate
    
    return {
        "total_allocations": total_allocations,
        "time_saved_hours": total_time_saved_hours,
        "cost_savings_usd": cost_savings,
        "roi_percentage": (cost_savings / 50000) * 100  # vs development cost
    }
```

---

## Technical Implementation

### Automatic Performance Instrumentation

```python
# app/services/allocation_service.py
@track_performance(service_name="AllocationService", include_metadata=True)
async def auto_allocate_vehicle_core(
    self, 
    vehicle_id: int, 
    start_date: date, 
    days_to_complete: int = 1
):
    """
    Decorator automatically captures:
    - Execution duration (ms)
    - Success/failure status
    - Error messages and stack traces
    - Business metadata (backup usage, conflict resolution)
    - User context and correlation IDs
    """
    # Business logic here...
    return allocation_result
```

### Metrics Database Schema

```python
# app/models/metrics.py
class Metrics(Base):
    __tablename__ = "metrics"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    correlation_id: Mapped[str] = mapped_column(
        String,
        index=True
    )

    service_name: Mapped[str] = mapped_column(
        String,
        index=True
    )

    method_name: Mapped[str] = mapped_column(
        String,
        index=True
    )

    user_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True
    )

    # Performance metrics
    duration_ms: Mapped[float] = mapped_column(
        Float
    )

    success: Mapped[bool] = mapped_column(
        Boolean
    )

    error_message: Mapped[str | None] = mapped_column(
        String,
        nullable=True
    )

    # Business metrics
    extra_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True
    )
```

```sql
-- This python code outputs a this SQL
CREATE TABLE metrics (
    id SERIAL PRIMARY KEY,
    correlation_id VARCHAR(36) NOT NULL,
    service_name VARCHAR(100) NOT NULL,
    method_name VARCHAR(100) NOT NULL,
    user_id INTEGER,
    
    -- Performance metrics
    duration_ms FLOAT NOT NULL,
    success BOOLEAN NOT NULL,
    error_message TEXT,
    
    -- Business intelligence
    metadata JSONB,
    
    -- Time series
    created_at TIMESTAMP DEFAULT NOW()
);

-- Optimized indexes for analytics queries
CREATE INDEX idx_metrics_service_method ON metrics(service_name, method_name);
CREATE INDEX idx_metrics_created_at ON metrics(created_at);
CREATE INDEX idx_metrics_correlation_id ON metrics(correlation_id);
CREATE INDEX idx_metrics_user_performance ON metrics(user_id, created_at, success);
```

### Correlation ID Tracking

```python
# app/core/metrics.py
def track_performance(service_name: Optional[str] = None, include_metadata: bool = False):
    """
    Production-grade decorator with correlation tracking:
    
    1. Generates unique correlation ID per request
    2. Tracks execution across service boundaries
    3. Enables end-to-end request tracing
    4. Non-blocking metrics recording
    """
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            correlation_id = str(uuid.uuid4())
            start_time = time.time()
            
            try:
                # Execute business logic
                result = await func(*args, **kwargs)
                success = True
                
                # Extract business metadata
                metadata = {}
                if include_metadata and isinstance(result, dict):
                    metadata = {
                        'result_keys': list(result.keys()),
                        'success_flag': result.get('success', None),
                        'backup_used': result.get('backup_used', False),
                        'allocation_id': result.get('allocation', {}).get('allocation_id')
                    }
                
                return result
                
            except Exception as e:
                success = False
                error_message = str(e)
                
                # Structured error logging
                logger.error(
                    f"Method failed: {service_name}.{func.__name__}",
                    extra={
                        'correlation_id': correlation_id,
                        'error_type': type(e).__name__,
                        'error_message': error_message,
                        'stack_trace': traceback.format_exc()
                    }
                )
                raise
                
            finally:
                duration_ms = (time.time() - start_time) * 1000
                
                # Async metrics recording (fire-and-forget)
                asyncio.create_task(
                    record_metric_async(
                        correlation_id=correlation_id,
                        service_name=service_name or args[0].__class__.__name__,
                        method_name=func.__name__,
                        duration_ms=duration_ms,
                        success=success,
                        error_message=error_message if not success else None,
                        metadata=metadata if metadata else None
                    )
                )
        
        return wrapper
    return decorator

# Any new service
from core.metrics import track_performance

class YourNewService:
    @track_performance(service_name="YourNewService", include_metadata=True)
    async def your_method(self, param1: str, param2: int):
        """Automatically tracked: duration, success rate, errors"""
        result = await self.business_logic(param1, param2)
        return {"success": True, "data": result}
```

### Automatic Collection
The decorator captures:
- ✅ Execution time (ms)
- ✅ Success/failure rates  
- ✅ Error messages and types
- ✅ Correlation IDs for tracing
- ✅ Business metadata (optional)

### View Results
```bash
# Prometheus metrics
curl http://localhost:8000/metrics/prometheus | grep your_service

# Grafana dashboard
open http://localhost:3000  # admin/admin

# Performance API
curl -H "Authorization: Bearer TOKEN" \
  http://localhost:8000/metrics/performance
```

That's it! Your service is now fully instrumented with enterprise-grade monitoring.\n