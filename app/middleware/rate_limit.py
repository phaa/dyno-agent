from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from prometheus_client import Counter

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/minute"]  # Global default
    # storage_uri="redis://localhost:6379", # next steps
)

# Metric for monitoring
rate_limit_exceeded_counter = Counter(
    'guardrails_rate_limit_exceeded_total',
    'Total rate limit violations',
    ['endpoint', 'user_id']
)

def custom_rate_limit_exceeded(request: Request, exc: RateLimitExceeded):
    user_id = getattr(request.state, 'user_id', 'anonymous')
    rate_limit_exceeded_counter.labels(
        endpoint=request.url.path,
        user_id=user_id
    ).inc()
    
    return {
        "error": "Rate limit exceeded. Please try again later.",
        "retry_after": int(exc.args[0].split("at")[-1]) if exc.args else 60
    }