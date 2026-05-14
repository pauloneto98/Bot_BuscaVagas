@echo off
title Bot Busca Vagas - MODO AUTONOMO (24/7)
color 0b

echo ==========================================================
echo        INICIANDO MODO AUTOMATICO CONTINUO
echo ==========================================================
echo O seu computador pode ficar ligado.
echo O bot ira buscar vagas e se candidatar em ciclos.
echo Para cancelar a qualquer momento, aperte CTRL + C ou feche a janela.
echo ==========================================================
echo.

python scripts\run_247.py

pause
