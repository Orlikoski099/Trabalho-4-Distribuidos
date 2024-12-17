# Dockerfile genérico para microsserviços
FROM python:3.10-slim

# Definir o diretório de trabalho no container
WORKDIR /app

# Instalar dependências diretamente
RUN pip install --no-cache-dir fastapi uvicorn pydantic httpx pika

# Instalar pyenv
RUN curl https://pyenv.run | bash

# Copiar o código do microsserviço para dentro do container
COPY . .

# Expor a porta padrão do FastAPI
EXPOSE 8000

# Iniciar o serviço (ajuste o nome do módulo se necessário)
CMD ["uvicorn", "sistemapgto:app", "--host", "0.0.0.0", "--port", "8000"]
