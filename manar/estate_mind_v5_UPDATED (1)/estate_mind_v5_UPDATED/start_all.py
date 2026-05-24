"""
start_all.py — Lance les deux serveurs Estate Mind en parallèle.
  Port 8000 → Chat IA       (main.py)
  Port 8001 → Analytics XAI (analytics.py)
"""
import subprocess
import sys
import os

def main():
    print("🚀 Démarrage Estate Mind — 2 serveurs")
    print("   Port 8000 → Chat IA       : http://localhost:8000")
    print("   Port 8001 → Analytics XAI : http://localhost:8001")
    print("   Ctrl+C pour arrêter les deux\n")

    chat_proc = subprocess.Popen([
        sys.executable, "-m", "uvicorn",
        "main:app",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--reload",
    ], env={**os.environ, "PYTHONUNBUFFERED": "1"})

    analytics_proc = subprocess.Popen([
        sys.executable, "-m", "uvicorn",
        "analytics:app",
        "--host", "0.0.0.0",
        "--port", "8001",
        "--reload",
    ], env={**os.environ, "PYTHONUNBUFFERED": "1"})

    try:
        chat_proc.wait()
        analytics_proc.wait()
    except KeyboardInterrupt:
        print("\n⛔ Arrêt des serveurs...")
        chat_proc.terminate()
        analytics_proc.terminate()

if __name__ == "__main__":
    main()