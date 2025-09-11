import os
from fastapi import FastAPI
from openai import OpenAI
from sqlalchemy import create_engine, text
from models import Base
from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str


DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://dyno_user:dyno_pass@db:5432/dyno_db")
engine = create_engine(DATABASE_URL)
Base.metadata.create_all(engine)

client = OpenAI(
    api_key="EMPTY",
    base_url=os.getenv("VLLM_URL", "http://vllm:8000/v1")
)

app = FastAPI()


@app.get("/hello")
def hello():
    return {"message": "Hello, World!"}

@app.post("/chat")
def chat(request: ChatRequest):
    response = client.chat.completions.create(
        model="RedHatAI/Llama-3.2-3B-Instruct-quantized.w8a8",
        messages=[
            {"role": "user", "content": request.message}
        ]
    )
    return {"response": response.choices[0].message.content}

@app.get("/vehicles")
def get_vehicles():
    with engine.connect() as connection:
        result = connection.execute(text("SELECT * FROM vehicles"))
        vehicles = [dict(row) for row in result]
    return {"vehicles": vehicles}