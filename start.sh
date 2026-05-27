#!/bin/bash
# start.sh — Script de inicialização concorrente do Bot Busca Vagas

# Sair imediatamente se algum comando falhar
set -e

echo "============================================================"
echo "🤖 INICIANDO BOT BUSCA VAGAS NA NUVEM"
echo "============================================================"

# Função para propagar sinais de parada do container
cleanup() {
    echo "⏹ Sinais de interrupção recebidos. Encerrando processos..."
    kill -TERM "$scheduler_pid" 2>/dev/null || true
    kill -TERM "$web_pid" 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM

# Garantir que a pasta de dados persistente exista
mkdir -p data/curriculos

# 1. Iniciar o agendador em background
echo "🚀 Iniciando Agendador de Candidaturas Contínuo (24/7)..."
python run_scheduler.py > data/bot_scheduler.log 2>&1 &
scheduler_pid=$!

# 2. Iniciar o servidor web FastAPI/Uvicorn em foreground
echo "💻 Iniciando Servidor do Dashboard Web..."
python web_server.py &
web_pid=$!

# Aguardar os processos terminarem
wait "$web_pid" "$scheduler_pid"
