import os
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent
from langchain_core.messages import AnyMessage
from langgraph.runtime import get_runtime
from core.config import MODEL_ID, GEMINI_MODEL_ID, VLLM_URL

from .tools import (
    Context,
    find_available_dynos,
    check_vehicle_allocation,
    detect_conflicts,
    completed_tests_count,
    maintenance_check,
    query_database,
)


def format_prompt(state) -> list[AnyMessage]:
    runtime = get_runtime(Context)
    system_msg = (
        """
        You are an assistant specialized in vehicle dynamometers. 
        You are free to use any of the given tools and query any database.
        Whenever the user asks for information, use all available tools to make the response as complete as possible.
        Always respond in plain text, using correct punctuation. 
        Do not use Markdown or HTML. 
        Use lists when needed 

        For vertical numbered lists with descriptions, use this format:
        - Item 1: description
        - Item 2: description
        - Item 3: description
        End each item with a newline.
        For horizontal lists, separate items with commas. 
        Always give accurate and complete information. 
        If you don't know the answer, just say you don't know. Never make up an answer.
        """
        f"Address the user as {runtime.context.user_name}."
    )
    return [{"role": "system", "content": system_msg}] + state["messages"]


def create_agentw(model: str):
    """
    Cria e retorna um agente configurado com LLM e ferramentas.
    O `db: AsyncSession` deve ser injetado em runtime via config.
    """

    # cria LLM
    if model == "gemini":
        llm = ChatGoogleGenerativeAI(
            model=GEMINI_MODEL_ID,
            api_key=os.getenv("GEMINI_API_KEY"),
            temperature=0,
            max_tokens=None,
            timeout=None,
            max_retries=2,
        )
    elif model == "vllm":
        llm = ChatOpenAI(
            model=MODEL_ID,
            api_key="EMPTY",
            base_url=VLLM_URL,
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