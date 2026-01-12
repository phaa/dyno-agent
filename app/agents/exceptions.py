class RetryableException(Exception):
    """Exception for errors that can be retried (network timeouts, temporary service unavailability)."""
    pass


class FatalException(Exception):
    """Exception for non-recoverable errors (authentication failures, validation errors)."""
    pass