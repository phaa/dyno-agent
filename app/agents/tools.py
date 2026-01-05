from datetime import date
from langchain_core.tools import tool
from langgraph.runtime import get_runtime
from services.allocation_service import AllocationService


# ---------------------------------------
# Helper Function (Wrapper)
# ---------------------------------------
def _get_service_from_runtime():
    """
    Retrieves the DB session from the LangGraph runtime and initializes the AllocationService.
    This ensures the service has access to the 'db' object (AsyncSession).

    Clean separation between agent tools and business logic:
    - Tools remain stateless and focused
    - Business logic encapsulated in services
    - Database operations properly managed
    """
    # We assume the GraphState or runtime context contains the 'db' object
    runtime = get_runtime()
    db = runtime.context.db
    return AllocationService(db=db)


# ---------------------------------------
# Utility Tools (Do not require DB)
# ---------------------------------------
@tool
def get_datetime_now():
    """
    Gets the current date and time when needed.

    Returns:
        The current date and time in YYYY-MM-DD HH:MM:SS format.
    """
    service = _get_service_from_runtime()
    return service.get_datetime_now_core()


# ---------------------------------------
# Dyno/Allocation Tools (Delegate to the Service)
# ---------------------------------------

@tool
async def find_available_dynos(start_date: date, end_date: date, weight_lbs: int, drive_type: str, test_type: str):
    """
    Finds available dynos for a vehicle test within a specified date range
    and technical compatibility.

    Args:
        start_date: Requested start date for the test
        end_date: Requested end date for the test
        weight_lbs: Vehicle weight in pounds
        drive_type: Vehicle drive type (e.g., 'AWD', '2WD')
        test_type: Type of test required (e.g., 'AWD', '2WD', 'brake')

    Returns:
        A list of available dynos.
    """
    
    service = _get_service_from_runtime()
    return await service.find_available_dynos_core(
        start_date=start_date,
        end_date=end_date,
        weight_lbs=weight_lbs,
        drive_type=drive_type,
        test_type=test_type
    )


@tool
async def check_vehicle_allocation(vehicle_id: int):
    """
    Checks whether a specific vehicle is already allocated to a dyno.

    Args:
        vehicle_id: The ID of the vehicle

    Returns:
        A list of strings describing allocations, or a message indicating none are scheduled.
    """

    service = _get_service_from_runtime()
    return await service.check_vehicle_allocation_core(vehicle_id=vehicle_id)


@tool
async def detect_conflicts():
    """
    Detects overlapping dyno allocations (conflicts) across all dynos.

    Returns:
        A list of conflict dictionaries, or a message if no conflicts are found.
    """

    service = _get_service_from_runtime()
    return await service.detect_conflicts_core()


@tool
async def completed_tests_count():
    """
    Counts the number of completed vehicle tests.

    Returns:
        Integer: number of completed tests.
    """

    service = _get_service_from_runtime()
    return await service.completed_tests_count_core()


@tool
async def get_tests_by_status(status: str):
    """
    Retrieves vehicle tests by their test status.

    Args:
        status: test status (e.g., 'completed', 'running', 'scheduled')

    Returns:
        A list of allocations.
    """

    service = _get_service_from_runtime()
    return await service.get_tests_by_status_core(status=status)


@tool
async def maintenance_check():
    """
    Checks which dynos are currently unavailable due to maintenance 
    or scheduled downtime.

    Returns:
        A list of strings describing dynos unavailable today,
        or a message if all are available.
    """

    service = _get_service_from_runtime()
    return await service.maintenance_check_core()


@tool
async def query_database(sql: str):
    """
    Executes a secure SQL SELECT query on the database.

    This is the agent's generic query mechanism.
    Only SELECT statements are allowed.

    Args:
        sql (str): A SQL SELECT statement to execute.
    
    Returns:
        - A list of dictionaries representing rows.
        - "No results found." if the query succeeds but returns empty.
        - An error message in case of failure.
    """

    # Optional: Use get_stream_writer() if you want the query logged in the agent stream.
    # writer = get_stream_writer()
    # writer(f"Querying database: {sql}")

    service = _get_service_from_runtime()
    return await service.query_database_core(sql=sql)


@tool
async def auto_allocate_vehicle(
    vehicle_id: int = None,
    vin: str = None,
    start_date: date = None,
    days_to_complete: int = None,
    backup: bool = False,
    max_backup_days: int = 7
):
    """
    Automatically allocates optimal dyno with:
    - Multi-dimensional compatibility matching
    - Concurrency control (FOR UPDATE locks)
    - Intelligent backup date selection
    - Real-time conflict detection

    Args:
        vehicle_id: Existing vehicle ID (preferred)
        vin: Alternative identifier
        start_date: Requested start date (datetime.date)
        days_to_complete: Duration in days
        backup: If true, attempts subsequent days up to max_backup_days
        max_backup_days: Number of future days to try when backup=True

    Returns:
        dict: { "success": bool, "message": str, "allocation": {...} }
    """

    service = _get_service_from_runtime()
    return await service.auto_allocate_vehicle_core(
        vehicle_id=vehicle_id,
        vin=vin,
        start_date=start_date,
        days_to_complete=days_to_complete,
        backup=backup,
        max_backup_days=max_backup_days
    )
