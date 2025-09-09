import os
from fastapi import FastAPI
from openai import OpenAI
from models import ChatRequest

client = OpenAI(
    api_key="EMPTY",
    base_url=os.getenv("VLLM_URL", "http://vllm:8080/v1")
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


