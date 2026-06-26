"""
Data Repositories — Bot Busca Vagas
Organized query classes for Applications and Leads.
"""

import sqlite3

from app.db.connection import get_db_connection


class ApplicationRepository:
    """Handles all CRUD operations for the applications table with user isolation."""

    @staticmethod
    def insert(app_data: dict, user_id: int) -> int | None:
        """Insert an application record. Returns the ID or None if duplicate."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                INSERT INTO applications (user_id, empresa, vaga, url, email_enviado, email_destino, data, curriculo_path, notas)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user_id,
                    app_data.get('empresa', ''),
                    app_data.get('vaga', ''),
                    app_data.get('url', ''),
                    app_data.get('email_enviado', False),
                    app_data.get('email_destino', ''),
                    app_data.get('data', ''),
                    app_data.get('curriculo_path', ''),
                    app_data.get('notes', app_data.get('notas', ''))  # supports both naming styles
                ))
                conn.commit()
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                return None

    @staticmethod
    def get_all(user_id: int) -> list[dict]:
        """Return all applications for a specific user ordered by date."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM applications WHERE user_id = ? ORDER BY data ASC", (user_id,))
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_applied_keys(user_id: int) -> set[tuple[str, str]]:
        """Return a set of (empresa, vaga) for O(1) duplicate lookups for a specific user."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT LOWER(empresa), LOWER(vaga) FROM applications WHERE user_id = ?", (user_id,))
            return {
                (str(row[0]).strip(), str(row[1]).strip())
                for row in cursor.fetchall()
                if row[0] and row[1]
            }

    @staticmethod
    def is_already_applied(empresa: str, vaga: str, user_id: int) -> bool:
        """Check if a specific application already exists for a user."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM applications WHERE user_id = ? AND LOWER(empresa) = LOWER(?) AND LOWER(vaga) = LOWER(?)",
                (user_id, empresa, vaga)
            )
            return cursor.fetchone() is not None

    @staticmethod
    def update(empresa: str, vaga: str, data_dict: dict, user_id: int):
        """Update an application record by empresa, vaga, and user_id."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            fields = []
            values = []
            for key, val in data_dict.items():
                fields.append(f"{key} = ?")
                values.append(val)
            values.extend([user_id, empresa, vaga])
            query = f"UPDATE applications SET {', '.join(fields)} WHERE user_id = ? AND empresa = ? AND vaga = ?"
            cursor.execute(query, values)
            conn.commit()


class LeadRepository:
    """Handles all CRUD operations for the leads table with user isolation."""

    @staticmethod
    def insert(lead_data: dict, user_id: int) -> bool:
        """Insert or ignore a lead (avoids duplicates). Returns True if inserted."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                INSERT INTO leads (user_id, empresa, email, site, cargo_da_vaga, fonte, data, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user_id,
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
    def get_all(user_id: int) -> list[dict]:
        """Return all leads for a user ordered by most recent first."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM leads WHERE user_id = ? ORDER BY id DESC", (user_id,))
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_pending(user_id: int) -> list[dict]:
        """Return only leads with status 'pending' for a user."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM leads WHERE user_id = ? AND status = 'pending' ORDER BY id ASC", (user_id,))
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def update_status(lead_id: int, new_status: str, user_id: int):
        """Update a lead's status by ID and user_id."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE leads SET status = ? WHERE id = ? AND user_id = ?", (new_status, lead_id, user_id))
            conn.commit()

    @staticmethod
    def update_status_by_email(email: str, new_status: str, user_id: int):
        """Update all leads matching an email address and user_id."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE leads SET status = ? WHERE email = ? AND user_id = ?", (new_status, email, user_id))
            conn.commit()

    @staticmethod
    def update_lead(lead_id: int, lead_data: dict, user_id: int):
        """Update lead details by ID and user_id."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            UPDATE leads 
            SET empresa = ?, email = ?, site = ?, cargo_da_vaga = ?, fonte = ?, status = ?
            WHERE id = ? AND user_id = ?
            ''', (
                lead_data.get('empresa', ''),
                lead_data.get('email', ''),
                lead_data.get('site', ''),
                lead_data.get('cargo_da_vaga', ''),
                lead_data.get('fonte', ''),
                lead_data.get('status', 'pending'),
                lead_id,
                user_id
            ))
            conn.commit()

    @staticmethod
    def delete_lead(lead_id: int, user_id: int):
        """Delete a lead by ID and user_id."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM leads WHERE id = ? AND user_id = ?", (lead_id, user_id))
            conn.commit()



class UserRepository:
    """Handles CRUD operations for the users table."""

    @staticmethod
    def create(user_data: dict) -> int | None:
        """Create a new user. Returns user ID or None if email already exists."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                INSERT INTO users (email, password_hash, name, is_admin, is_active)
                VALUES (?, ?, ?, ?, ?)
                ''', (
                    user_data.get('email', '').lower().strip(),
                    user_data.get('password_hash', ''),
                    user_data.get('name', '').strip(),
                    1 if user_data.get('is_admin', False) else 0,
                    1 if user_data.get('is_active', True) else 0
                ))
                conn.commit()
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                return None

    @staticmethod
    def get_by_email(email: str) -> dict | None:
        """Find a user by email."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE LOWER(email) = LOWER(?)", (email.strip(),))
            row = cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_by_id(user_id: int) -> dict | None:
        """Find a user by ID."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_all() -> list[dict]:
        """List all users for admin review."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, email, name, is_admin, is_active, created_at, last_login FROM users ORDER BY id ASC")
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def update_last_login(user_id: int):
        """Update last login timestamp to now."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET last_login = datetime('now') WHERE id = ?", (user_id,))
            conn.commit()

    @staticmethod
    def update_status(user_id: int, is_active: bool):
        """Enable or disable user account."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET is_active = ? WHERE id = ?", (1 if is_active else 0, user_id))
            conn.commit()

    @staticmethod
    def update_password(user_id: int, password_hash: str):
        """Update user password hash."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))
            conn.commit()

    @staticmethod
    def delete(user_id: int) -> bool:
        """Delete a user. Returns True if deleted."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
            return cursor.rowcount > 0


class UserConfigRepository:
    """Handles CRUD operations for user configurations (Multi-Tenant settings)."""

    @staticmethod
    def get_by_user_id(user_id: int) -> dict | None:
        """Get configurations for a specific user."""
        import json
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM user_config WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if not row:
                return None
            
            data = dict(row)
            # Deserialize JSON fields
            try:
                data['job_categories'] = json.loads(data['job_categories']) if data['job_categories'] else []
            except Exception:
                data['job_categories'] = []
            
            try:
                data['presencial_cities'] = json.loads(data['presencial_cities']) if data['presencial_cities'] else []
            except Exception:
                data['presencial_cities'] = []
                
            return data

    @staticmethod
    def save(user_id: int, config_data: dict) -> bool:
        """Save user configurations (inserts if new, updates if exists)."""
        import json
        # Ensure categories and cities are stored as JSON strings
        cats = config_data.get('job_categories', [])
        cities = config_data.get('presencial_cities', [])
        
        cats_str = json.dumps(cats) if isinstance(cats, list) else str(cats)
        cities_str = json.dumps(cities) if isinstance(cities, list) else str(cities)

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM user_config WHERE user_id = ?", (user_id,))
            exists = cursor.fetchone() is not None

            if exists:
                cursor.execute('''
                UPDATE user_config SET
                    candidate_name = ?,
                    resume_filename = ?,
                    email_address = ?,
                    email_app_password = ?,
                    email_cc = ?,
                    job_categories = ?,
                    presencial_cities = ?,
                    search_presencial = ?,
                    search_portugal = ?,
                    max_jobs_per_category = ?
                WHERE user_id = ?
                ''', (
                    config_data.get('candidate_name', ''),
                    config_data.get('resume_filename', ''),
                    config_data.get('email_address', ''),
                    config_data.get('email_app_password', ''),
                    config_data.get('email_cc', ''),
                    cats_str,
                    cities_str,
                    1 if config_data.get('search_presencial', True) else 0,
                    1 if config_data.get('search_portugal', True) else 0,
                    config_data.get('max_jobs_per_category', 5),
                    user_id
                ))
            else:
                cursor.execute('''
                INSERT INTO user_config (
                    user_id, candidate_name, resume_filename, email_address,
                    email_app_password, email_cc, job_categories, presencial_cities,
                    search_presencial, search_portugal, max_jobs_per_category
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user_id,
                    config_data.get('candidate_name', ''),
                    config_data.get('resume_filename', ''),
                    config_data.get('email_address', ''),
                    config_data.get('email_app_password', ''),
                    config_data.get('email_cc', ''),
                    cats_str,
                    cities_str,
                    1 if config_data.get('search_presencial', True) else 0,
                    1 if config_data.get('search_portugal', True) else 0,
                    config_data.get('max_jobs_per_category', 5)
                ))
            conn.commit()
            return True


