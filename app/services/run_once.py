"""
Execução única do pipeline — hunter opcional + aplicador.
Uso: python -m app.services.run_once [--hunt-leads] [--teste]
"""

import argparse
import subprocess
import sys

from app.services.pipeline import build_main_command, run_hunter_phase


def main():
    parser = argparse.ArgumentParser(description="Pipeline unificado do Bot Busca Vagas")
    parser.add_argument("--hunt-leads", action="store_true", help="Buscar novos leads antes de candidatar")
    parser.add_argument("--teste", action="store_true", help="Modo teste (sem envio de email)")
    args = parser.parse_args()

    if args.hunt_leads and not args.teste:
        print(">>> Etapa 1/2: busca de leads na web")
        code = run_hunter_phase()
        if code != 0:
            print(f"[!] Hunter encerrou com codigo {code} (continuando aplicador)")

    print(">>> Etapa 2/2: candidaturas")
    mode = "teste" if args.teste else "full"
    cmd = build_main_command(mode)
    sys.exit(subprocess.run(cmd).returncode)


if __name__ == "__main__":
    main()
