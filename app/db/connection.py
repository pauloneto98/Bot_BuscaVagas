"""
Database Connection & Schema — Bot Busca Vagas
Manages SQLite connection and table initialization.
"""

import os
import sqlite3
from contextlib import contextmanager

from app.config import settings

DB_PATH = os.path.join(settings.DATA_DIR, "bot_database.db")


@contextmanager
def get_db_connection():
    """Context manager for SQLite connections with Row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """Create all tables and indexes if they don't exist."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Leads table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa TEXT NOT NULL,
            email TEXT,
            site TEXT,
            cargo_da_vaga TEXT,
            fonte TEXT,
            status TEXT DEFAULT 'pending',
            data TEXT
        )
        ''')

        cursor.execute('''
        CREATE UNIQUE INDEX IF NOT EXISTS idx_leads_empresa_email
        ON leads (empresa, email)
        ''')

        # Applications table
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

        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_applications_lower_keys
        ON applications (LOWER(empresa), LOWER(vaga))
        ''')

        conn.commit()


# Initialize on import
init_db()
