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
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 1. Create users table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            is_admin BOOLEAN DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            last_login TEXT
        )
        ''')

        # 2. Create user_config table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            candidate_name TEXT,
            resume_filename TEXT,
            email_address TEXT,
            email_app_password TEXT,
            email_cc TEXT,
            job_categories TEXT,
            presencial_cities TEXT,
            search_presencial BOOLEAN DEFAULT 1,
            search_portugal BOOLEAN DEFAULT 1,
            max_jobs_per_category INTEGER DEFAULT 5,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        ''')

        # 3. Create job_queue table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS job_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            job_type TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now')),
            started_at TEXT,
            finished_at TEXT,
            result TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        ''')

        # 4. Check and add user_id column to leads table
        cursor.execute("PRAGMA table_info(leads)")
        leads_cols = [row['name'] for row in cursor.fetchall()]
        if 'user_id' not in leads_cols:
            cursor.execute("ALTER TABLE leads ADD COLUMN user_id INTEGER")
            conn.commit()

        # 5. Check and add user_id column to applications table
        cursor.execute("PRAGMA table_info(applications)")
        apps_cols = [row['name'] for row in cursor.fetchall()]
        if 'user_id' not in apps_cols:
            cursor.execute("ALTER TABLE applications ADD COLUMN user_id INTEGER")
            conn.commit()

        # 6. Recreate indexes for leads
        cursor.execute("DROP INDEX IF EXISTS idx_leads_empresa_email")
        cursor.execute('''
        CREATE UNIQUE INDEX IF NOT EXISTS idx_leads_user_empresa_email
        ON leads (user_id, empresa, email)
        ''')

        # 7. Recreate indexes for applications
        cursor.execute("DROP INDEX IF EXISTS idx_applications_empresa_vaga")
        cursor.execute("DROP INDEX IF EXISTS idx_applications_lower_keys")
        cursor.execute('''
        CREATE UNIQUE INDEX IF NOT EXISTS idx_applications_user_empresa_vaga
        ON applications (user_id, empresa, vaga)
        ''')
        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_applications_user_lower_keys
        ON applications (user_id, LOWER(empresa), LOWER(vaga))
        ''')

        # 8. Create default admin user (Paulo Neto) if users table is empty
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            from app.utils.security import hash_password
            import json

            # Default values from config.env (loaded via settings)
            admin_email = settings.EMAIL_ADDRESS if settings.EMAIL_ADDRESS else "admin@admin.com"
            admin_password = settings.DASHBOARD_PASSWORD
            admin_name = settings.CANDIDATE_NAME
            password_hash = hash_password(admin_password)

            # Insert admin user (id = 1)
            cursor.execute('''
            INSERT INTO users (email, password_hash, name, is_admin, is_active)
            VALUES (?, ?, ?, 1, 1)
            ''', (admin_email, password_hash, admin_name))
            admin_id = cursor.lastrowid

            # Insert corresponding user_config
            # Serializing category and city lists to JSON format
            categories_list = [cat.strip() for cat in settings.JOB_CATEGORIES.split(",") if cat.strip()]
            cities_list = settings.PRESENCIAL_CITIES

            cursor.execute('''
            INSERT INTO user_config (
                user_id, candidate_name, resume_filename, email_address,
                email_app_password, email_cc, job_categories, presencial_cities,
                search_presencial, search_portugal, max_jobs_per_category
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                admin_id,
                admin_name,
                settings.RESUME_PDF,
                admin_email,
                settings.EMAIL_APP_PASSWORD, # original app password (or encrypted)
                settings.EMAIL_CC,
                json.dumps(categories_list),
                json.dumps(cities_list),
                1 if settings.SEARCH_PRESENCIAL else 0,
                1 if settings.SEARCH_PORTUGAL else 0,
                settings.MAX_JOBS_PER_CATEGORY
            ))

            # 9. Migrate orphan leads and applications to the admin_id
            cursor.execute("UPDATE leads SET user_id = ? WHERE user_id IS NULL", (admin_id,))
            cursor.execute("UPDATE applications SET user_id = ? WHERE user_id IS NULL", (admin_id,))

        conn.commit()


# Initialize on import
init_db()

