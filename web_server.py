"""
Web Server — Bot Busca Vagas
Thin entry point that starts the FastAPI dashboard.
Run: python web_server.py
"""

if __name__ == "__main__":
    import uvicorn
    from app.api.server import app  # noqa: F401

    print("\n>>> Bot Busca Vagas - Dashboard Web")
    print("    Abra no navegador: http://localhost:8000\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
