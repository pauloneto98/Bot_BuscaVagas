"""
Scheduler — Bot Busca Vagas
Runs the global scheduler daemon:
1. Periodically polls all active users.
2. Checks if each user has a pending or running job.
3. If not, checks when their last job finished.
4. If it was more than X hours ago (default 4h), enqueues a new 'full_cycle' job.
"""

import time
from datetime import datetime, timezone
import sys
import io

# UTF-8 buffer adjustment for Windows console to prevent encoding issues
if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass

from app.db.repositories import UserRepository
from app.services.job_queue import JobQueue
from app.db.connection import get_db_connection

# Default cycle interval: 4 hours
INTERVAL_HOURS = 4
CHECK_INTERVAL_SECONDS = 60  # Check queue every 60 seconds

def get_last_finished_job(user_id: int) -> dict | None:
    """Retrieve the most recent finished, failed, or cancelled job for a user."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
        SELECT * FROM job_queue 
        WHERE user_id = ? AND status IN ('done', 'error', 'cancelled') 
        ORDER BY id DESC 
        LIMIT 1
        ''', (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def parse_sqlite_datetime(dt_str: str) -> datetime:
    """Parse SQLite datetime('now') string ('YYYY-MM-DD HH:MM:SS') into UTC datetime."""
    try:
        return datetime.strptime(dt_str.strip(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        try:
            return datetime.fromisoformat(dt_str.strip()).replace(tzinfo=timezone.utc)
        except Exception:
            return datetime.now(timezone.utc)

def run_scheduler():
    print("=" * 60)
    print("BOT BUSCA VAGAS - AGENDADOR GLOBAL MULTI-USUÁRIO ATIVADO")
    print("=" * 60)
    print(f"Intervalo de ciclo automático: {INTERVAL_HOURS} horas por usuário.")
    print("Aguardando verificação periódica...")
    print("Pressione CTRL+C para parar a qualquer momento.\n")

    while True:
        try:
            # Get all users
            users = UserRepository.get_all()
            active_users = [u for u in users if u.get("is_active") == 1]
            
            now_utc = datetime.now(timezone.utc)
            
            for user in active_users:
                user_id = user["id"]
                user_name = user["name"]
                user_email = user["email"]
                
                # Check for active job
                active_job = JobQueue.get_active_job_for_user(user_id)
                if active_job:
                    # User already has a job running or pending in queue
                    continue
                
                # Check last completed job
                last_job = get_last_finished_job(user_id)
                should_enqueue = False
                reason = ""
                
                if not last_job:
                    # User has never run a job, run first cycle
                    should_enqueue = True
                    reason = "Primeiro ciclo do usuário"
                else:
                    finished_at_str = last_job.get("finished_at")
                    if not finished_at_str:
                        should_enqueue = True
                        reason = "Último job sem data de finalização"
                    else:
                        finished_at_dt = parse_sqlite_datetime(finished_at_str)
                        elapsed_seconds = (now_utc - finished_at_dt).total_seconds()
                        elapsed_hours = elapsed_seconds / 3600.0
                        
                        if elapsed_hours >= INTERVAL_HOURS:
                            should_enqueue = True
                            reason = f"Último ciclo finalizado há {elapsed_hours:.1f} horas (limite {INTERVAL_HOURS}h)"
                
                if should_enqueue:
                    print(f"[{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}] [Scheduler] Enfileirando 'full_cycle' para {user_name} ({user_email}) | Motivo: {reason}")
                    job_id = JobQueue.add_job(user_id, "full_cycle")
                    print(f"  -> Job #{job_id} adicionado com sucesso.")
            
        except Exception as e:
            print(f"[Scheduler] Erro no ciclo do agendador: {e}")
            
        time.sleep(CHECK_INTERVAL_SECONDS)

if __name__ == "__main__":
    try:
        run_scheduler()
    except KeyboardInterrupt:
        print("\nAgendador parado pelo usuário.")
