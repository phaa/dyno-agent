import json
import os
import logging
from typing import AsyncGenerator

from fastapi.responses import StreamingResponse

logging.basicConfig(level=logging.DEBUG)
logging.getLogger("langchain").setLevel(logging.DEBUG)

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres import PostgresSaver

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from models.vehicle import Vehicle

from schemas.allocation import AllocateRequest, AllocationOut
from schemas.chat import ChatRequest

from services.allocator import find_available_dynos, allocate_dyno_transactional

from agents.agent import create_agentw
from agents.tools import Context


from langchain_core.messages import SystemMessage, HumanMessage, AIMessage


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the checkpointer and agent
    with PostgresSaver.from_conn_string(os.getenv("DATABASE_URL_2")) as checkpointer:
        checkpointer.setup()
        app.state.checkpointer = checkpointer

        agent = create_agentw(model="gemini", checkpointer=checkpointer)
        app.state.agent = agent
        
        yield
        # Clean up functions


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


@app.get("/hello")
def hello():
    return {"message": "Hello, World!"}


@app.post("/chat")
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    result = await app.state.agent.ainvoke(
        {"messages": [{"role": "user", "content": request.message}]},
        context=Context(user_name="Pedro", db=db),
        config={"configurable": {"thread_id": f"user-{request.user_id}"}},
        #checkpointer=app.state.checkpointer,
    )

    assistant_messages = [
        msg.text()
        for msg in result["messages"]
        if isinstance(msg, AIMessage)
    ]
    return {"reply": " ".join(assistant_messages)}


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest, db: AsyncSession = Depends(get_db)) -> StreamingResponse:
    """
    Endpoint para chat com streaming SSE (Server-Sent Events).
    Recebe uma mensagem do usuário e envia as respostas do modelo
    em tempo real, pedaço por pedaço.
    """

    async def event_generator() -> AsyncGenerator[str, None]:
        """
        Gera eventos SSE a partir do agente, usando `stream_mode="updates"`.
        Cada pedaço enviado contém a última mensagem do assistente.
        """

        # Inicia o streaming do agente
        agent = app.state.agent

        """ initial_state = {
            "messages": [{"role": "user", "content": question}],
            "db": db
        } """
        
        async for stream_mode, chunk in agent.astream(
            input={"messages": [{"role": "user", "content": request.message}]},
            context=Context(user_name="Pedro", db=db),
            config={"configurable": {"thread_id": f"user-{request.user_id}"}},
            #checkpointer=app.state.checkpointer,
            stream_mode=["updates", "custom"] # values, updates, custom
        ):
            if stream_mode == "updates":
                for step, data in chunk.items():
                    assistant_msg = data["messages"][-1]
                    if isinstance(assistant_msg, AIMessage):
                        payload = json.dumps({'content': assistant_msg.content})
                        yield f"data: {payload}\n\n"

            elif stream_mode == "custom":   
                payload = json.dumps({'content': chunk})
                yield f"data: {payload}\n\n"


        # Finaliza o stream
        yield "data: [DONE]\n\n"

    # Retorna a resposta como SSE
    return StreamingResponse(event_generator(), media_type="text/event-stream")



@app.post("/allocate", response_model=AllocationOut)
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




# pega a última mensagem gerada
            # para usar com stream_mode="values"
            #msg = chunk["messages"][-1]
            #if isinstance(msg, AIMessage):
            #    yield f"data: {json.dumps({'content': msg.content})}\n\n"