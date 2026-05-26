@echo off
cd /d "C:\Bot_Busca_Vaga-20260428T205807Z-3-001\bot_curriculo"
python desktop_app.py
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERRO] O aplicativo encontrou um problema.
    pause
)
