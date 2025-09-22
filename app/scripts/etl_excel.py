import asyncio
import pandas as pd
from datetime import timedelta
from sqlalchemy import select
from models.dyno import Dyno
from models.allocation import Allocation
from models.vehicle import Vehicle
from core.db import AsyncSessionLocal


async def load_forecast(file_path: str):
    df = pd.read_excel(file_path, sheet_name="Cert Mileage Forecast - All", skiprows=3)

    # Corrigir nomes de colunas
    df.columns = df.columns.str.strip()
    vin_col = next((c for c in df.columns if "VIN" in str(c)), None)
    if not vin_col:
        raise ValueError("Coluna VIN não encontrada no Excel")

    df = df.dropna(subset=[vin_col])

    async with AsyncSessionLocal() as session:
        for _, row in df.iterrows():
            vehicle = Vehicle(
                vin=row[vin_col],
                build_id=row.get("BUILD ID #"),
                program=row.get("Program"),
                cert_team=row.get("Cert Team"),
                weight_class="<10k" if "<10" in str(row.get("Powerpack", "")).lower() else ">10k",
                drive_type=row.get("DYNO", "any").upper() if row.get("DYNO") in ["2WD", "AWD"] else "any",
                engine=row.get("Powerpack"),
                build_type=row.get("Build Type")
            )
            session.add(vehicle)
            await session.flush()  # garante vehicle.id

            days_to_complete = row.get("Days to complete")
            start_date, end_date = None, None
            if pd.notna(days_to_complete):
                start_date = pd.to_datetime("today").date()
                end_date = start_date + timedelta(days=int(days_to_complete))

            allocation = Allocation(
                vehicle_id=vehicle.id,
                dyno_id=None,  # atribuído depois pelas regras
                test_type=row.get("Test"),
                start_date=start_date,
                end_date=end_date,
                status="scheduled"
            )
            session.add(allocation)

        await session.commit()


async def load_dyno_rules(file_path: str):
    df = pd.read_excel(file_path, sheet_name="DynoRules")
    df = df.dropna(subset=["TestType"])

    async with AsyncSessionLocal() as session:
        for _, row in df.iterrows():
            dyno_names = str(row["Dynos (must be separated by comma)"]).split(",")
            dyno_names = [d.strip() for d in dyno_names if d.strip()]

            for dyno_name in dyno_names:
                result = await session.execute(select(Dyno).where(Dyno.name == dyno_name))
                dyno = result.scalar_one_or_none()

                if not dyno:
                    dyno = Dyno(name=dyno_name)
                    session.add(dyno)

                dyno.max_weight_class = str(row["WeightClass"]).lower()
                dyno.supported_drive = str(row["DriveType"]).lower()
                if row["TestType"] not in (dyno.supported_test_types or []):
                    dyno.supported_test_types = (dyno.supported_test_types or []) + [row["TestType"]]

        await session.commit()


FILE_PATH = "CERT_FUEL BASELINE_Gabriella.xlsm"

async def main():
    await load_forecast(FILE_PATH)
    await load_dyno_rules(FILE_PATH)

if __name__ == "__main__":
    asyncio.run(main())