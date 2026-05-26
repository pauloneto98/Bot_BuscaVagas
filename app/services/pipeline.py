"""
Pipeline helpers — execução unificada do bot.
"""

import os
import subprocess
import sys

from app.config import settings


def run_hunter_phase(max_queries: int = 8) -> int:
    """Busca novos leads na web. Retorna código de saída do subprocesso."""
    return subprocess.run(
        [sys.executable, "-m", "app.core.hunter", "--max-queries", str(max_queries)],
        cwd=settings.BASE_DIR,
    ).returncode


def build_main_command(mode: str = "full") -> list[str]:
    """Monta comando do aplicador (main.py)."""
    cmd = [sys.executable, os.path.join(settings.BASE_DIR, "main.py")]
    if mode == "teste":
        cmd.append("--teste")
    return cmd
