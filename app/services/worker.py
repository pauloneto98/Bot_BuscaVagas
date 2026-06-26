"""
Sequential Job Queue Worker — Bot Busca Vagas
Polls the SQLite job_queue sequentially, running 1 job at a time to stay under 1GB RAM on EC2 t3.micro.
"""

import os
import sys
import time
import subprocess
from datetime import datetime
from app.config import settings
from app.services.job_queue import JobQueue

def run_worker():
    print("=" * 60)
    print("BOT BUSCA VAGAS - WORKER DA FILA SEQUENCIAL ATIVADO")
    print("=" * 60)
    print("Aguardando novos jobs na fila do SQLite...")
    print("Pressione CTRL+C para parar a qualquer momento.\n")

    while True:
        try:
            job = JobQueue.get_next_pending()
            if not job:
                time.sleep(5)
                continue

            job_id = job["id"]
            user_id = job["user_id"]
            job_type = job["job_type"]

            print(f"\n[Worker] Processando Job #{job_id} | Tipo: {job_type} | Usuário: {user_id}")
            
            # 1. Marcar como iniciado
            if not JobQueue.start_job(job_id):
                print(f"[Worker] Falha ao iniciar Job #{job_id} (talvez cancelado/iniciado por outro worker).")
                continue

            # 2. Configurar arquivo de log do usuário
            from app.utils.paths import get_user_log_file
            log_file = get_user_log_file(user_id, "bot.log")
            
            # Sobrescrever o arquivo de log para o novo ciclo do usuário
            try:
                with open(log_file, "w", encoding="utf-8") as f:
                    f.write(f"=== Iniciando Execução - Job #{job_id} às {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
            except Exception as e:
                print(f"[Worker] Erro ao preparar log_file: {e}")

            # 3. Montar comandos baseados no tipo de job
            # Se for teste, rodamos main.py com --teste
            # Se for hunter_only, rodamos app.core.hunter
            # Se for apply_only, rodamos main.py
            # Se for full_cycle, rodamos app.core.hunter depois main.py
            commands = []
            if job_type == "teste":
                commands.append([sys.executable, os.path.join(settings.BASE_DIR, "main.py"), "--teste", "--user-id", str(user_id)])
            elif job_type == "hunter_only":
                commands.append([sys.executable, "-m", "app.core.hunter"])
            elif job_type == "apply_only":
                commands.append([sys.executable, os.path.join(settings.BASE_DIR, "main.py"), "--user-id", str(user_id)])
            elif job_type == "full_cycle":
                commands.append([sys.executable, "-m", "app.core.hunter"])
                commands.append([sys.executable, os.path.join(settings.BASE_DIR, "main.py"), "--user-id", str(user_id)])
            else:
                print(f"[Worker] Tipo de job desconhecido: {job_type}")
                JobQueue.fail_job(job_id, f"Tipo de job desconhecido: {job_type}")
                continue

            # 4. Configurar ambiente para o subprocesso
            child_env = os.environ.copy()
            child_env["PYTHONUNBUFFERED"] = "1"
            child_env["CURRENT_USER_ID"] = str(user_id)
            # Para desabilitar Playwright no servidor, passamos SERVER_MODE=true
            child_env["SERVER_MODE"] = "true"

            success = True
            error_msg = ""

            for cmd in commands:
                print(f"[Worker] Rodando comando: {' '.join(cmd)}")
                try:
                    with open(log_file, "a", encoding="utf-8") as log_f:
                        # Executar o subprocesso
                        proc = subprocess.Popen(
                            cmd,
                            stdout=log_f,
                            stderr=subprocess.STDOUT,
                            cwd=settings.BASE_DIR,
                            env=child_env,
                        )

                        # Loop de acompanhamento para permitir cancelamento do job
                        while proc.poll() is None:
                            # Verificar se o usuário cancelou o job no banco
                            current_job = JobQueue.get_job_by_id(job_id)
                            if not current_job or current_job["status"] == "cancelled":
                                print(f"[Worker] Job #{job_id} cancelado pelo usuário. Terminando subprocesso...")
                                proc.terminate()
                                try:
                                    proc.wait(timeout=5)
                                except subprocess.TimeoutExpired:
                                    proc.kill()
                                success = False
                                error_msg = "Cancelado pelo usuário"
                                break
                            time.sleep(2)

                        if not success:
                            break

                        if proc.returncode != 0:
                            success = False
                            error_msg = f"Comando falhou com código de saída {proc.returncode}"
                            break

                except Exception as e:
                    success = False
                    error_msg = f"Erro ao executar subprocesso: {str(e)}"
                    print(f"[Worker] Erro ao rodar comando: {e}")
                    break

            # 5. Atualizar o status do job no banco
            current_job = JobQueue.get_job_by_id(job_id)
            if current_job and current_job["status"] == "cancelled":
                print(f"[Worker] Job #{job_id} encerrado como cancelado.")
            elif success:
                print(f"[Worker] Job #{job_id} concluído com sucesso!")
                JobQueue.complete_job(job_id, {"status": "success", "finished_at": datetime.now().isoformat()})
            else:
                print(f"[Worker] Job #{job_id} falhou: {error_msg}")
                JobQueue.fail_job(job_id, error_msg)

        except KeyboardInterrupt:
            print("\n[Worker] Parando worker sequencial.")
            break
        except Exception as e:
            print(f"[Worker] Erro inesperado no loop principal: {e}")
            time.sleep(5)

if __name__ == "__main__":
    run_worker()
