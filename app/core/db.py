import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from .environment import get_database_url, get_checkpointer_url

# Load env variables 
load_dotenv()

DATABASE_URL = get_database_url()
DATABASE_URL_CHECKPOINTER = get_checkpointer_url()

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    pool_size=20,
    max_overflow=30,
    pool_pre_ping=True,
    pool_recycle=3600,
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
Base = declarative_base()
#Base.metadata.create_all(engine)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
