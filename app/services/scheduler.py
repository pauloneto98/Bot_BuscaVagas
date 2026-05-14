"""
Scheduler — Bot Busca Vagas
Runs the full pipeline in continuous 24/7 cycles:
  1. Email Hunter (lead discovery)
  2. Job Applicator (resume sending)
  3. Cooldown (human-like pacing)
"""

import io
import os
import random
import subprocess
import sys
import time
from datetime import datetime

if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass

from app.config import settings

BASE_DIR = settings.BASE_DIR


def run_continuous():
    print("=" * 60)
    print("BOT BUSCA VAGAS - MODO CONTINUO (24/7) ATIVADO")
    print("=" * 60)
    print("O bot rodara em ciclos continuos, intercalando:")
    print("1. Busca de novas empresas (Email Hunter)")
    print("2. Aplicacao em vagas (Web e E-mail)")
    print("3. Descanso (para simular comportamento humano)")
    print("Pressione CTRL+C para parar a qualquer momento.\n")

    ciclo = 1
    while True:
        print(f"\n{'=' * 60}")
        print(f"INICIANDO CICLO #{ciclo} - {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        print(f"{'=' * 60}\n")

        # 1. Run Hunter
        print(">>> ETAPA 1: CACADOR DE LEADS (Buscando novas empresas na web)")
        subprocess.run(
            [sys.executable, "-m", "app.core.hunter", "--max-queries", "8"],
            cwd=BASE_DIR
        )

        time.sleep(10)

        # 2. Run main applicator
        print("\n>>> ETAPA 2: APLICADOR (Candidatando-se as vagas encontradas)")
        subprocess.run(
            [sys.executable, os.path.join(BASE_DIR, "main.py")],
            cwd=BASE_DIR
        )

        # 3. Cooldown
        delay_minutos = random.randint(5, 15)

        print(f"\nCICLO #{ciclo} CONCLUIDO!")
        print(f"O bot entrara em repouso por {delay_minutos} minutos...")

        try:
            for minuto in range(delay_minutos, 0, -1):
                print(f"ZzZz... Faltam {minuto} minuto(s) para o proximo ciclo.", flush=True)
                time.sleep(60)
        except KeyboardInterrupt:
            print("\nBot parado manualmente pelo usuario.", flush=True)
            break

        ciclo += 1


if __name__ == "__main__":
    try:
        run_continuous()
    except KeyboardInterrupt:
        print("\n\nBot parado manualmente pelo usuario.")
