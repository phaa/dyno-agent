import os
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain_core.messages import AnyMessage
from langgraph.runtime import get_runtime
from langgraph.checkpoint.postgres import PostgresSaver
from core.config import MODEL_ID

from .tools import (
    find_available_dynos,
    check_vehicle_allocation,
    detect_conflicts,
    completed_tests_count,
    maintenance_check,
    query_database,
)


@dataclass
class Context:
    user_name: str
    db: AsyncSession 


def format_prompt(state) -> list[AnyMessage]:
    runtime = get_runtime(Context)
    system_msg = (
        "You are a helpful assistant. "
        f"Address the user as {runtime.context.user_name}."
    )
    return [{"role": "system", "content": system_msg}] + state["messages"]


def create_agentw(checkpointer: PostgresSaver):
    """
    Cria e retorna um agente configurado com LLM e ferramentas.
    O `db: AsyncSession` deve ser injetado em runtime via config.
    """

    # cria LLM
    llm = ChatOpenAI(
        model=MODEL_ID,
        api_key="EMPTY",
        base_url=os.getenv("VLLM_URL"),
        temperature=0,
    )

    # tools já decoradas com @tool
    tools = [
        find_available_dynos,
        check_vehicle_allocation,
        detect_conflicts,
        completed_tests_count,
        maintenance_check,
        query_database,
    ]

    # cria o agente
    agent = create_agent(
        model=llm,
        tools=tools,
        prompt=format_prompt,
        context_schema=Context  
    )

    return agent