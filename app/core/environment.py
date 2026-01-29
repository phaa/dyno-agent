import os

def is_production() -> bool:
    """Detects if running in production via PRODUCTION variable"""
    return os.getenv("PRODUCTION").lower() == "true"

def get_database_url() -> str:
    """Returns SQLAlchemy database URL based on environment"""
    if is_production():
        return os.getenv("DATABASE_URL_PROD")
    else:
        return os.getenv("DATABASE_URL")

def get_checkpointer_url() -> str:
    """Returns LangGraph checkpointer database URL based on environment"""
    if is_production():
        return os.getenv("DATABASE_URL_CHECKPOINTER_PROD")
    else:
        return os.getenv("DATABASE_URL_CHECKPOINTER")
    