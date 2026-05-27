# Dockerfile — Bot Busca Vagas (Deploy 100% na Nuvem)
FROM python:3.11-slim

# Evitar escrita de arquivos .pyc e ativar buffering do log para saída em tempo real
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

WORKDIR /app

# Instalar dependências básicas do sistema operacional
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copiar e instalar dependências do Python primeiro (otimização de cache de camadas)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Instalar navegadores do Playwright e suas dependências de sistema (para suporte a automações headless)
RUN playwright install chromium --with-deps

# Copiar o restante do código da aplicação
COPY . .

# Garantir permissão de execução no script de inicialização e converter finais de linha se salvos em Windows
RUN chmod +x start.sh && \
    sed -i 's/\r$//' start.sh

# Expor a porta padrão (usada localmente, pode ser substituída por $PORT dinamicamente na nuvem)
EXPOSE 8000

# Executar o container através do script start.sh
CMD ["./start.sh"]
