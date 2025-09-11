from datetime import date
from sqlalchemy import text

def get_available_dynos(test_type, weight_class, traction, start_date, end_date):
    """
    Retorna uma lista de dynos disponíveis para o veículo, considerando restrições.
    
    weight_class: '<10k' ou '>10k'
    start_date, end_date: datetime.date
    """
    with engine.connect() as conn:
        # Traduz weight_class em limite numérico
        weight_limit = 10000 if weight_class == '<10k' else 10001
        
        # Consulta dynos compatíveis e disponíveis
        query = text("""
        SELECT * FROM dynos d
        WHERE 
            (d.max_weight >= :weight_limit) 
            AND (:test_type = d.type OR d.type = 'any')
            AND d.id NOT IN (
                SELECT dyno_id FROM allocations
                WHERE NOT (end_date < :start_date OR start_date > :end_date)
            )
        """)
        result = conn.execute(query, {
            "weight_limit": weight_limit,
            "test_type": test_type,
            "start_date": start_date,
            "end_date": end_date
        })
        return [dict(row) for row in result]