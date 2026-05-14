"""
Data Repositories — Bot Busca Vagas
Organized query classes for Applications and Leads.
"""

import sqlite3

from app.db.connection import get_db_connection


class ApplicationRepository:
    """Handles all CRUD operations for the applications table."""

    @staticmethod
    def insert(app_data: dict) -> int | None:
        """Insert an application record. Returns the ID or None if duplicate."""
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

    @staticmethod
    def get_all() -> list[dict]:
        """Return all applications ordered by date."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM applications ORDER BY data ASC")
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_applied_keys() -> set[tuple[str, str]]:
        """Return a set of (empresa, vaga) for O(1) duplicate lookups."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT LOWER(empresa), LOWER(vaga) FROM applications")
            return {
                (str(row[0]).strip(), str(row[1]).strip())
                for row in cursor.fetchall()
                if row[0] and row[1]
            }

    @staticmethod
    def is_already_applied(empresa: str, vaga: str) -> bool:
        """Check if a specific application already exists."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM applications WHERE LOWER(empresa) = LOWER(?) AND LOWER(vaga) = LOWER(?)",
                (empresa, vaga)
            )
            return cursor.fetchone() is not None

    @staticmethod
    def update(empresa: str, vaga: str, data_dict: dict):
        """Update an application record by empresa and vaga."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            fields = []
            values = []
            for key, val in data_dict.items():
                fields.append(f"{key} = ?")
                values.append(val)
            values.extend([empresa, vaga])
            query = f"UPDATE applications SET {', '.join(fields)} WHERE empresa = ? AND vaga = ?"
            cursor.execute(query, values)
            conn.commit()


class LeadRepository:
    """Handles all CRUD operations for the leads table."""

    @staticmethod
    def insert(lead_data: dict) -> bool:
        """Insert or ignore a lead (avoids duplicates). Returns True if inserted."""
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
                return False

    @staticmethod
    def get_all() -> list[dict]:
        """Return all leads ordered by most recent first."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM leads ORDER BY id DESC")
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_pending() -> list[dict]:
        """Return only leads with status 'pending'."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM leads WHERE status = 'pending' ORDER BY id ASC")
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def update_status(lead_id: int, new_status: str):
        """Update a lead's status by ID."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE leads SET status = ? WHERE id = ?", (new_status, lead_id))
            conn.commit()

    @staticmethod
    def update_status_by_email(email: str, new_status: str):
        """Update all leads matching an email address."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE leads SET status = ? WHERE email = ?", (new_status, email))
            conn.commit()
