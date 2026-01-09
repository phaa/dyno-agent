import re
from datetime import date, timedelta, datetime
from typing import List, Dict, Union, Optional
from sqlalchemy import select, or_, and_, text, func, exists
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import aliased

# Models
from models.dyno import Dyno
from models.allocation import Allocation
from models.vehicle import Vehicle

# Metrics
from core.metrics import track_performance

# Exceptions
from exceptions import (
    AllocationDomainError,
    InvalidQueryError,
    NoAvailableDynoError,
    InvalidDateRangeError,
    VehicleAlreadyAllocatedError,
    DynoIncompatibleError,
    InvalidAllocationStateError,
    DatabaseQueryError
)


class AllocationService:
    """
    Business logic service for vehicle-to-dynamometer allocation operations.
    
    This service provides core functionality for:
    - Finding available dynos based on vehicle compatibility
    - Automatic vehicle allocation with concurrency control
    - Conflict detection and resolution
    - Maintenance window management
    - Safe database querying with security validation
    
    The service is fully isolated from LangChain/LangGraph frameworks,
    enabling clean unit testing and reusability across different interfaces.
    
    All database operations use SQLAlchemy 2.0 async patterns with proper
    transaction management and row-level locking for race condition prevention.
    """

    def __init__(self, db: AsyncSession):
        """
        Initializes the allocation service with a database session.
        
        Args:
            db (AsyncSession): Active SQLAlchemy async database session
                              for all database operations
        """
        self.db = db

    @track_performance(service_name="AllocationService", include_metadata=True)
    def get_datetime_now_core(self):
        """
        Returns the current date and time.
        
        This method is tracked for performance monitoring and provides
        a consistent timestamp source across the application.
        
        Returns:
            datetime: Current date and time
        """
        return datetime.now()

    @track_performance(service_name="AllocationService", include_metadata=True)
    async def find_available_dynos_core(
        self, 
        start_date: date, 
        end_date: date, 
        weight_lbs: int, 
        drive_type: str, 
        test_type: str
    ) -> List[Dict]:
        """
        Finds available dynamometers based on vehicle compatibility and scheduling constraints.
        
        Performs sophisticated multi-dimensional matching using PostgreSQL array operators
        to find dynos that support the vehicle's specifications and are available during
        the requested time window.
        
        Args:
            start_date (date): Start date of the requested allocation period
            end_date (date): End date of the requested allocation period  
            weight_lbs (int): Vehicle weight in pounds for compatibility matching
            drive_type (str): Vehicle drive type ('2WD', 'AWD', etc.)
            test_type (str): Type of test to be performed ('brake', 'emission', etc.)
            
        Returns:
            list[dict]: List of available dyno dictionaries with 'id' and 'name' keys
            
        Database Operations:
            - Uses PostgreSQL @> array operator for compatibility matching
            - Respects maintenance windows (available_from/available_to)
            - Filters only enabled dynos
            - Orders results by dyno name for consistent output
        """
        
        # Determine weight class
        weight_class = "<10K" if weight_lbs <= 10000 else ">10K"
        
        # OPTIMIZATION: Combine compatibility + availability check with NOT EXISTS
        # Exclude dynos with conflicting allocations in single query
        # Suggested index: CREATE INDEX idx_allocation_dyno_dates ON allocation(dyno_id, start_date, end_date) WHERE status != 'cancelled';
        # Suggested index: CREATE INDEX idx_dyno_arrays ON dyno USING GIN(supported_weight_classes, supported_drives, supported_test_types);
        
        try:
            stmt = (
                select(Dyno)
                .where(
                    Dyno.enabled == True,
                    # Compatibility checks using PostgreSQL @> array operators
                    Dyno.supported_weight_classes.op("@>")([weight_class]),
                    Dyno.supported_drives.op("@>")([drive_type]),
                    Dyno.supported_test_types.op("@>")([test_type]),
                    # Maintenance/availability windows
                    or_(Dyno.available_from == None, Dyno.available_from <= start_date),
                    or_(Dyno.available_to == None, Dyno.available_to >= end_date),
                    # Exclude dynos with conflicting allocations (NOT EXISTS is more efficient than NOT IN)
                    ~exists().where(
                        and_(
                            Allocation.dyno_id == Dyno.id,
                            Allocation.status != "cancelled",
                            Allocation.start_date <= end_date,
                            Allocation.end_date >= start_date
                        )
                    )
                )
                .order_by(Dyno.name)
            )
            result = await self.db.execute(stmt)

            if not result.scalars().first():
                raise NoAvailableDynoError(
                    f"No dynos support weight={weight_class}, drive={drive_type}, test={test_type}"
                )

            return [
                dict(
                    id=d.id, 
                    name=d.name
                ) 
                for d in result.scalars().all()
            ]
        except SQLAlchemyError as e:
            raise DatabaseQueryError(str(e))

    @track_performance(service_name="AllocationService", include_metadata=True)
    async def auto_allocate_vehicle_core(
        self, 
        start_date: date, 
        days_to_complete: int, 
        vehicle_id: Optional[int] = None, 
        vin: Optional[str] = None, 
        backup: bool = False, 
        max_backup_days: int = 7
    ) -> Dict:
        """
        Automatically allocates an optimal dyno for a vehicle with intelligent backup scheduling.
        
        This is the core allocation algorithm that handles:
        - Vehicle resolution by ID or VIN
        - Duration calculation and validation
        - Primary window allocation attempt
        - Backup window search with configurable range
        - Concurrency control using database row locking
        - Transactional safety with rollback on conflicts
        
        Args:
            start_date (date): Preferred start date for allocation
            vehicle_id (int, optional): Database ID of the vehicle to allocate
            vin (str, optional): VIN of the vehicle (alternative to vehicle_id)
            days_to_complete (int): Duration in days (defaults to 1)
            backup (bool): Whether to search backup dates if primary fails
            max_backup_days (int): Maximum days to search forward for backup slots
            
        Returns:
            dict: Allocation result with success status, message, and allocation details
                 Format: {"success": bool, "message": str, "allocation": dict}
                 
        Concurrency Control:
            - Uses SELECT ... FOR UPDATE to lock dyno rows
            - Re-validates conflicts after acquiring lock
            - Atomic commit/rollback for each allocation attempt
            
        Algorithm:
            1. Resolve vehicle by ID or VIN
            2. Calculate allocation duration
            3. Try primary time window
            4. If backup enabled, try shifted windows up to max_backup_days
            5. Return first successful allocation or failure message
        """

        # Resolve vehicle
        try:
            if vehicle_id:
                q = select(Vehicle).where(Vehicle.id == vehicle_id)
            elif vin:
                q = select(Vehicle).where(Vehicle.vin == vin)
            else:
                return {
                    "success": False, 
                    "message": "vehicle_id or vin must be provided."
                }

            res = await self.db.execute(q)
            vehicle = res.scalar_one_or_none()

            if not vehicle:
                return {
                    "success": False, 
                    "message": "Vehicle not found."
                }   
        except SQLAlchemyError as e:
            raise DatabaseQueryError(str(e))

        if days_to_complete < 1:
            raise InvalidDateRangeError("days_to_complete must be at least 1.")

        # Try requested window, then backup windows
        end_date = start_date + timedelta(days=days_to_complete - 1)

        # Check for existing overlapping allocations for the vehicle first
        existing_vehicle_alloc = await self.db.execute(
            select(func.count(Allocation.id)).where(
                Allocation.vehicle_id == vehicle.id,
                Allocation.status != "cancelled",
                Allocation.start_date <= end_date,
                Allocation.end_date >= start_date
            )
        )

        if existing_vehicle_alloc.scalar() > 0:
            raise VehicleAlreadyAllocatedError(
                f"Vehicle {vehicle.id} already has an overlapping allocation."
            )
        
        
        result = await self._try_window(vehicle, start_date, end_date)
        if result:
            return {
                "success": True, 
                "message": "Allocated in requested window.", 
                "allocation": result
            }

        if backup:
            for delta in range(1, max_backup_days + 1):
                s = start_date + timedelta(days=delta)
                e = s + timedelta(days=days_to_complete - 1)
                result = await self._try_window(vehicle, s, e)
                if result:
                    return {
                        "success": True, 
                        "message": f"Allocated with backup shift of {delta} day(s).", 
                        "allocation": result
                    }
    
        raise NoAvailableDynoError(
            "No available dynos found for request."
        )
    
    @track_performance(service_name="AllocationService")
    async def check_vehicle_allocation_core(self, vehicle_id: int) -> Union[str, List[str]]:
        """
        Retrieves all allocations for a specific vehicle.
        
        Args:
            vehicle_id (int): The ID of the vehicle to check allocations for
            
        Returns:
            str | list[str]: A list of formatted allocation details
        """
        try:
            stmt = (
                select(Allocation, Dyno)
                .join(Dyno, Dyno.id == Allocation.dyno_id)
                .where(Allocation.vehicle_id == vehicle_id)
            )
            result = await self.db.execute(stmt)
            rows = result.all()

            if not rows:
                raise AllocationDomainError("No allocations found for the specified vehicle.")
            
            output = []
            for alloc, dyno in rows:
                output.append(
                    f"Vehicle {vehicle_id} scheduled on dyno {dyno.name} from {alloc.start_date} to {alloc.end_date} (status: {alloc.status})"
                )
                
            return output
        except SQLAlchemyError as e:
            raise DatabaseQueryError(str(e))

    @track_performance(service_name="AllocationService")
    async def detect_conflicts_core(self) -> List[Dict]:
        """
        OPTIMIZED: Detects scheduling conflicts using SQL self-join instead of O(n²) Python loops.
        
        Uses PostgreSQL self-join with aliases to find overlapping allocations
        on the same dyno in a single query, dramatically improving performance.
        
        Returns:
            list[dict]: Either "No conflicts found." or a list of conflict details
                            containing dyno name, conflicting vehicles, and overlap periods
                            
        Performance:
            - Before: O(n²) Python loops loading all allocations into memory
            - After: Single SQL query with proper indexing
            - Suggested index: CREATE INDEX idx_allocation_conflicts ON allocation(dyno_id, start_date, end_date, status, vehicle_id);
        """
        # Create aliases for self-join
        a1 = aliased(Allocation)
        a2 = aliased(Allocation)
        
        try:
            stmt = (
                select(
                    Dyno.name.label("dyno_name"),
                    a1.vehicle_id.label("vehicle1_id"),
                    a2.vehicle_id.label("vehicle2_id"),
                    a1.start_date.label("start1"),
                    a1.end_date.label("end1"),
                    a2.start_date.label("start2"),
                    a2.end_date.label("end2")
                )
                .select_from(
                    a1.join(a2, a1.dyno_id == a2.dyno_id)
                    .join(Dyno, Dyno.id == a1.dyno_id)
                )
                .where(
                    # Same dyno, different allocations
                    a1.id < a2.id,  # Avoid duplicates (a1 vs a2 and a2 vs a1)
                    a1.status != "cancelled",
                    a2.status != "cancelled",
                    # Overlap condition: start1 <= end2 AND end1 >= start2
                    a1.start_date <= a2.end_date,
                    a1.end_date >= a2.start_date
                )
            )
            
            result = await self.db.execute(stmt)
            rows = result.all()
            
            if not rows:
                return []
                
            return [
                {
                    "dyno": row.dyno_name,
                    "vehicles": [row.vehicle1_id, row.vehicle2_id],
                    "overlap": (row.start1, row.end1, row.start2, row.end2)
                }
                for row in rows
            ]
        except SQLAlchemyError as e:
            raise DatabaseQueryError(str(e))
    
    async def completed_tests_count_core(self) -> int:
        """
        OPTIMIZED: Counts completed tests using SQL COUNT(*) instead of loading all records.
        
        Returns:
            int: The count of allocations with status "completed"
            
        Performance:
            - Before: SELECT all records, load into memory, len() in Python
            - After: Single COUNT(*) query executed in database
        """
        try:
            stmt = select(func.count(Allocation.id)).where(Allocation.status == "completed")
            result = await self.db.execute(stmt)
            return result.scalar()
        except SQLAlchemyError as e:
            raise DatabaseQueryError(str(e))

    async def get_tests_by_status_core(self, status: str) -> List[Dict[str, Union[int, str, date]]]:
        """
        Retrieves all test allocations filtered by status.
        
        Args:
            status (str): The allocation status to filter by (e.g., "scheduled", "completed", "cancelled")
            
        Returns:
            str | list[dict]: Either an error message or list of allocation dictionaries containing id, type, start_date, and end_date
    
        """
        try:
            stmt = (
                select(Allocation)
                .where(
                    Allocation.status == status
                )
            )
            result = await self.db.execute(stmt)
            return [
                dict(
                    id=allocation.id, 
                    type=allocation.test_type, 
                    start_date=allocation.start_date,
                    end_date=allocation.end_date
                ) 
                for allocation in result.scalars().all()
            ]
        except SQLAlchemyError as e:
            raise DatabaseQueryError(str(e))

    @track_performance(service_name="AllocationService")
    async def maintenance_check_core(self) -> Union[str, List[str]]:
        """
        Identifies dynos that are outside their availability windows.
        
        Checks all enabled dynos to find those that are currently unavailable
        due to maintenance windows or availability restrictions.
        
        Returns:
            str | list[dict]: Either an error message or a list of messages describing unavailable dynos
                           
        Maintenance Conditions:
            - Future maintenance: available_from > today (not yet available)
            - Past maintenance: available_to < today (should be disabled)
        """
        today = date.today()
        try:
            stmt = (
                select(Dyno)
                .where(
                    Dyno.enabled == True,
                    or_(
                        # Future maintenance: available_from is in the future (not available yet)
                        and_(Dyno.available_from != None, Dyno.available_from > today),

                        # Past maintenance: available_to is in the past (should be disabled)
                        and_(Dyno.available_to != None, Dyno.available_to < today),
                    )
                )
            )
            result = await self.db.execute(stmt)
            dynos = result.scalars().all()
            
            return [
                f"Dyno {d.name} is currently outside its availability window ({d.available_from} to {d.available_to})."
                for d in dynos
            ]
        except SQLAlchemyError as e:
            raise DatabaseQueryError(str(e))

    @track_performance(service_name="AllocationService")
    async def query_database_core(self, sql: str):
        """
        Executes a safe SELECT query against the database with security validation.
        
        Provides a controlled interface for running custom SQL queries while preventing
        dangerous operations through keyword filtering and query type validation.
        
        Args:
            sql (str): The SQL query to execute (must be a SELECT statement)
            
        Returns:
            str | list[dict]: Either an error message or list of query results as dictionaries
            
        Security:
            - Only SELECT queries are allowed
            - Forbidden keywords (DROP, DELETE, UPDATE, INSERT, ALTER) are blocked
            - Uses SQLAlchemy's text() for safe query execution
        """
        sql_clean = sql.strip().lower()
        forbidden = re.compile(r"\b(drop|delete|update|insert|alter)\b", re.IGNORECASE)

        if (not sql_clean.startswith("select") or 
            ";" in sql_clean.strip().rstrip(";") or 
            forbidden.search(sql_clean)
        ):
            raise InvalidQueryError("Only SELECT queries are allowed.")
        
        try:
            # Kill bad queries in production
            await self.db.execute(
                text("SET LOCAL statement_timeout = '2000ms'")
            )
            
            result = await self.db.execute(text(sql))
            rows = result.fetchall()

            if not rows:
                return []
            
            keys = result.keys()
            return [
                dict(zip(keys, row)) 
                for row in rows
            ]
        except SQLAlchemyError as e:
            raise DatabaseQueryError(str(e))
        
    def handle_exception_core(self, e: Exception) -> dict:
        """
        Centralized exception handling for the allocation service.
        
        The exceptions are already logged trough the @track_performance decorator.
        This method provides a standardized error message format for consistency.
        
        Args:
            e (Exception): The exception to handle 

        Returns:
            str: A standardized error message describing the exception
        """
        # In the future we will expand this to map specific exceptions to messages to be used by the agent
        if isinstance(e, AllocationDomainError):
            return {
                "success": False,
                "error_type": e.__class__.__name__,
                "message": str(e)
            }

        # Anything else is a real failure → crash graph
        raise e

    async def _try_window(self, vehicle, s_date: date, e_date: date):
        """Try to allocate vehicle in a specific time window using multiple dyno candidates."""

        test_type = "brake"  # Fallback

        # Step 1: Find compatible & apparently available dynos (no locks yet)
        candidates = await self.find_available_dynos_core(
            s_date,
            e_date,
            vehicle.weight_lbs,
            vehicle.drive_type,
            test_type
        )

        # Step 2: Try dynos one by one with row-level locking
        for candidate in candidates:
            dyno_id = candidate["id"]

            try:
                async with self.db.begin():
                    # Lock dyno row
                    dyno = (
                        await self.db.execute(
                            select(Dyno)
                            .where(Dyno.id == dyno_id)
                            .with_for_update()
                        )
                    ).scalar_one_or_none()

                    if not dyno or not dyno.enabled:
                        continue

                    # Re-check for overlapping allocations after lock
                    existing_alloc = await self.db.execute(
                        select(func.count(Allocation.id))
                        .where(
                            Allocation.dyno_id == dyno_id,
                            Allocation.status != "cancelled",
                            Allocation.start_date <= e_date,
                            Allocation.end_date >= s_date,
                        )
                    )

                    if existing_alloc.scalar() > 0:
                        # Dyno lost to race condition → try next
                        continue

                    # Create allocation atomically
                    alloc = Allocation(
                        vehicle_id=vehicle.id,
                        dyno_id=dyno_id,
                        test_type=test_type,
                        start_date=s_date,
                        end_date=e_date,
                        status="scheduled",
                    )

                    self.db.add(alloc)
                    await self.db.flush()

                    return {
                        "allocation_id": alloc.id,
                        "dyno_id": dyno.id,
                        "dyno_name": dyno.name,
                        "start_date": str(alloc.start_date),
                        "end_date": str(alloc.end_date),
                        "status": alloc.status,
                    }

            except SQLAlchemyError as e:
                raise DatabaseQueryError(str(e))

        # All candidates failed
        return None
