import runpy
import sys
import os

# Add the directory containing this script to sys.path to ensure correct imports
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

if __name__ == "__main__":
    print("🚀 Starting Bot Busca Vagas Scheduler service...")
    runpy.run_module("app.services.scheduler", run_name="__main__")
