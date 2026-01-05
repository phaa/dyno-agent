# Adding Services to Metrics System

## Quick Guide: Instrumenting New Services

### 1. Add Decorator to Service Methods

```python
# services/your_new_service.py
from core.metrics import track_performance

class YourNewService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    @track_performance(service_name="YourNewService", include_metadata=True)
    async def your_method(self, param1: str, param2: int):
        """Method automatically tracked for performance"""
        # Your business logic here
        result = await self.do_something(param1, param2)
        return {"success": True, "data": result}
    
    @track_performance(service_name="YourNewService")
    async def another_method(self, param: str):
        """Simple tracking without metadata"""
        return await self.process(param)
```

### 2. Example: Adding Metrics to Validators Service

```python
# services/validators.py
from datetime import date
from core.metrics import track_performance

class BusinessRules: 
    MAX_ALLOCATION_DAYS = 30
    MIN_ALLOCATION_DAYS = 1

    @staticmethod
    @track_performance(service_name="BusinessRules")
    def validate_allocation_duration(start_date: date, end_date: date):
        duration = (end_date - start_date).days + 1
        if duration < BusinessRules.MIN_ALLOCATION_DAYS:
            raise ValueError(f"Allocation duration must be at least {BusinessRules.MIN_ALLOCATION_DAYS} day(s).")
        if duration > BusinessRules.MAX_ALLOCATION_DAYS:
            raise ValueError(f"Allocation duration cannot exceed {BusinessRules.MAX_ALLOCATION_DAYS} days.")
```

### 3. Automatic Metrics Collection

The decorator automatically captures:
- ✅ **Execution time** (milliseconds)
- ✅ **Success/failure rate**
- ✅ **Error messages** and types
- ✅ **Correlation IDs** for tracing
- ✅ **User context** (if available)
- ✅ **Business metadata** (if enabled)

### 4. View Metrics in Dashboards

```bash
# Check Prometheus metrics
curl http://localhost:8000/metrics/prometheus | grep your_new_service

# View in Grafana
open http://localhost:3000  # admin/admin

# API endpoint
curl -H "Authorization: Bearer TOKEN" \
  http://localhost:8000/metrics/performance?hours=24
```

### 5. Custom Business Metrics (Optional)

```python
# For special business logic tracking
from core.prometheus_metrics import prometheus_collector

class YourNewService:
    @track_performance(service_name="YourNewService", include_metadata=True)
    async def special_business_method(self, data):
        result = await self.process(data)
        
        # Custom business metric
        if result.get('high_value_transaction'):
            prometheus_collector.record_custom_metric(
                metric_name="high_value_transactions_total",
                value=1,
                labels={"service": "YourNewService"}
            )
        
        return result
```

## That's It!

Your new service is now fully instrumented with:
- **Prometheus metrics** for monitoring
- **Grafana dashboards** for visualization  
- **CloudWatch integration** for enterprise monitoring
- **Database logging** for historical analysis

The system automatically handles all the complexity - you just add the decorator!