"""
Módulo de Logger/Histórico — v2 (Refatorado para SQLite)
Registra candidaturas enviadas, evita duplicatas, exporta CSV e relatórios.
"""

import csv
import os
from datetime import datetime, date

from modules.database import (
    insert_application,
    get_all_applications,
    is_already_applied as db_is_already_applied
)

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
CSV_FILE = os.path.join(DATA_DIR, "candidaturas.csv")
MD_FILE = os.path.join(DATA_DIR, "candidaturas_enviadas.md")


def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def load_history() -> dict:
    """Função legada mantida para compatibilidade temporária."""
    return {"candidaturas": get_all_applications()}


def save_history(history: dict):
    """Função legada. Não faz nada agora que usamos SQLite."""
    pass


def build_applied_set(history: dict = None) -> set[tuple[str, str]]:
    """Cria um set (O(1) lookup) com as vagas já aplicadas para busca super rápida."""
    applied = set()
    apps = get_all_applications()
    for c in apps:
        empresa = c.get("empresa", "").strip().lower()
        vaga = c.get("vaga", "").strip().lower()
        applied.add((empresa, vaga))
    return applied

def is_already_applied(history: dict, empresa: str, titulo_vaga: str) -> bool:
    """Verifica no banco se a vaga já foi aplicada."""
    return db_is_already_applied(empresa, titulo_vaga)


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
    """Registra uma nova candidatura no histórico (Banco de Dados)."""
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
    
    insert_application(entry)
    
    if "candidaturas" in history:
        history["candidaturas"].append(entry)
        
    _append_csv(entry)
    _append_md(entry)
    return entry


def _append_csv(entry: dict):
    """Acrescenta uma entrada ao CSV de histórico."""
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
    """Acrescenta a vaga no Markdown caso o email tenha sido enviado."""
    if not entry.get("email_enviado"):
        return
        
    _ensure_data_dir()
    file_exists = os.path.exists(MD_FILE)
    
    with open(MD_FILE, "a", encoding="utf-8") as f:
        if not file_exists:
            f.write("# 📋 Relatório de Candidaturas Enviadas\n\n")
            f.write("| Data | Empresa | Vaga | Email de Destino | Arquivo CV |\n")
            f.write("|------|---------|------|------------------|------------|\n")
            
        cv_name = os.path.basename(entry.get('curriculo_path', ''))
        f.write(f"| {entry['data']} | **{entry['empresa']}** | {entry['vaga']} | `{entry.get('email_destino', '')}` | `{cv_name}` |\n")


def get_stats(history: dict = None) -> dict:
    """Retorna estatísticas gerais das candidaturas direto do banco."""
    candidaturas = get_all_applications()
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
    """Retorna as N candidaturas mais recentes."""
    apps = get_all_applications()
    return list(reversed(apps))[:n]


def export_csv() -> str:
    """Retorna o caminho do CSV exportado (ou mensagem de erro)."""
    if os.path.exists(CSV_FILE):
        return CSV_FILE
    return ""
