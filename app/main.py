from contextlib import asynccontextmanager
from dataclasses import dataclass
import json
import logging
from typing import AsyncGenerator

from fastapi import Body, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from agents.agent import build_graph
from schemas.user import UserSchema
from core.db import get_db, DATABASE_URL_CHECKPOINTER
from models.vehicle import Vehicle
from models.user import User
from schemas.allocation import AllocateRequest, AllocationOut
from schemas.chat import ChatRequest
from services.allocator import allocate_dyno_transactional, find_available_dynos

from auth.auth_handler import sign_jwt
from auth.passwords_handler import hash_password_async, verify_password_async
from schemas.user import UserSchema, UserLoginSchema

logging.basicConfig(level=logging.DEBUG)
logging.getLogger("langchain").setLevel(logging.DEBUG)

@dataclass
class UserContext:
    db: AsyncSession


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncPostgresSaver.from_conn_string(DATABASE_URL_CHECKPOINTER) as checkpointer:
        app.state.checkpointer = checkpointer
    
        try:
            await checkpointer.setup()
            yield
        finally:
            # teardown no shutdown
            app.state.checkpointer = None


app = FastAPI(title="Dyno Allocator API", lifespan=lifespan)

origins = [
    "http://localhost:5173",  # front-end
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],   # Permite POST, GET, OPTIONS, etc
    allow_headers=["*"],
)


@app.get("/", tags=["root"])
def hello():
    return {"message": "Hello, World!"}


@app.post("/chat/stream", tags=["chat"])
async def chat_stream(request: ChatRequest, db: AsyncSession = Depends(get_db)) -> StreamingResponse:
    """
    Endpoint for chat with SSE (Server-Sent Events) streaming.
    Receives a message from the user and sends the model's responses

    in real time, chunk by chunk.
    """

    user_message = request.message
    user_id = request.user_id

    async def event_generator() -> AsyncGenerator[str, None]:
        """
        Gera eventos SSE a partir do agente, usando `stream_mode="updates"`.
        Cada pedaço enviado contém a última mensagem do assistente.
        """
        
        graph = await build_graph(app.state.checkpointer)

        inputs = {
            "messages": [{"role": "user", "content": user_message}], # trocar por HumanMessage(content=request.message)
            "user_name": "Pedro",
        }

        # thread_id garante continuidade da conversa
        config = {"configurable": {"thread_id": str(user_id)}}
        context = UserContext(db=db)

        stream_args = {
            "input": inputs,
            "config": config,
            "context": context,
            "stream_mode": ["updates", "custom"],  # Can be "values", "updates", "custom"
        }
        #inputs, config=config, context=context, stream_mode=["updates", "custom"]
        async for stream_mode, chunk in graph.astream(**stream_args):
            if stream_mode == "updates":
                for step, data in chunk.items():
                    #logger.warning(step)
                    #logger.warning(data)

                    if not data or "messages" not in data:
                        continue

                    for msg in data["messages"]:
                        if isinstance(msg, AIMessage) and msg.content:
                            payload = json.dumps({
                                "type": "assistant_message" ,
                                "content": msg.content
                            })

                            yield f"data: {payload}\n\n"

            elif stream_mode == "custom":   
                payload = json.dumps({
                    "type": "token",
                    "content": chunk
                })
                yield f"data: {payload}\n\n" 

        # Finaliza o stream
        yield "data: [DONE]\n\n"

    # Retorna a resposta como SSE
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/allocate", tags=["vehicles"],response_model=AllocationOut)
async def allocate(req: AllocateRequest, db: AsyncSession = Depends(get_db)):
    # 1) Resolve vehicle: must have weight_lbs and drive_type (either via vehicle_id or payload)
    if req.vehicle_id:
        veh = (await db.execute(select(Vehicle).where(Vehicle.id == req.vehicle_id))).scalar_one_or_none()
        if not veh:
            raise HTTPException(status_code=404, detail="Vehicle not found.")
        weight = veh.weight_lbs
        drive = veh.drive_type
        vehicle_id = veh.id
    else:
        if not (req.weight_lbs and req.drive_type):
            raise HTTPException(status_code=400, detail="Vehicle data missing: provide vehicle_id or weight_lbs+drive_type.")
        # Optional: upsert vehicle if vin provided
        vehicle_id = None
        weight = req.weight_lbs
        drive = req.drive_type

    # 2) find candidates
    candidates = await find_available_dynos(db, req.start_date, req.end_date, weight, drive, req.test_type)
    if not candidates:
        raise HTTPException(status_code=404, detail="No available dynos match constraints.")

    # 3) choose one (heuristic: first candidate)
    chosen = candidates[0]
    # If vehicle_id is None, create vehicle row to record allocation
    if vehicle_id is None:
        newv = Vehicle(vin=req.vin, weight_lbs=req.weight_lbs, drive_type=req.drive_type)
        db.add(newv)
        await db.flush()  # get id
        vehicle_id = newv.id

    # 4) transactional allocation
    try:
        alloc = await allocate_dyno_transactional(db, chosen.id, vehicle_id, req.test_type, req.start_date, req.end_date)
    except Exception as e:
        raise HTTPException(status_code=409, detail=str(e))

    return AllocationOut(
        allocation_id=alloc.id,
        dyno_id=chosen.id,
        dyno_name=chosen.name,
        start_date=alloc.start_date,
        end_date=alloc.end_date,
        status=alloc.status,
    )

@app.post("/register", tags=["auth"])
async def register_user(user: UserSchema, db: AsyncSession = Depends(get_db)):
    # Verify if user exists in db
    existing_user = (await db.execute(select(User).where(User.email == user.email))).scalar_one_or_none()

    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists.")
    
    if not user.email or not user.password or not user.fullname:
        raise HTTPException(status_code=400, detail="Missing user information.")

    # Hash password
    hashed_password = await hash_password_async(user.password)

    # Create new user
    new_user = User(
        email=user.email,
        fullname=user.fullname,
        password=hashed_password,  # In production, hash the password before storing
    )

    # Add user to db    
    db.add(new_user)
    await db.flush() 

    try:
        await db.commit() # persist the new user
    except IntegrityError:
        # handle race where another request created the same email
        await db.rollback()
        raise HTTPException(status_code=409, detail="Email already registered.")

    # return token after successful commit
    return sign_jwt(user.email)


@app.post("/login", tags=["auth"])
async def login_user(user: UserLoginSchema, db: AsyncSession = Depends(get_db)):
    # Check user in db
    existing_user = (await db.execute(select(User).where(User.email == user.email))).scalar_one_or_none()
    if not existing_user:
        raise HTTPException(status_code=404, detail="User not found.")
    
    password_valid = await verify_password_async(user.password, existing_user.password)
    if not password_valid:
        raise HTTPException(status_code=401, detail="Invalid password.")    

    # Generate JWT token
    token = sign_jwt(existing_user.email)
    return token