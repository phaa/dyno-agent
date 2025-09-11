# app/services/allocator.py
from sqlalchemy import select, and_, or_, not_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date

from models import Dyno, Allocation, Vehicle

async def find_available_dynos(
    db: AsyncSession,
    start_date: date,
    end_date: date,
    weight_lbs: int,
    drive_type: str,
    test_type: str,
):
    # subquery: existe alocação conflictante?
    conflict_exists = (
        select(Allocation.id)
        .where(
            Allocation.dyno_id == Dyno.id,
            Allocation.status != "cancelled",
            not_(
                or_(
                    Allocation.end_date < start_date,  # existing ends before new starts -> no overlap
                    Allocation.start_date > end_date,  # existing starts after new ends -> no overlap
                )
            ),
        )
        .exists()
    )

    statement = (
        select(Dyno)
        .where(
            Dyno.enabled == True,
            Dyno.max_weight_lbs >= weight_lbs,
            or_(Dyno.supported_drive == drive_type, Dyno.supported_drive == "any"),
            Dyno.supported_test_types.contains([test_type]),  # Postgres ARRAY containment
            
            # optional: dyno.availability window
            or_(Dyno.available_from == None, Dyno.available_from <= start_date),
            or_(Dyno.available_to == None, Dyno.available_to >= end_date),
            not_(conflict_exists),
        )
        .order_by(Dyno.max_weight_lbs)  # heurística (preferir menor dyno que atende)
    )

    result = await db.execute(statement)
    return result.scalars().all()

async def allocate_dyno_transactional(
    db: AsyncSession,
    dyno_id: int,
    vehicle_id: int,
    test_type: str,
    start_date: date,
    end_date: date,
):
    
    # lock dyno row
    q = select(Dyno).where(Dyno.id == dyno_id).with_for_update()
    dyno = (await db.execute(q)).scalar_one_or_none()
    if dyno is None or not dyno.enabled:
        raise Exception("Dyno not available (gone or disabled).")

    # re-check overlap
    conflict_q = (
        select(Allocation)
        .where(
            Allocation.dyno_id == dyno_id,
            Allocation.status != "cancelled",
            not_(
                or_(
                    Allocation.end_date < start_date,
                    Allocation.start_date > end_date,
                )
            ),
        )
        .limit(1)
    )
    conflict = (await db.execute(conflict_q)).scalar_one_or_none()
    if conflict:
        raise Exception("Dyno already booked for the requested interval.")

    alloc = Allocation(
        vehicle_id=vehicle_id,
        dyno_id=dyno_id,
        test_type=test_type,
        start_date=start_date,
        end_date=end_date,
        status="scheduled",
    )
    db.add(alloc)
    # commit happens at exit of context manager
    # reload allocation to have id populated
    await db.commit()
    await db.refresh(alloc)
    return alloc
