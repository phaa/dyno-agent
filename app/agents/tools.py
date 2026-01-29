from datetime import date
from langchain_core.tools import tool
from langgraph.runtime import get_runtime
from services.allocation_service import AllocationService
from .stream_writer import get_stream_writer


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
    Use this tool when the user asks about:
    - Today's date
    - The current day or time
    - "Now", "today", "current date", or time-based reasoning

    This tool should be used instead of assuming or hallucinating dates.

    Returns:
        A string with the current date and time in format:
        YYYY-MM-DD HH:MM:SS
    """
    service = _get_service_from_runtime()
    return service.get_datetime_now_core()


# ---------------------------------------
# Dyno/Allocation Tools (Delegate to the Service)
# ---------------------------------------

@tool
async def find_available_dynos(start_date: date, end_date: date, weight_lbs: int, drive_type: str, test_type: str):
    """
    Use this tool when the user wants to:
    - Find available dynos for a new test
    - Check which dynos can run a test in a given date range
    - Ask questions like:
        * "Which dynos are available?"
        * "Can I schedule a test between X and Y?"
        * "What dynos support this vehicle?"

    Do NOT use this tool to allocate or book a dyno.
    This tool is read-only and does not create allocations.

    Returns:
        A list of available dynos that match:
        - Date availability
        - Vehicle weight
        - Drive type (AWD / 2WD)
        - Test type
    """
    
    writer = get_stream_writer()
    writer("🔍 Searching database for available dynamometers...")
    
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
    Use this tool when the user asks:
    - If a vehicle is already scheduled
    - Whether a vehicle has an existing dyno allocation
    - To check conflicts before booking another test

    Typical questions:
    - "Is vehicle 77 already scheduled?"
    - "Does this car have any allocations?"
    - "Show me current bookings for this vehicle"

    Returns:
        A list describing current or past allocations for the vehicle.
        If none exist, returns an explicit 'no allocations found' message.
    """

    writer = get_stream_writer()
    writer(f"🚗 Checking vehicle {vehicle_id} allocations...")

    service = _get_service_from_runtime()

    return await service.check_vehicle_allocation_core(vehicle_id=vehicle_id)


@tool
async def detect_conflicts():
    """
    Use this tool when the user wants to:
    - Detect scheduling conflicts
    - Check overlapping dyno bookings
    - Audit the system for allocation issues

    Typical questions:
    - "Are there any conflicts?"
    - "Do we have overlapping dyno schedules?"
    - "Is anything double-booked?"

    Returns:
        A list of detected conflicts with dyno, dates, and vehicles,
        or a message stating that no conflicts were found.
    """

    writer = get_stream_writer()
    writer("⚠️ Analyzing allocation conflicts...")

    service = _get_service_from_runtime()
    return await service.detect_conflicts_core()


@tool
async def completed_tests_count():
    """
    Use this tool when the user asks for:
    - Metrics or statistics
    - How many tests have been completed
    - System-level KPIs

    Typical questions:
    - "How many tests are completed?"
    - "Total number of finished tests?"

    Returns:
        An integer representing the number of completed tests.
    """

    writer = get_stream_writer()
    writer("📊 Counting completed tests...")

    service = _get_service_from_runtime()
    return await service.completed_tests_count_core()


@tool
async def get_tests_by_status(status: str):
    """
    Use this tool when the user wants to list tests by status.

    Valid statuses include:
    - completed
    - running
    - scheduled

    Typical questions:
    - "Show me all running tests"
    - "Which tests are scheduled?"
    - "List completed tests"

    Prefer this tool over direct SQL queries when filtering by status.

    Returns:
        A list of tests matching the requested status.
    """

    writer = get_stream_writer()
    writer(f"📄 Searching tests with status '{status}'...")

    service = _get_service_from_runtime()
    return await service.get_tests_by_status_core(status=status)


@tool
async def maintenance_check():
    """
    Use this tool when the user asks about:
    - Dyno availability due to maintenance
    - Downtime or temporarily unavailable dynos

    Typical questions:
    - "Are any dynos under maintenance?"
    - "Why is dyno X unavailable?"
    - "Which dynos are down today?"

    Returns:
        A list of dynos currently unavailable due to maintenance,
        or a message indicating all dynos are operational.
    """

    writer = get_stream_writer()
    writer("🔧 Checking dynamometer maintenance status...")

    service = _get_service_from_runtime()
    return await service.maintenance_check_core()


@tool
async def query_database(sql: str):
    """
    Executes a secure SQL SELECT query on the database.

    - This is the agent's generic query mechanism.
    - Only SELECT statements are allowed.
    - Avoid queries without where clauses and limit clauses.

    Args:
        sql (str): A SQL SELECT statement to execute.
    
    Returns:
        - A list of dictionaries representing rows.
        - "No results found." if the query succeeds but returns empty.
        - An error message in case of failure.
    """

    writer = get_stream_writer()
    writer(f"📊 Querying system informations with SQL: {sql}")

    service = _get_service_from_runtime()
    return await service.query_database_core(sql=sql)


@tool
async def auto_allocate_vehicle(
    start_date: date,
    days_to_complete: int,
    vehicle_id: int = None,
    vin: str = None,
    backup: bool = False,
    max_backup_days: int = 7
):
    """
    Use this tool ONLY when the user explicitly wants to:
    - Book
    - Allocate
    - Schedule a vehicle on a dyno

    This tool performs a real allocation and modifies system state.

    Typical user intents:
    - "Schedule this vehicle"
    - "Book a dyno"
    - "Automatically allocate a test"
    - "Find and reserve the best dyno"

    If the user is only asking questions or exploring options,
    use read-only tools instead.

    Returns:
        {
          "success": boolean,
          "message": explanation of the result,
          "allocation": allocation details (if successful)
        }
    """

    writer = get_stream_writer()
    writer("⚙️ Attempting intelligent vehicle auto-allocation...")

    service = _get_service_from_runtime()
    result = await service.auto_allocate_vehicle_core(
        vehicle_id=vehicle_id,
        vin=vin,
        start_date=start_date,
        days_to_complete=days_to_complete,
        backup=backup,
        max_backup_days=max_backup_days
    )
    return result


TOOLS = [
    get_datetime_now,
    find_available_dynos,
    check_vehicle_allocation,
    detect_conflicts,
    completed_tests_count,
    maintenance_check,
    query_database,
    auto_allocate_vehicle,
]