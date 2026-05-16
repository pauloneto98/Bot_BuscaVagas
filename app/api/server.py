"""
FastAPI Application Server — Bot Busca Vagas
Central entry point that assembles all routers and middleware.
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.api.auth import router as auth_router
from app.api.routes.bot import router as bot_router
from app.api.routes.hunter import router as hunter_router
from app.api.routes.auto import router as auto_router
from app.api.routes.stats import router as stats_router
from app.api.routes.config import router as config_router

app = FastAPI(title="Bot Busca Vagas", version="4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:8001",
        "http://127.0.0.1:8001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all route modules
app.include_router(auth_router)
app.include_router(bot_router)
app.include_router(hunter_router)
app.include_router(auto_router)
app.include_router(stats_router)
app.include_router(config_router)


@app.get("/")
def serve_index():
    return FileResponse(os.path.join(settings.WEB_DIR, "index.html"))


# Static files must be mounted LAST (catch-all)
app.mount("/static", StaticFiles(directory=settings.WEB_DIR), name="static")
