"""
start_all.py — Estate Mind BO6 — Démarrage des services.
=========================================================
Lance BO6 (orchestrateur) + Dashboard et ouvre le navigateur.

ARCHITECTURE RÉELLE :
  BO1 à BO5 sont des microservices RÉELS sur leurs machines.
  Configurer leurs IPs dans .env si multi-PC.
  Base de données : Supabase (schéma bo6_tracking).

Usage :
  python start_all.py            # Lance BO6 + Dashboard
  python start_all.py --no-browser  # Sans ouvrir le navigateur
"""
import subprocess
import sys
import time
import os
import webbrowser
import urllib.request
import argparse

GRN = "\033[92m"
RED = "\033[91m"
YEL = "\033[93m"
ORG = "\033[38;5;208m"
RST = "\033[0m"
BOLD = "\033[1m"

BANNER = f"""
{ORG}{BOLD}
╔══════════════════════════════════════════════════════╗
║          ESTATE MIND — BO6 Orchestrateur             ║
║          Supabase · Agents Réels BO1-BO5             ║
╚══════════════════════════════════════════════════════╝
{RST}"""

SERVICES = [
    (
        "BO6  (Orchestrateur — Port 8000)",
        [sys.executable, "-m", "uvicorn", "main:app",
         "--port", "8000", "--host", "0.0.0.0", "--reload"],
        "http://localhost:8000/api/v1/health",
    ),
    (
        "Dashboard (Métriques — Port 8050)",
        [sys.executable, "app/dashboard/metrics_dashboard.py"],
        "http://localhost:8050",
    ),
]


def wait_for(url, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(1)
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    print(BANNER)

    if not os.path.exists(".env"):
        print(f"{RED}  ✗ Fichier .env manquant !{RST}")
        sys.exit(1)
    os.makedirs("reports", exist_ok=True)

    procs = []
    env = os.environ.copy()
    env["PYTHONPATH"] = os.getcwd()

    print(f"\n{BOLD}  Démarrage des services...{RST}\n")
    for name, cmd, health_url in SERVICES:
        print(f"  {YEL}▶{RST}  {name}")
        p = subprocess.Popen(cmd, cwd=os.getcwd(), env=env,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        procs.append((name, p, health_url))
        time.sleep(2)

    print(f"\n  Vérification des services...")
    time.sleep(5)

    print(f"\n  {'─'*50}")
    for name, p, url in procs:
        ok = wait_for(url, timeout=25)
        icon = f"{GRN}✓ OK{RST}" if ok else f"{RED}✗ KO{RST}"
        print(f"  {name:<38} {icon}")
    print(f"  {'─'*50}")

    # Vérification agents BO1-BO5
    try:
        from dotenv import dotenv_values
        env_vals = dotenv_values(".env")
        agents = {
            "BO1": env_vals.get("AGENT_BO1_URL", "http://localhost:8001"),
            "BO2": env_vals.get("AGENT_BO2_URL", "http://localhost:8002"),
            "BO3": env_vals.get("AGENT_BO3_URL", "http://localhost:8003"),
            "BO4": env_vals.get("AGENT_BO4_URL", "http://localhost:8004"),
            "BO5": env_vals.get("AGENT_BO5_URL", "http://localhost:8005"),
        }
        print(f"\n  Agents BO1-BO5 (microservices réels) :")
        for name, base_url in agents.items():
            try:
                with urllib.request.urlopen(f"{base_url}/health", timeout=3) as r:
                    status = f"{GRN}✓ Connecté{RST}" if r.status == 200 else f"{YEL}⚠ Dégradé{RST}"
            except Exception:
                status = f"{RED}✗ Non joignable{RST}"
            print(f"    {name}  {base_url:<35} {status}")
        print(f"  {YEL}ℹ  Configurer les IPs dans .env si agents sur d'autres machines{RST}")
    except Exception:
        pass

    print(f"""
{ORG}{BOLD}  ╔══════════════════════════════════════════════════════╗
  ║  API REST  :  http://localhost:8000                 ║
  ║  Swagger   :  http://localhost:8000/docs            ║
  ║  Dashboard :  http://localhost:8050                 ║
  ║  Frontend  :  http://localhost:8000/frontend/       ║
  ╚══════════════════════════════════════════════════════╝{RST}
  {YEL}Ctrl+C pour arrêter{RST}
""")

    if not args.no_browser:
        time.sleep(2)
        webbrowser.open("http://localhost:8000/docs")
        time.sleep(1)
        webbrowser.open("http://localhost:8000/frontend/index.html")

    try:
        for _, p, _ in procs:
            p.wait()
    except KeyboardInterrupt:
        print(f"\n  Arrêt des services...")
        for name, p, _ in procs:
            p.terminate()
            print(f"  {RED}✗{RST} {name} arrêté")


if __name__ == "__main__":
    main()
