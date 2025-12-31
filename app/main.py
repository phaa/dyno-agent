import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from core.db import DATABASE_URL_CHECKPOINTER
from exceptions import ValidationError, validation_exception_handler
from routers import allocation, auth, chat, health

logging.basicConfig(level=logging.DEBUG)
logging.getLogger("langchain").setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncPostgresSaver.from_conn_string(DATABASE_URL_CHECKPOINTER) as checkpointer:
        app.state.checkpointer = checkpointer
        try:
            await checkpointer.setup()
            yield
        finally:
            app.state.checkpointer = None


app = FastAPI(title="Dyno Allocator API", lifespan=lifespan)

app.add_exception_handler(ValidationError, validation_exception_handler)

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(allocation.router)


@app.get("/", tags=["root"])
def hello():
    return {"message": "Hello, World!"}