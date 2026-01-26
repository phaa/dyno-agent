class RetryableException(Exception):
    """Exception for errors that can be retried (network timeouts, temporary service unavailability)."""

class FatalException(Exception):
    """Exception for non-recoverable errors (authentication failures, validation errors)."""

class AllocationDomainError(RetryableException):
    """Base class for all allocation domain errors."""

class NoAvailableDynoError(AllocationDomainError):
    """Raised when no dyno satisfies availability and compatibility constraints."""

class InvalidDateRangeError(AllocationDomainError):
    """Raised when start_date is after end_date or dates violate business rules."""

class VehicleAlreadyAllocatedError(AllocationDomainError):
    """Raised when the vehicle already has an overlapping allocation."""

class DatabaseQueryError(AllocationDomainError):
    """Raised when a database query fails or returns unexpected results."""

class InvalidQueryError(AllocationDomainError):
    """Raised when a provided SQL query is invalid or unsafe."""