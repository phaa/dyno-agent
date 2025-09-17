# Base image: Python 3.11 slim
FROM python:3.11-slim

# Definindo diretório de trabalho no container
WORKDIR /app

# Copiando requirements.txt e instalando dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiando o código do app
COPY . .
COPY migrations ./migrations

# Expondo a porta que o FastAPI vai rodar
EXPOSE 8000

# Comando para rodar o Uvicorn (hot reload)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]