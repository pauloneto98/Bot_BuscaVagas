import sqlite3
import os
import json
from contextlib import contextmanager

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "bot_database.db")

os.makedirs(DATA_DIR, exist_ok=True)

@contextmanager
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Tabela de Leads
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa TEXT NOT NULL,
            email TEXT,
            site TEXT,
            cargo_da_vaga TEXT,
            fonte TEXT,
            status TEXT DEFAULT 'pending', -- 'pending', 'applied', 'failed', 'ignored'
            data TEXT
        )
        ''')
        
        # Adicionar restrição unique (empresa, email) - ignorando case sensitive se possível
        cursor.execute('''
        CREATE UNIQUE INDEX IF NOT EXISTS idx_leads_empresa_email 
        ON leads (empresa, email)
        ''')
        
        # Tabela de Candidaturas (Applications)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa TEXT NOT NULL,
            vaga TEXT NOT NULL,
            url TEXT,
            email_enviado BOOLEAN,
            email_destino TEXT,
            data TEXT,
            curriculo_path TEXT,
            notas TEXT
        )
        ''')
        
        cursor.execute('''
        CREATE UNIQUE INDEX IF NOT EXISTS idx_applications_empresa_vaga 
        ON applications (empresa, vaga)
        ''')
        
        conn.commit()

# Run initialization when module is imported
init_db()

# --- Helpers for Leads ---

def insert_lead(lead_data):
    """Insere ou ignora um lead (evita duplicatas)."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute('''
            INSERT INTO leads (empresa, email, site, cargo_da_vaga, fonte, data, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                lead_data.get('empresa', ''),
                lead_data.get('email', ''),
                lead_data.get('site', ''),
                lead_data.get('cargo_da_vaga', ''),
                lead_data.get('fonte', ''),
                lead_data.get('data', ''),
                lead_data.get('status', 'pending')
            ))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            # Já existe
            return False

def get_all_leads():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM leads ORDER BY id DESC")
        return [dict(row) for row in cursor.fetchall()]

def get_pending_leads():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM leads WHERE status = 'pending' ORDER BY id ASC")
        return [dict(row) for row in cursor.fetchall()]

def update_lead_status(lead_id, new_status):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE leads SET status = ? WHERE id = ?", (new_status, lead_id))
        conn.commit()
        
def update_lead_status_by_email(email, new_status):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE leads SET status = ? WHERE email = ?", (new_status, email))
        conn.commit()

# --- Helpers for Applications ---

def insert_application(app_data):
    """Insere registro de candidatura. Retorna o ID ou None se falhou/duplicou."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute('''
            INSERT INTO applications (empresa, vaga, url, email_enviado, email_destino, data, curriculo_path, notas)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                app_data.get('empresa', ''),
                app_data.get('vaga', ''),
                app_data.get('url', ''),
                app_data.get('email_enviado', False),
                app_data.get('email_destino', ''),
                app_data.get('data', ''),
                app_data.get('curriculo_path', ''),
                app_data.get('notas', '')
            ))
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None

def update_application(empresa, vaga, data_dict):
    """Atualiza registro de candidatura por empresa e vaga."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Build set clause dynamically
        fields = []
        values = []
        for key, val in data_dict.items():
            fields.append(f"{key} = ?")
            values.append(val)
            
        values.extend([empresa, vaga])
        
        query = f"UPDATE applications SET {', '.join(fields)} WHERE empresa = ? AND vaga = ?"
        cursor.execute(query, values)
        conn.commit()

def get_all_applications():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM applications ORDER BY data ASC")
        # Ordering by id/date ASC is like original json append
        return [dict(row) for row in cursor.fetchall()]

def is_already_applied(empresa, vaga):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM applications WHERE LOWER(empresa) = LOWER(?) AND LOWER(vaga) = LOWER(?)", 
                      (empresa, vaga))
        return cursor.fetchone() is not None
