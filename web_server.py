"""
Web Server — Bot Busca Vagas
Thin entry point that starts the FastAPI dashboard.
Run: python web_server.py
"""

if __name__ == "__main__":
    import os
    import uvicorn
    from app.api.server import app  # noqa: F401

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    print("\n>>> Bot Busca Vagas - Dashboard Web")
    print(f"    Abra no navegador: http://{host}:{port}\n")
    uvicorn.run(app, host=host, port=port)
