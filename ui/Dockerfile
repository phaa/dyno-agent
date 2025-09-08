# Base image: Python 3.11 slim
FROM python:3.11-slim

# Definindo diretório de trabalho no container
WORKDIR /app

# Copiando requirements.txt e instalando dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiando o código do app
COPY . .

# Expondo a porta que o FastAPI vai rodar
EXPOSE 8501

# Comando para rodar o Streamlit (hot reload)
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
