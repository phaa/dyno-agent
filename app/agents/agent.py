import os
from langchain_openai import ChatOpenAI
from langchain.agents import create_react_agent, AgentExecutor
from langchain_core.prompts import PromptTemplate
from langchain.prompts import ChatPromptTemplate
from .tools import allocate_tool

llm = ChatOpenAI(
    model="RedHatAI/Llama-3.2-3B-Instruct-quantized.w8a8",
    api_key="EMPTY",  # vLLM ignora a chave
    base_url=os.getenv("VLLM_URL", "http://vllm:8000/v1"),  
    temperature=0
)

tools = [allocate_tool]


prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a helpful assistant who can use tools to help with simple tasks.
You have access to these tools:

{tools}

The available tools are: {tool_names}

Follow this format:

Question: the user's question
Thought: think about what to do
Action: the tool to use, should be one of [{tool_names}]
Action Input: the input to the tool
Observation: the result of the tool
Thought: I now know the final answer
Final Answer: your final answer to the user's question"""),
    ("user", "Question: {input}\n{agent_scratchpad}")
])


# prompt = PromptTemplate.from_template(prompt_template)
agent = create_react_agent(
    llm=llm,
    tools=tools,
    prompt=prompt
)
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,
    handle_parsing_errors=True
)