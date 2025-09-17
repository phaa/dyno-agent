import os
import sys
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession

# Necessário para importar db e models
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Como Executamos como  script, temos que importar db e models como se estivéssemos no root
from db import AsyncSessionLocal, engine
from models import Dyno, Vehicle

async def seed():
    async with AsyncSessionLocal() as db:
        dynos = [
            Dyno(name="Dyno-A", max_weight_lbs=8000, supported_drive="2WD", supported_test_types=["brake"], enabled=True),
            Dyno(name="Dyno-B", max_weight_lbs=12000, supported_drive="AWD", supported_test_types=["brake", "emission"], enabled=True),
            Dyno(name="Dyno-C", max_weight_lbs=20000, supported_drive="any", supported_test_types=["emission"], enabled=True),
        ]
        db.add_all(dynos)

        # Veículos
        vehicles = [
            Vehicle(vin="VIN001", weight_lbs=7000, drive_type="2WD"),
            Vehicle(vin="VIN002", weight_lbs=11000, drive_type="AWD"),
            Vehicle(vin="VIN003", weight_lbs=18000, drive_type="2WD"),
        ]
        db.add_all(vehicles)

        await db.commit()
        print("Dados de seed inseridos com sucesso")

if __name__ == "__main__":
    asyncio.run(seed())