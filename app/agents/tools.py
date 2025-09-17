from langchain.tools import Tool
from services.allocator import allocate_dyno_transactional

allocate_tool = Tool(
    name="AllocateDyno",
    func=allocate_dyno_transactional,  # função que já existe no FastAPI
    description="Aloca um dyno para um veículo com base em tipo de teste, peso, tração e datas."
)