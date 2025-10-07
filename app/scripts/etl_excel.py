import sys
import os

# Necessário para importar db e models
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import pandas as pd
from datetime import timedelta
from sqlalchemy import select
from models.dyno import Dyno
from models.allocation import Allocation
from models.vehicle import Vehicle
from core.db import AsyncSessionLocal


async def load_dyno_rules(file_path: str):
    df = pd.read_excel(file_path, sheet_name="DynoRules")
    df = df.dropna(subset=["TestType"])

    async with AsyncSessionLocal() as session:

        """ def split_and_clean(dyno_str: str):
            dyno_names = str(dyno_str).split(",")
            return [d.strip() for d in dyno_names if d.strip()]

        all_dynos = df["Dynos (must be separated by comma)"]
        all_dynos = all_dynos.apply(split_and_clean)

        all_dynos = [
            dyno.strip() 
            for sublist in all_dynos 
            for dyno in sublist
        ]
        all_dynos = sorted(list(set(all_dynos)))  # remove duplicatas
        
        for dyno_name in all_dynos:
            dyno = Dyno(name=dyno_name)
             """

        dynos = {}

        for _, row in df.iterrows():
            dyno_names = str(row["Dynos (must be separated by comma)"]).split(",")
            dyno_names = [d.strip() for d in dyno_names if d.strip()]

            for dyno_name in dyno_names:
                #result = await session.execute(select(Dyno).where(Dyno.name == dyno_name)); dyno = result.scalar_one_or_none()
                dyno = dynos.get(dyno_name)
                if dyno is None:
                    dyno = Dyno(name=dyno_name) 

                test_type = str(row["TestType"]).strip().lower()
                if (test_type not in (dyno.supported_test_types or [])) and (test_type != "any"): # precisamos de valores específicos
                    dyno.supported_test_types = (dyno.supported_test_types or []) + [test_type]

                weight_class = str(row["WeightClass"]).strip().lower()
                if (weight_class not in (dyno.supported_weight_classes or [])) and (weight_class != "any"):
                    dyno.supported_weight_classes = (dyno.supported_weight_classes or []) + [weight_class]

                drive_type = str(row["DriveType"]).strip().lower()
                if (drive_type not in (dyno.supported_drives or [])) and (drive_type != "any"):
                    dyno.supported_drives = (dyno.supported_drives or []) + [drive_type]

                dynos[dyno_name] = dyno
        
        for k, dyno in dynos.items():
            print(f"Dyno: {k}, Weight Classes: {dyno.supported_weight_classes}, Drive Types: {dyno.supported_drives}, Test Types: {dyno.supported_test_types}")
            session.add(dyno)
        
        await session.commit()


async def load_forecast(file_path: str):
    df = pd.read_excel(file_path, sheet_name="Cert Mileage Forecast - All", skiprows=4, index_col=0)
    #print(df.columns)
    df.columns = df.columns.str.strip()
    ignore = ['DYNO CONSTRAINT (2WD/AWD)', 'GAS TYPE (ONLY FOR CERT)', 'CYCLE', 'NOTES']
    df = df.drop(columns=ignore)
    df = df.reset_index()

    vehicles = {}
    allocations = {}

    async with AsyncSessionLocal() as session:
        for _, row in df.iterrows():
            # vamos armazenar somente veiculos e alocacoes relacionadas a veiculos com VIN
            if pd.isna(row.get("VIN #")) or pd.isna(row.get("><10K")) or pd.isna(row.get("AWD/2WD")) or pd.isna(row.get("Test")):
                continue

            # Se o veiculo ainda nao existir, cria ele
            # Aqui o dicionario funciona como um controle para evitar duplicatas
            # Ao inves de consultar o banco toda vez, o que seria lento, usamos o dicionario em memoria
            vehicle = vehicles.get(row.get("VIN #"))
            if vehicle is None:
                vehicle = Vehicle(
                    vin=row.get("VIN #"),
                    build_id="No Build ID especified" if pd.isna(row.get("BUILD ID #")) else row.get("BUILD ID #"),
                    program=row.get("Program"),
                    cert_team="No Cert Team especified" if pd.isna(row.get("Cert Team")) else row.get("Cert Team"),
                    weight_class=row.get("><10K"),
                    drive_type=row.get("AWD/2WD"),
                    engine="No Engine especified" if pd.isna(row.get("Powerpack")) else row.get("Powerpack"),
                    build_type="No Build Type especified" if pd.isna(row.get("Build Type")) else row.get("Build Type")
                )
                session.add(vehicle)
                vehicles[row.get("VIN #")] = vehicle
                await session.flush()  # garante vehicle.id

            # pegar as datas de alocação
            est_start = row.get("Estimated Start")
            new_est_start = row.get("NEW EST DATE")
            actual_start = row.get("ACTUAL START DATE")
            projected_end = row.get("Projected End Date")
            testing_completed = row.get("TESTING COMPLETED")

            start_date = max(d for d in [est_start, new_est_start, actual_start] if pd.notna(d))
            end_date = max(d for d in [projected_end, testing_completed] if pd.notna(d))   

            status = row.get("Status").lower()
            if status == "g":
                status = "scheduled"

            # se dyno for igual a algum error, ignorar
            if str(row.get("DYNO")).strip() in ["No dyno available", "Invalid drive", "No dyno candidates", "nan"]:
                #print(f"Ignorando alocação com DYNO inválido para veículo {vehicle.vin}")
                continue

            dyno_name = f"{row.get('TEST FACILITY')} {row.get('DYNO')}"
            if "Track" in dyno_name:
                dyno_name = dyno_name.replace("Track Track", "Track")  

            #print(dyno_name)
            result = await session.execute(select(Dyno).where(Dyno.name == dyno_name)); 
            dyno = result.scalar_one_or_none()
            #print(dyno.__dict__)
            #print("-------------------")

            allocation = Allocation(
                vehicle_id=vehicle.id,
                dyno_id=dyno.id,
                test_type=row.get("Test"),
                start_date=start_date,
                end_date=end_date,
                status=status
            )

            allocations[vehicle.vin] = allocation
            session.add(allocation)
            await session.flush()  # garante allocation.id

        print(f"Total unique vehicles to add: {len(vehicles)}")
        print(f"Total allocations to add: {len(allocations)}")
        await session.commit()




FILE_PATH = "CERT_FUEL BASELINE_Gabriella.xlsm"

async def main():
    #await load_dyno_rules(FILE_PATH)
    await load_forecast(FILE_PATH)

if __name__ == "__main__":
    asyncio.run(main())