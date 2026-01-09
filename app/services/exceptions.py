class AllocationDomainError(Exception):
    """Base class for all allocation domain errors."""

class NoAvailableDynoError(AllocationDomainError):
    """Raised when no dyno satisfies availability and compatibility constraints."""

class InvalidDateRangeError(AllocationDomainError):
    """Raised when start_date is after end_date or dates violate business rules."""

class VehicleAlreadyAllocatedError(AllocationDomainError):
    """Raised when the vehicle already has an overlapping allocation."""

class DynoIncompatibleError(AllocationDomainError):
    """Raised when dyno does not support vehicle/test constraints."""

class InvalidAllocationStateError(AllocationDomainError):
    """Raised when an operation is not allowed in the current allocation state."""

class DatabaseQueryError(AllocationDomainError):
    """Raised when a database query fails or returns unexpected results."""

class InvalidQueryError(AllocationDomainError):
    """Raised when a provided SQL query is invalid or unsafe."""