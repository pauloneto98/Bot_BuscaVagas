import os
import sys
import json
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from modules.database import insert_lead, insert_application, get_db_connection

DATA_DIR = os.path.join(BASE_DIR, "data")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
LEADS_FILE = os.path.join(DATA_DIR, "leads_ti.json")
MANUAL_FILE = os.path.join(DATA_DIR, "emails_tech_compilado.json")

def migrate_history():
    print("Migrando history.json...")
    if not os.path.exists(HISTORY_FILE):
        print("  history.json não encontrado. Pulando.")
        return

    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            candidaturas = data.get("candidaturas", [])
        except Exception as e:
            print(f"  Erro ao ler history.json: {e}")
            return
    
    count = 0
    for c in candidaturas:
        app_data = {
            "empresa": c.get("empresa", "Desconhecida"),
            "vaga": c.get("vaga", "Desconhecida"),
            "url": c.get("url", ""),
            "email_enviado": bool(c.get("email_enviado", False)),
            "email_destino": c.get("email_destino", ""),
            "data": c.get("data", ""),
            "curriculo_path": c.get("curriculo_gerado", ""),
            "notas": c.get("notas", "")
        }
        res = insert_application(app_data)
        if res:
            count += 1
            
    print(f"  {count} candidaturas migradas com sucesso.")

def migrate_leads():
    print("Migrando leads_ti.json...")
    if not os.path.exists(LEADS_FILE):
        print("  leads_ti.json não encontrado. Pulando.")
        return

    with open(LEADS_FILE, "r", encoding="utf-8") as f:
        try:
            leads = json.load(f)
        except Exception as e:
            print(f"  Erro ao ler leads_ti.json: {e}")
            return
            
    count = 0
    for l in leads:
        lead_data = {
            "empresa": l.get("empresa", ""),
            "email": l.get("email", ""),
            "site": l.get("site", ""),
            "cargo_da_vaga": l.get("cargo_da_vaga", ""),
            "fonte": l.get("fonte", "Email Hunter"),
            "data": l.get("data", datetime.now().strftime("%Y-%m-%d")),
            "status": "pending"
        }
        if lead_data["empresa"] and lead_data["email"]:
            res = insert_lead(lead_data)
            if res: count += 1
            
    print(f"  {count} leads do Hunter migrados com sucesso.")

def migrate_manual():
    print("Migrando emails_tech_compilado.json...")
    if not os.path.exists(MANUAL_FILE):
        print("  emails_tech_compilado.json não encontrado. Pulando.")
        return

    with open(MANUAL_FILE, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            agencias = data.get("agencias_rh", [])
        except Exception as e:
            print(f"  Erro ao ler emails_tech_compilado.json: {e}")
            return
            
    count = 0
    for l in agencias:
        lead_data = {
            "empresa": l.get("nome", ""),
            "email": l.get("email", ""),
            "site": l.get("site", ""),
            "cargo_da_vaga": l.get("especialidade", "Tecnologia"),
            "fonte": "JSON Compilado (Manual)",
            "data": datetime.now().strftime("%Y-%m-%d"),
            "status": "pending"
        }
        if lead_data["empresa"] and lead_data["email"]:
            res = insert_lead(lead_data)
            if res: count += 1
            
    print(f"  {count} leads manuais migrados com sucesso.")

if __name__ == "__main__":
    print("Iniciando migração de dados para SQLite...")
    migrate_history()
    migrate_leads()
    migrate_manual()
    print("Migração concluída!")
