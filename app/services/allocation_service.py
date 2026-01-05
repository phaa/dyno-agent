import re
from datetime import date, timedelta, datetime
from sqlalchemy import select, or_, and_, extract, text, not_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import relationship, declarative_base

# Models
from models.dyno import Dyno
from models.allocation import Allocation
from models.vehicle import Vehicle

# Metrics
from core.metrics import track_performance


class AllocationService:
    """
    Contains business logic and direct database access
    for Dynos and Allocations. Fully isolated from LangChain/LangGraph,
    allowing clean unit testing.
    """

    def __init__(self, db: AsyncSession):
        """Initializes the service with an active database session."""
        self.db = db

    # ---------------------------------------
    # Core Logic: Find Available Dynos
    # ---------------------------------------
    @track_performance(service_name="AllocationService", include_metadata=True)
    async def find_available_dynos_core(self, start_date: date, end_date: date, weight_lbs: int, drive_type: str, test_type: str):
        """
        SQL logic implementation to find available Dynos based on
        compatibility and availability windows (including maintenance).
        """
        
        # Determine weight class
        weight_class = "<10K" if weight_lbs <= 10000 else ">10K"
        
        stmt = (
            select(Dyno)
            .where(
                Dyno.enabled == True,

                # Checks compatibility with PostgreSQL array fields (using @> operator)
                Dyno.supported_weight_classes.op("@>")([weight_class]),
                Dyno.supported_drives.op("@>")([drive_type]),
                Dyno.supported_test_types.op("@>")([test_type]),
                
                # RESTORED CHECK: Maintenance / Availability Windows
                # The dyno must be available DURING the requested window.
                or_(Dyno.available_from == None, Dyno.available_from <= start_date),
                or_(Dyno.available_to == None, Dyno.available_to >= end_date),
            )
            .order_by(Dyno.name)
        )
        result = await self.db.execute(stmt)
        return [
            dict(
                id=d.id, 
                name=d.name
            ) 
            for d in result.scalars().all()
        ]

    # ---------------------------------------
    # Core Logic: Auto Allocate Vehicle
    # ---------------------------------------
    @track_performance(service_name="AllocationService", include_metadata=True)
    async def auto_allocate_vehicle_core(self, vehicle_id: int = None, vin: str = None, start_date: date = None, days_to_complete: int = None, backup: bool = False, max_backup_days: int = 7):
        """
        Attempts to allocate a dyno, including vehicle resolution, duration calculation,
        backup window loop, and transactional concurrency control.
        """
        if start_date is None:
            return {"success": False, "message": "start_date is required."}

        # Resolve vehicle
        try:
            if vehicle_id:
                q = select(Vehicle).where(Vehicle.id == vehicle_id)
            elif vin:
                q = select(Vehicle).where(Vehicle.vin == vin)
            else:
                return {"success": False, "message": "vehicle_id or vin must be provided."}

            res = await self.db.execute(q)
            vehicle = res.scalar_one_or_none()
            if not vehicle:
                return {"success": False, "message": "Vehicle not found."}
        except SQLAlchemyError as e:
            return {"success": False, "message": f"Database error while fetching vehicle: {str(e)}"}

        # Determine duration
        try:
            days = days_to_complete if days_to_complete is not None else 1
            days = int(days)
        except Exception:
            days = 1

        # Helper to try a specific window
        async def try_window(s_date: date, e_date: date):
            test_type = "brake"  # Fallback, since Vehicle model does not define a test type
            
            candidates = await self.find_available_dynos_core(
                s_date, e_date, vehicle.weight_lbs, vehicle.drive_type, test_type
            )
            if not candidates:
                return None

            # Try to reserve the first available dyno using FOR UPDATE and re-check conflicts
            for c in candidates:
                dyno_id = c["id"]
                
                # Lock dyno row (FOR UPDATE) to avoid race conditions
                lock_q = select(Dyno).where(Dyno.id == dyno_id).with_for_update()
                lock_res = await self.db.execute(lock_q)
                dyno = lock_res.scalar_one_or_none()
                if not dyno or not dyno.enabled:
                    continue

                # Re-check overlapping allocations for the locked dyno
                conflict_q = (
                    select(Allocation)
                    .where(
                        Allocation.dyno_id == dyno_id,
                        Allocation.status != "cancelled",
                        not_(
                            or_(
                                Allocation.end_date < s_date,
                                Allocation.start_date > e_date,
                            )
                        ),
                    )
                    .limit(1)
                )
                conflict = (await self.db.execute(conflict_q)).scalar_one_or_none()
                if conflict:
                    continue

                # Create allocation
                alloc = Allocation(
                    vehicle_id=vehicle.id,
                    dyno_id=dyno_id,
                    test_type=test_type,
                    start_date=s_date,
                    end_date=e_date,
                    status="scheduled",
                )
                self.db.add(alloc)
                try:
                    await self.db.commit()
                    await self.db.refresh(alloc)
                except Exception:
                    await self.db.rollback()
                    continue

                return {
                    "allocation_id": alloc.id,
                    "dyno_id": dyno.id,
                    "dyno_name": dyno.name,
                    "start_date": str(alloc.start_date),
                    "end_date": str(alloc.end_date),
                    "status": alloc.status,
                }

            return None

        # Try requested window, then backup windows
        end_date = start_date + timedelta(days=days - 1)
        result = await try_window(start_date, end_date)
        if result:
            return {"success": True, "message": "Allocated in requested window.", "allocation": result}

        if backup:
            for delta in range(1, max_backup_days + 1):
                s = start_date + timedelta(days=delta)
                e = s + timedelta(days=days - 1)
                result = await try_window(s, e)
                if result:
                    return {"success": True, "message": f"Allocated with backup shift of {delta} day(s).", "allocation": result}

        return {"success": False, "message": "No available dynos found for request."}
    
    # ---------------------------------------
    # Core Logic: Check vehicle allocation
    # ---------------------------------------
    async def check_vehicle_allocation_core(self, vehicle_id: int):
        stmt = (
            select(Allocation, Dyno)
            .join(Dyno, Dyno.id == Allocation.dyno_id)
            .where(Allocation.vehicle_id == vehicle_id)
        )
        result = await self.db.execute(stmt)
        rows = result.all()

        if not rows:
            return f"Vehicle {vehicle_id} is not scheduled."
        
        output = []

        for alloc, dyno in rows:
            output.append(
                f"Vehicle {vehicle_id} scheduled on dyno {dyno.name} from {alloc.start_date} to {alloc.end_date} (status: {alloc.status})"
            )
            
        return output

    # ---------------------------------------
    # Core Logic: Detect conflicts
    # ---------------------------------------
    @track_performance(service_name="AllocationService")
    async def detect_conflicts_core(self):
        stmt = (
            select(Allocation, Dyno)
            .join(Dyno, Dyno.id == Allocation.dyno_id)
            .where(Allocation.status != "cancelled")
        )
        result = await self.db.execute(stmt)
        allocations = result.all()

        conflicts = []
        for i in range(len(allocations)):
            alloc_i, dyno_i = allocations[i]

            for j in range(i + 1, len(allocations)):
                alloc_j, dyno_j = allocations[j]

                if dyno_i.id != dyno_j.id:
                    continue

                if alloc_i.start_date <= alloc_j.end_date and alloc_i.end_date >= alloc_j.start_date:
                    conflicts.append({
                        "dyno": dyno_i.name,
                        "vehicles": [alloc_i.vehicle_id, alloc_j.vehicle_id],
                        "overlap": (alloc_i.start_date, alloc_i.end_date, alloc_j.start_date, alloc_j.end_date)
                    })

        return conflicts or "No conflicts found."
    
    # ---------------------------------------
    # Core Logic: Completed tests count
    # ---------------------------------------
    async def completed_tests_count_core(self):
        stmt = (
            select(Allocation)
            .where(
                Allocation.status == "completed"
            )
        )
        result = await self.db.execute(stmt)
        rows = result.scalars().all()
        return len(rows)

    # ---------------------------------------
    # Core Logic: Get tests by status
    # ---------------------------------------
    async def get_tests_by_status_core(self, status: str):
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
                end_date=allocation.start_date
            ) 
            for allocation in result.scalars().all()
        ]

    # ---------------------------------------
    # Core Logic: Maintenance check
    # ---------------------------------------
    async def maintenance_check_core(self):
        """
        Checks if any dynos are outside their availability window today.
        """
        today = date.today()
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
        
        if not dynos:
            return "All active dynos are available today."
        
        return [
            f"Dyno {d.name} is currently outside its availability window ({d.available_from} to {d.available_to})."
            for d in dynos
        ]

    # ---------------------------------------
    # Core Logic: Generic query
    # ---------------------------------------
    async def query_database_core(self, sql: str):
        sql_clean = sql.strip().lower()
        if not sql_clean.startswith("select"):
            return "Only SELECT queries are allowed."
        
        forbidden = re.compile(r"\b(drop|delete|update|insert|alter)\b", re.IGNORECASE)

        if forbidden.search(sql_clean):
            return "Query contains forbidden keywords."
        
        try:
            result = await self.db.execute(text(sql))
            rows = result.fetchall()

            if not rows:
                return "No results found."
            
            keys = result.keys()
            return [
                dict(zip(keys, row)) 
                for row in rows
            ]
        except Exception as e:
            return f"Error executing query: {str(e)}"
