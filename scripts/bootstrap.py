#!/usr/bin/env python3
import os
import sys
import subprocess

ROOT = os.path.dirname(os.path.dirname(__file__))
VENV = os.path.join(ROOT, 'venv')
PY = os.path.join(VENV, 'Scripts', 'python.exe') if os.name == 'nt' else os.path.join(VENV, 'bin', 'python')
PIP = os.path.join(VENV, 'Scripts', 'pip.exe') if os.name == 'nt' else os.path.join(VENV, 'bin', 'pip')

def run(cmd: str):
    print(f"$ {cmd}")
    subprocess.run(cmd, shell=True, check=False)

def ensure_venv():
    if not os.path.isdir(VENV):
        print("Creating virtual environment...")
        subprocess.run([sys.executable, '-m', 'venv', VENV], check=True)

def install_requirements():
    ensure_venv()
    req = os.path.join(ROOT, 'bot_curriculo', 'requirements.txt')
    if os.path.exists(req):
        run(f"{PIP} install -r {req}")
    else:
        print("Requirements file not found, skipping dependencies install.")

def install_playwright():
    ensure_venv()
    run(f"{PY} -m pip install playwright")
    run(f"{PY} -m playwright install")

def main():
    install_requirements()
    install_playwright()
    print("Bootstrap complete.")

if __name__ == '__main__':
    main()
