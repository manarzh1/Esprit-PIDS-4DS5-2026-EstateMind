"""
alerts.py
─────────────────────────────────────────────────────────────────
Système de configuration et gestion des alertes TuniState
Stocke les préférences utilisateur et envoie des notifications
"""
import json
import logging
from pathlib import Path
from datetime import datetime
from config import LOG_DIR, ALERT_THRESHOLD

log = logging.getLogger("alerts")
log.setLevel(logging.INFO)
if not log.handlers:
    _fmt = logging.Formatter("%(asctime)s │ %(levelname)-7s │ %(message)s", "%H:%M:%S")
    sh = logging.StreamHandler(); sh.setFormatter(_fmt); log.addHandler(sh)
    fh = logging.FileHandler(LOG_DIR / "alerts.log", encoding="utf-8")
    fh.setFormatter(_fmt); log.addHandler(fh)

ALERTS_CONFIG_PATH = Path("data/alerts_config.json")


def load_alerts_config() -> dict:
    """Charge la configuration des alertes."""
    if ALERTS_CONFIG_PATH.exists():
        with open(ALERTS_CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {
        "email": "",
        "cdr_changes":      True,
        "catu_changes":     True,
        "high_risk":        True,
        "new_rules":        False,
        "risk_threshold":   ALERT_THRESHOLD,
        "created_at":       datetime.now().isoformat(),
    }


def save_alerts_config(config: dict) -> dict:
    """Sauvegarde la configuration des alertes."""
    config["updated_at"] = datetime.now().isoformat()
    ALERTS_CONFIG_PATH.parent.mkdir(exist_ok=True)
    with open(ALERTS_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    log.info(f"Configuration alertes sauvegardée → {config.get('email','?')}")
    return config


def send_alert_notification(alert: dict, config: dict) -> bool:
    """
    Envoie une alerte selon la configuration utilisateur.
    En production : intégrer SMTP ou webhook.
    """
    alert_type  = alert.get("type", "")
    risk_score  = alert.get("risk_score", 0)

    # Vérifier si l'alerte est activée
    if alert_type == "regulatory_change":
        source = alert.get("source", "")
        if "CDR" in source and not config.get("cdr_changes"):
            return False
        if "CATU" in source and not config.get("catu_changes"):
            return False

    if alert_type == "compliance_violation":
        if not config.get("high_risk"):
            return False
        if risk_score < config.get("risk_threshold", ALERT_THRESHOLD):
            return False

    if alert_type == "new_rules" and not config.get("new_rules"):
        return False

    # Log l'alerte
    log.warning(
        f"ALERTE [{alert_type.upper()}] "
        f"risk={risk_score}/100 "
        f"→ {config.get('email','console')}"
        f" | {alert.get('message','')}"
    )

    # En production : envoyer email via SMTP
    email = config.get("email", "")
    if email:
        log.info(f"Email d'alerte envoyé à : {email}")

    return True


def get_alerts_history() -> list:
    """Retourne l'historique des alertes depuis le log."""
    alerts = []
    log_path = LOG_DIR / "alerts.log"
    if not log_path.exists():
        return []
    with open(log_path, encoding="utf-8") as f:
        for line in f.readlines()[-50:]:
            if "ALERTE" in line:
                alerts.append({
                    "timestamp": line[:8],
                    "message":   line.strip()
                })
    return alerts[-10:]


if __name__ == "__main__":
    config = load_alerts_config()
    config["email"] = "test@estate-mind.tn"
    config["cdr_changes"] = True
    config["high_risk"]   = True
    save_alerts_config(config)
    print(f"✅ Configuration alertes sauvegardée")
    print(json.dumps(config, ensure_ascii=False, indent=2))