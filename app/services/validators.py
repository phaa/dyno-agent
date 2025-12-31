from datetime import date

class BusinessRules: 
    MAX_ALLOCATION_DAYS = 30
    MIN_ALLOCATION_DAYS = 1

    @staticmethod
    def validate_allocation_duration(start_date: date, end_date: date):
        duration = (end_date - start_date).days + 1
        if duration < BusinessRules.MIN_ALLOCATION_DAYS:
            raise ValueError(f"Allocation duration must be at least {BusinessRules.MIN_ALLOCATION_DAYS} day(s).")
        if duration > BusinessRules.MAX_ALLOCATION_DAYS:
            raise ValueError(f"Allocation duration cannot exceed {BusinessRules.MAX_ALLOCATION_DAYS} days.")