from contextlib import asynccontextmanager
from dataclasses import dataclass
import json
import logging
from typing import AsyncGenerator

from fastapi import Body, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from agents.graph import build_graph
from app.services.conversation_service import ConversationService
from auth.auth_bearer import JWTBearer
from schemas.user import UserSchema
from core.db import get_db, DATABASE_URL_CHECKPOINTER
from models.vehicle import Vehicle
from models.user import User
from schemas.allocation import AllocateRequest, AllocationOut
from schemas.chat import ChatRequest
from services.allocator import allocate_dyno_transactional, find_available_dynos
from services.validators import BusinessRules
from exceptions import ValidationError, validation_exception_handler

from auth.auth_handler import sign_jwt, decode_jwt, get_user_email_from_token
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
            # teardown on shutdown
            app.state.checkpointer = None


app = FastAPI(title="Dyno Allocator API", lifespan=lifespan)

# Register exception handler
app.add_exception_handler(ValidationError, validation_exception_handler)

origins = [
    "http://localhost:5173",  # for front-end
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],   # Allows POST, GET, OPTIONS, etc
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/", tags=["root"])
def hello():
    return {"message": "Hello, World!"}


@app.post("/chat/stream", dependencies=[Depends(JWTBearer())], tags=["chat"])
async def chat_stream(request: ChatRequest, db: AsyncSession = Depends(get_db)) -> StreamingResponse:
    """
    Endpoint for chat with SSE (Server-Sent Events) streaming.
    Receives a message from the user and sends the model's responses in real time, chunk by chunk.
    """

    user_email = get_user_email_from_token(request)
    user_message: str = request.message
    conv_id: str | None = request.conversation_id

    async def event_generator() -> AsyncGenerator[str, None]:
        """
        Generator function to yield chat response chunks as SSE.
        """
        graph = await build_graph(app.state.checkpointer)

        conv_service = ConversationService(db=db)
        
        # Get or create conversation
        conversation = await conv_service.get_or_create_conversation(
            user_email=user_email,
            conversation_id=conv_id
        )

        # Save user message
        await conv_service.save_message(
            conversation_id=conversation.id,
            role="user",
            content=user_message
        )

        inputs = {
            "messages": [HumanMessage(content=user_message)],
            "user_name": user_email.split("@")[0], 
        }

        # Thread ID to maintain context
        config = {"configurable": {"thread_id": user_email}}
        context = UserContext(db=db)

        stream_args = {
            "input": inputs,
            "config": config,
            "context": context,
            "stream_mode": ["updates", "custom"],  # Can be "values", "updates", "custom"
        }

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
                                "type": "assistant" ,
                                "content": msg.content
                            })
                            await conv_service.save_message(
                                conversation_id=conversation.id,
                                role="assistant",
                                content=msg.content
                            )
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


@app.post("/allocate", tags=["vehicles"], response_model=AllocationOut)
async def allocate(req: AllocateRequest, db: AsyncSession = Depends(get_db)):
    # Validate business rules
    BusinessRules.validate_allocation_duration(req.start_date, req.end_date)
    
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
            raise ValidationError("Vehicle data missing: provide vehicle_id or weight_lbs+drive_type.", "vehicle_data")
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


@app.get("/conversations/{conversation_id}/messages", dependencies=[Depends(JWTBearer())], tags=["chat"])
async def get_conversation_messages(
    conversation_id: str, 
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Get messages from a specific conversation for the authenticated user."""
    user_email = get_user_email_from_token(request)
    conv_service = ConversationService(db=db)
    
    messages = await conv_service.get_conversation_history(
        user_email=user_email,
        conversation_id=conversation_id
    )
    
    if not messages:
        raise HTTPException(status_code=404, detail="Conversation not found or access denied")
    
    return {"messages": messages}