import re
from dataclasses import dataclass
from langchain_core.tools import tool
from langgraph.runtime import get_runtime
from langgraph.config import get_stream_writer
from sqlalchemy import select, or_, extract, text
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date
from models.dyno import Dyno
from models.allocation import Allocation
from models.vehicle import Vehicle


@dataclass
class Context:
    user_name: str
    db: AsyncSession 


# ---------------------------------------
# Find available dynos
# ---------------------------------------
@tool
async def find_available_dynos(start_date: date, end_date: date, weight_lbs: int, drive_type: str, test_type: str):
    """Find dynos available for a vehicle's test within a given date range.

    This tool helps the agent determine which dynos can accommodate a vehicle based on weight, drive type, and test type.

    Args:
        start_date: Start date of the requested test period
        end_date: End date of the requested test period
        weight_lbs: Vehicle weight in pounds
        drive_type: Drive type of the vehicle (e.g., 'AWD', '2WD')
        test_type: Type of test to be conducted
    Returns:
        A list of available dynos, each as a dictionary with 'id', 'label', and 'facility'
    """

    runtime = get_runtime(Context)
    db = runtime.context.db
    
    stmt = (
        select(Dyno)
        .where(
            Dyno.enabled == True,
            Dyno.max_weight_lbs >= weight_lbs,
            or_(Dyno.supported_drive == drive_type, Dyno.supported_drive == "any"),
            Dyno.supported_test_types.op("@>")([test_type]),  # PostgreSQL array contains
            or_(Dyno.available_from == None, Dyno.available_from <= start_date),
            or_(Dyno.available_to == None, Dyno.available_to >= end_date),
        )
        .order_by(Dyno.max_weight_lbs)
    )
    result = await db.execute(stmt)
    return [dict(id=d.id, label=d.label, facility=d.facility) for d in result.scalars().all()]

# ---------------------------------------
# Check vehicle allocation
# ---------------------------------------
@tool
async def check_vehicle_allocation(vehicle_id: str):
    """Check if a specific vehicle is already allocated to a dyno.

    The agent can use this tool to verify scheduling conflicts or get details of existing allocations.

    Args:
        vehicle_id: The name or identifier of the vehicle
    Returns:
        A list of strings describing allocations, or a message if no allocations exist
    """

    runtime = get_runtime(Context)
    db = runtime.context.db

    stmt = (
        select(Allocation, Dyno)
        .join(Dyno, Dyno.id == Allocation.dyno_id)
        .join(Vehicle, Vehicle.id == Allocation.vehicle_id)
        .where(Vehicle.name == vehicle_id)
    )
    result = await db.execute(stmt)
    rows = result.all()
    if not rows:
        return f"Vehicle {vehicle_id} is not scheduled."
    output = []
    for alloc, dyno in rows:
        output.append(
            f"Vehicle {vehicle_id} scheduled on dyno {dyno.label} from {alloc.start_date} to {alloc.end_date}"
        )
    return output

# ---------------------------------------
# Detect conflicts
# ---------------------------------------
@tool
async def detect_conflicts():
    """Detect overlapping allocations across all dynos.

    This tool allows the agent to identify scheduling conflicts between vehicles on the same dyno.

    Returns:
        A list of conflict dictionaries, each containing:
            - 'dyno': the dyno label
            - 'vehicles': list of involved vehicle IDs
            - 'overlap': overlapping date ranges
        Or a message if no conflicts are found
    """

    runtime = get_runtime(Context)
    db = runtime.context.db

    stmt = (
        select(Allocation, Dyno)
        .join(Dyno, Dyno.id == Allocation.dyno_id)
        .where(Allocation.status != "cancelled")
    )
    result = await db.execute(stmt)
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
                    "dyno": dyno_i.label,
                    "vehicles": [alloc_i.vehicle_id, alloc_j.vehicle_id],
                    "overlap": (alloc_i.start_date, alloc_i.end_date, alloc_j.start_date, alloc_j.end_date)
                })
    return conflicts or "No conflicts found."

# ---------------------------------------
# Completed tests count
# ---------------------------------------
@tool
async def completed_tests_count(weight_limit_lbs: int, month: int, year: int):
    """Count completed vehicle tests under a weight limit for a specific month and year.

    The agent can use this to provide statistics or generate reports.

    Args:
        weight_limit_lbs: Maximum vehicle weight in pounds
        month: Month of the completed tests
        year: Year of the completed tests
    Returns:
        Integer: number of completed tests matching the criteria
    """

    runtime = get_runtime(Context)
    db = runtime.context.db

    stmt = (
        select(Allocation)
        .join(Vehicle, Vehicle.id == Allocation.vehicle_id)
        .where(
            Vehicle.weight_lbs <= weight_limit_lbs,
            Allocation.status == "completed",
            extract("month", Allocation.end_date) == month,
            extract("year", Allocation.end_date) == year,
        )
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return len(rows)

# ---------------------------------------
# Maintenance check
# ---------------------------------------
@tool
async def maintenance_check():
    """Check which dynos are currently under maintenance.

    The agent can use this to avoid scheduling vehicles on dynos unavailable due to maintenance.

    Returns:
        A list of strings describing dynos under maintenance with start and end dates,
        or a message if no dynos are currently under maintenance
    """

    runtime = get_runtime(Context)
    db = runtime.context.db

    today = date.today()
    stmt = (
        select(Dyno)
        .where(Dyno.maintenance_start <= today, Dyno.maintenance_end >= today)
    )
    result = await db.execute(stmt)
    dynos = result.scalars().all()
    if not dynos:
        return "No dynos under maintenance this week."
    return [f"{d.label} under maintenance from {d.maintenance_start} to {d.maintenance_end}" for d in dynos]

# ---------------------------------------
# Generic query
# ---------------------------------------
@tool
async def query_database(sql: str):
    """Execute a safe SQL SELECT query against the database.

    The agent can use this to fetch information dynamically from the database without modifying data.
    Exploring the database:
    - You are allowed to discover table columns dynamically.
    - You are using a PostgreSQL database.
    - You may use queries like:
    - SELECT * FROM table_name LIMIT 1;
    - SELECT column_name FROM information_schema.columns WHERE table_name = 'table_name';
    - Use these queries to understand the table structure before generating the final query.

    Args:
        sql: SQL SELECT statement to execute (other statements are blocked)
    Returns:
        A list of dictionaries for query results, or an error/message if the query is invalid or empty
    """

    writer = get_stream_writer()
    writer(f"Consultando baco de dados com: {sql}")

    runtime = get_runtime(Context)
    db = runtime.context.db

    sql_clean = sql.strip().lower()
    if not sql_clean.startswith("select"):
        return "Only SELECT queries are allowed."
    forbidden = re.compile(r"\b(drop|delete|update|insert|alter)\b", re.IGNORECASE)
    if forbidden.search(sql_clean):
        return "Query contains forbidden keywords."
    try:
        result = await db.execute(text(sql))
        rows = result.fetchall()
        if not rows:
            return "No results found."
        keys = result.keys()
        return [dict(zip(keys, row)) for row in rows]
    except Exception as e:
        return f"Error executing query: {str(e)}"
