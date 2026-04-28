"""
Módulo de Logger/Histórico — v2
Registra candidaturas enviadas, evita duplicatas, exporta CSV e relatórios.
"""

import csv
import json
import os
from datetime import datetime, date

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
CSV_FILE = os.path.join(DATA_DIR, "candidaturas.csv")


def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def load_history() -> dict:
    _ensure_data_dir()
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"candidaturas": []}


def save_history(history: dict):
    _ensure_data_dir()
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def is_already_applied(history: dict, empresa: str, titulo_vaga: str) -> bool:
    for c in history.get("candidaturas", []):
        if (c["empresa"].lower() == empresa.lower() and
                c["vaga"].lower() == titulo_vaga.lower()):
            return True
    return False


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
    """Registra uma nova candidatura no histórico."""
    entry = {
        "data": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "empresa": empresa,
        "vaga": titulo_vaga,
        "url": url,
        "email_enviado": email_enviado,
        "email_destino": email_destino,
        "curriculo_gerado": curriculo_path,
        "notas": notas,
    }
    history["candidaturas"].append(entry)
    save_history(history)
    _append_csv(entry)
    return entry


def _append_csv(entry: dict):
    """Acrescenta uma entrada ao CSV de histórico."""
    _ensure_data_dir()
    file_exists = os.path.exists(CSV_FILE)
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "data", "empresa", "vaga", "url",
            "email_enviado", "email_destino", "curriculo_gerado", "notas",
        ])
        if not file_exists:
            writer.writeheader()
        writer.writerow(entry)


def get_stats(history: dict) -> dict:
    """Retorna estatísticas gerais das candidaturas."""
    candidaturas = history.get("candidaturas", [])
    total = len(candidaturas)
    enviados = sum(1 for c in candidaturas if c.get("email_enviado"))
    hoje = date.today().strftime("%Y-%m-%d")
    hoje_count = sum(1 for c in candidaturas if c.get("data", "").startswith(hoje))

    # Por fonte (se disponível no campo notas ou url)
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


def get_recent(history: dict, n: int = 10) -> list[dict]:
    """Retorna as N candidaturas mais recentes."""
    return list(reversed(history.get("candidaturas", [])))[:n]


def export_csv() -> str:
    """Retorna o caminho do CSV exportado (ou mensagem de erro)."""
    if os.path.exists(CSV_FILE):
        return CSV_FILE
    return ""
