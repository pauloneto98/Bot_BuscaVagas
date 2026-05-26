"""
Metrics & Application Logger — Bot Busca Vagas
Tracks API usage, application history, and exports reports.
Merged from the original modules/logger.py and modules/metrics.py.
"""

import csv
import json
import os
from datetime import datetime, date

from app.config import settings
from app.db.repositories import ApplicationRepository

# ── Paths ──────────────────────────────────────────────────────────
CSV_FILE = os.path.join(settings.DATA_DIR, "candidaturas.csv")
MD_FILE = os.path.join(settings.DATA_DIR, "candidaturas_enviadas.md")


def _ensure_data_dir():
    os.makedirs(settings.DATA_DIR, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════
#  METRICS
# ═══════════════════════════════════════════════════════════════════

_metrics = {
    "rate_limit_hits": 0,
    "gemini_calls": 0,
    "fallbacks_used": 0,
}


def inc_rate_limit():
    _metrics["rate_limit_hits"] += 1
    _persist_metrics()


def inc_call():
    _metrics["gemini_calls"] += 1
    _persist_metrics()


def inc_fallback():
    _metrics["fallbacks_used"] += 1
    _persist_metrics()


def _persist_metrics():
    _ensure_data_dir()
    with open(settings.METRICS_FILE, "w", encoding="utf-8") as f:
        json.dump(_metrics, f, indent=2)


def export_metrics(path: str | None = None):
    if path is None:
        path = settings.METRICS_FILE
    _persist_metrics()
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ═══════════════════════════════════════════════════════════════════
#  APPLICATION HISTORY
# ═══════════════════════════════════════════════════════════════════

def load_history() -> dict:
    """Legacy wrapper for backward compatibility."""
    return {"candidaturas": ApplicationRepository.get_all()}


def save_history(history: dict):
    """Legacy no-op (SQLite handles persistence)."""
    pass


def build_applied_set(history: dict = None) -> set[tuple[str, str]]:
    """Create a set of (empresa, vaga) for O(1) duplicate lookups."""
    return ApplicationRepository.get_applied_keys()


def is_already_applied(history: dict, empresa: str, titulo_vaga: str) -> bool:
    """Check if an application already exists in the database."""
    return ApplicationRepository.is_already_applied(empresa, titulo_vaga)


def log_application(
    history: dict,
    empresa: str,
    titulo_vaga: str,
    url: str,
    email_enviado: bool,
    email_destino: str = "",
    curriculo_path: str = "",
    notas: str = "",
) -> dict:
    """Record a new application in the database, CSV, and Markdown."""
    entry = {
        "data": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "empresa": empresa,
        "vaga": titulo_vaga,
        "url": url,
        "email_enviado": email_enviado,
        "email_destino": email_destino,
        "curriculo_path": curriculo_path,
        "notas": notas,
    }

    ApplicationRepository.insert(entry)

    if "candidaturas" in history:
        history["candidaturas"].append(entry)

    _append_csv(entry)
    _append_md(entry)
    return entry


def _append_csv(entry: dict):
    """Append an entry to the CSV history file."""
    _ensure_data_dir()
    file_exists = os.path.exists(CSV_FILE)
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "data", "empresa", "vaga", "url",
            "email_enviado", "email_destino", "curriculo_path", "notas",
        ])
        if not file_exists:
            writer.writeheader()
        writer.writerow(entry)


def _append_md(entry: dict):
    """Append the application to a Markdown report if email was sent."""
    if not entry.get("email_enviado"):
        return

    _ensure_data_dir()
    file_exists = os.path.exists(MD_FILE)

    with open(MD_FILE, "a", encoding="utf-8") as f:
        if not file_exists:
            f.write("# Relatorio de Candidaturas Enviadas\n\n")
            f.write("| Data | Empresa | Vaga | Email de Destino | Arquivo CV |\n")
            f.write("|------|---------|------|------------------|------------|\n")

        cv_name = os.path.basename(entry.get('curriculo_path', ''))
        f.write(f"| {entry['data']} | **{entry['empresa']}** | {entry['vaga']} | `{entry.get('email_destino', '')}` | `{cv_name}` |\n")


def get_stats(history: dict = None) -> dict:
    """Return aggregate statistics from the database."""
    candidaturas = ApplicationRepository.get_all()
    total = len(candidaturas)
    enviados = sum(1 for c in candidaturas if c.get("email_enviado"))
    hoje = date.today().strftime("%Y-%m-%d")
    hoje_count = sum(1 for c in candidaturas if str(c.get("data", "")).startswith(hoje))

    por_empresa: dict[str, int] = {}
    for c in candidaturas:
        emp = c.get("empresa", "Desconhecida")
        por_empresa[emp] = por_empresa.get(emp, 0) + 1

    return {
        "total_vagas_encontradas": total,
        "emails_enviados": enviados,
        "sem_email": total - enviados,
        "candidaturas_hoje": hoje_count,
        "top_empresas": sorted(por_empresa.items(), key=lambda x: -x[1])[:5],
    }


def get_recent(history: dict = None, n: int = 10) -> list[dict]:
    """Return the N most recent applications."""
    apps = ApplicationRepository.get_all()
    return list(reversed(apps))[:n]


def export_csv() -> str:
    """Return the path to the exported CSV file."""
    if os.path.exists(CSV_FILE):
        return CSV_FILE
    return ""
