import re
from dataclasses import dataclass
from langchain_core.tools import tool
from langgraph.runtime import get_runtime
from langgraph.config import get_stream_writer
from sqlalchemy import select, or_, and_, extract, text
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

    This tool helps the agent determine which dynos can accommodate a vehicle 
    based on weight, drive type, test type, and availability period.

    Args:
        start_date: Start date of the requested test period
        end_date: End date of the requested test period
        weight_lbs: Vehicle weight in pounds
        drive_type: Drive type of the vehicle (e.g., 'AWD', '2WD')
        test_type: Type of test to be conducted
    Returns:
        A list of available dynos, each as a dictionary with 'id' and 'name'
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
    return [dict(id=d.id, name=d.name) for d in result.scalars().all()]

# ---------------------------------------
# Check vehicle allocation
# ---------------------------------------
@tool
async def check_vehicle_allocation(vehicle_id: int):
    """Check if a specific vehicle is already allocated to a dyno.

    Args:
        vehicle_id: The ID of the vehicle
    Returns:
        A list of strings describing allocations, or a message if no allocations exist
    """

    runtime = get_runtime(Context)
    db = runtime.context.db

    stmt = (
        select(Allocation, Dyno)
        .join(Dyno, Dyno.id == Allocation.dyno_id)
        .where(Allocation.vehicle_id == vehicle_id)
    )
    result = await db.execute(stmt)
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
# Detect conflicts
# ---------------------------------------
@tool
async def detect_conflicts():
    """Detect overlapping allocations across all dynos.

    Returns:
        A list of conflict dictionaries, each containing:
            - 'dyno': the dyno name
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
                    "dyno": dyno_i.name,
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
    """Check which dynos are currently unavailable due to availability windows.

    Since Dyno has 'available_from' and 'available_to' instead of explicit 
    maintenance fields, this tool considers dynos unavailable if today's 
    date is outside their availability window.

    Returns:
        A list of strings describing dynos unavailable today,
        or a message if all dynos are available
    """

    runtime = get_runtime(Context)
    db = runtime.context.db

    today = date.today()
    stmt = (
        select(Dyno)
        .where(
            Dyno.enabled == True,
            or_(
                and_(Dyno.available_from != None, Dyno.available_from > today),
                and_(Dyno.available_to != None, Dyno.available_to < today),
            )
        )
    )
    result = await db.execute(stmt)
    dynos = result.scalars().all()
    if not dynos:
        return "All dynos are available today."
    return [f"Dyno {d.name} is unavailable (outside availability window)" for d in dynos]


@tool
async def get_table_columns(table_name: str):
    """Retrieve the column names of a specific table from the database.

    This tool allows the agent to explore the schema dynamically without hardcoding
    table structures. It only works for tables explicitly listed as allowed.

    Args:
        table_name (str): The name of the table to inspect.

    Returns:
        - A list of column names if the table exists and columns can be retrieved.
        - An error message if the table is not allowed or the columns could not be fetched.

    Usage:
        Use this tool before generating a SELECT query, to discover which columns
        are available in the target table. This ensures the agent builds valid
        and precise queries without assuming the schema in advance.
    """

    allowed_tables = ["vehicles", "dynos", "tests"]

    if table_name not in allowed_tables:
        return f"Table {table_name} is not allowed."
    
    sql = f"SELECT * FROM {table_name} LIMIT 1"
    result = await query_database(sql)
    
    if isinstance(result, list) and result:
        return list(result[0].keys())
    else:
        return f"Could not fetch columns for table {table_name}."
    

# ---------------------------------------
# Generic query
# ---------------------------------------
@tool
async def query_database(sql: str):
    """Execute a safe SQL SELECT query against the PostgreSQL database.

    This tool is used by the agent to fetch data dynamically without modifying it. 
    Only SELECT statements are permitted. Any attempt to execute INSERT, UPDATE, 
    DELETE, DROP, ALTER, or other modifying statements will be blocked.

    Exploring the database:
    - You are allowed to explore the schema dynamically.
    - The database is PostgreSQL, so prefer PostgreSQL-style queries.
    - To inspect a table's structure, you may use:
      - SELECT * FROM table_name LIMIT 1;
      - SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'table_name';
    - Use these queries to understand the available columns and data types 
      before building your final SELECT query.

    Args:
        sql (str): A SQL SELECT statement to execute. Must follow PostgreSQL syntax.
    
    Returns:
        - A list of dictionaries where each dictionary represents a row 
          (keys are column names, values are cell data).
        - "No results found." if the query executes successfully but returns no rows.
        - An error message string if the query is invalid or fails to execute.

    Usage:
        Use this tool after identifying the relevant table(s) and columns. 
        Always limit queries to the exact data needed and follow PostgreSQL syntax. 
        Example:
        SELECT model, weight FROM vehicles WHERE type = 'AWD';
    """

    #writer = get_stream_writer()
    #writer(f"Consultando baco de dados: {sql}")

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
