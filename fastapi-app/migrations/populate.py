from sqlalchemy import create_engine, text
from datetime import date
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://dyno_user:dyno_pass@db:5432/dyno_db")
engine = create_engine(DATABASE_URL)

with engine.begin() as conn:
    # Inserir veículos
    vehicles = [
        {"name": "Car A", "weight_class": "<10k", "traction": "AWD"},
        {"name": "Car B", "weight_class": ">10k", "traction": "2WD"},
        {"name": "Truck C", "weight_class": ">10k", "traction": "AWD"},
    ]

    for v in vehicles:
        conn.execute(text("""
            INSERT INTO vehicles (name, weight_class, traction)
            VALUES (:name, :weight_class, :traction)
        """), v)

    # Inserir dynos
    dynos = [
        {"name": "Dyno 1", "supported_weight_class": "<10k", "supported_traction": "AWD", "supported_test_type": "performance"},
        {"name": "Dyno 2", "supported_weight_class": ">10k", "supported_traction": "2WD", "supported_test_type": "endurance"},
        {"name": "Dyno 3", "supported_weight_class": ">10k", "supported_traction": "AWD", "supported_test_type": "performance"},
        {"name": "Dyno 4", "supported_weight_class": "any", "supported_traction": "any", "supported_test_type": "any"},
    ]

    for d in dynos:
        conn.execute(text("""
            INSERT INTO dynos (name, supported_weight_class, supported_traction, supported_test_type)
            VALUES (:name, :supported_weight_class, :supported_traction, :supported_test_type)
        """), d)

    # Inserir algumas alocações de exemplo
    allocations = [
        {"vehicle_id": 1, "dyno_id": 1, "test_type": "performance", "start_date": date(2025, 9, 15), "end_date": date(2025, 9, 20)},
        {"vehicle_id": 2, "dyno_id": 2, "test_type": "endurance", "start_date": date(2025, 9, 18), "end_date": date(2025, 9, 25)},
    ]

    for a in allocations:
        conn.execute(text("""
            INSERT INTO allocations (vehicle_id, dyno_id, test_type, start_date, end_date)
            VALUES (:vehicle_id, :dyno_id, :test_type, :start_date, :end_date)
        """), a)

print("Banco populado com sucesso ✅")
