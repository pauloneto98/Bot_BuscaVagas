import time
import subprocess
import random
import sys
import os
import io
from datetime import datetime

# Fix encoding no Windows para suportar emojis/UTF-8
if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def run_continuous():
    print("="*60)
    print("🤖 BOT BUSCA VAGAS - MODO CONTÍNUO (24/7) ATIVADO")
    print("="*60)
    print("O bot rodará em ciclos contínuos, intercalando:")
    print("1. Busca de novas empresas (Email Hunter)")
    print("2. Aplicação em vagas (Web e E-mail)")
    print("3. Descanso (para simular comportamento humano e evitar bloqueios)")
    print("Pressione CTRL+C para parar a qualquer momento.\n")
    
    ciclo = 1
    while True:
        print(f"\n{'='*60}")
        print(f"🔄 INICIANDO CICLO #{ciclo} - {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        print(f"{'='*60}\n")
        
        # 1. Rodar Hunter
        print(">>> ETAPA 1: CAÇADOR DE LEADS (Buscando novas empresas na web)")
        subprocess.run([sys.executable, os.path.join(BASE_DIR, "tools", "email_hunter.py"), "--max-queries", "8"], cwd=BASE_DIR)
        
        time.sleep(10)
        
        # 2. Rodar Aplicador Principal
        print("\n>>> ETAPA 2: APLICADOR (Candidatando-se às vagas encontradas e no BD)")
        subprocess.run([sys.executable, os.path.join(BASE_DIR, "main.py")], cwd=BASE_DIR)
        
        # 3. Dormir para evitar Rate Limits do Google e Bloqueios de Sites
        # Dorme entre 5 a 15 minutos aleatoriamente
        delay_minutos = random.randint(5, 15)
        segundos_totais = delay_minutos * 60
        
        print(f"\n⏳ CICLO #{ciclo} CONCLUÍDO!")
        print(f"O bot entrará em repouso por {delay_minutos} minutos para simular comportamento humano natural...")
        
        try:
            for minuto in range(delay_minutos, 0, -1):
                print(f"ZzZz... Faltam {minuto} minuto(s) para o próximo ciclo.", flush=True)
                time.sleep(60)
        except KeyboardInterrupt:
            print("\n🛑 Bot parado manualmente pelo usuário.", flush=True)
            break
            
        ciclo += 1

if __name__ == "__main__":
    try:
        run_continuous()
    except KeyboardInterrupt:
        print("\n\n🛑 Bot parado manualmente pelo usuário.")
