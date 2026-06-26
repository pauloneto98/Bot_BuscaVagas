import sqlite3
import json
from datetime import datetime
from app.db.connection import get_db_connection

class JobQueue:
    """Manages the SQLite-based sequential job queue for bot executions."""

    @staticmethod
    def add_job(user_id: int, job_type: str) -> int:
        """Add a new job to the queue. Returns the job ID."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            INSERT INTO job_queue (user_id, job_type, status, created_at)
            VALUES (?, ?, 'pending', datetime('now'))
            ''', (user_id, job_type))
            conn.commit()
            return cursor.lastrowid

    @staticmethod
    def get_next_pending() -> dict | None:
        """Retrieve the oldest pending job in the queue."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            SELECT * FROM job_queue 
            WHERE status = 'pending' 
            ORDER BY id ASC 
            LIMIT 1
            ''')
            row = cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    def start_job(job_id: int) -> bool:
        """Mark a job as running."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            UPDATE job_queue 
            SET status = 'running', started_at = datetime('now') 
            WHERE id = ?
            ''', (job_id,))
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def complete_job(job_id: int, result: dict = None) -> bool:
        """Mark a job as successfully completed."""
        result_str = json.dumps(result) if result else "{}"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            UPDATE job_queue 
            SET status = 'done', finished_at = datetime('now'), result = ? 
            WHERE id = ?
            ''', (result_str, job_id))
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def fail_job(job_id: int, error_msg: str) -> bool:
        """Mark a job as failed with an error message."""
        result_str = json.dumps({"error": error_msg})
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            UPDATE job_queue 
            SET status = 'error', finished_at = datetime('now'), result = ? 
            WHERE id = ?
            ''', (result_str, job_id))
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def cancel_job(job_id: int) -> bool:
        """Cancel a pending job or abort a running job."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            UPDATE job_queue 
            SET status = 'cancelled', finished_at = datetime('now'), result = '{"message": "Cancelado pelo usuario"}'
            WHERE id = ? AND status IN ('pending', 'running')
            ''', (job_id,))
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def get_job_by_id(job_id: int) -> dict | None:
        """Retrieve job details by ID."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM job_queue WHERE id = ?", (job_id,))
            row = cursor.fetchone()
            if not row:
                return None
            data = dict(row)
            try:
                data["result"] = json.loads(data["result"]) if data["result"] else {}
            except Exception:
                data["result"] = {"raw": data["result"]}
            return data

    @staticmethod
    def get_active_job_for_user(user_id: int) -> dict | None:
        """Retrieve any currently running or pending job for a specific user."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            SELECT * FROM job_queue 
            WHERE user_id = ? AND status IN ('pending', 'running') 
            ORDER BY id DESC 
            LIMIT 1
            ''', (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_queue_position(user_id: int, job_id: int) -> int:
        """Get the position of a pending job in the queue (0 if running/completed)."""
        job = JobQueue.get_job_by_id(job_id)
        if not job or job["status"] != "pending":
            return 0
            
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Count how many pending jobs with lower ID exist
            cursor.execute('''
            SELECT COUNT(*) FROM job_queue 
            WHERE status = 'pending' AND id < ?
            ''', (job_id,))
            count = cursor.fetchone()[0]
            # Position is count + 1 (1-based: 1st, 2nd, etc.)
            return count + 1
