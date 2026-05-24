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


def _send_email_alert(to: str, alert: dict) -> None:
    """Envoi réel d'email via SMTP pour une alerte de conformité."""
    import smtplib, ssl
    from email.mime.text      import MIMEText
    from email.mime.multipart import MIMEMultipart
    import config as cfg

    risk    = alert.get("risk_score", 0)
    sev     = "CRITIQUE" if risk >= 80 else "ÉLEVÉ" if risk >= 70 else "MOYEN"
    rule    = alert.get("rule", {})
    action  = (rule.get("action", "") if isinstance(rule, dict) else str(rule))
    actor   = (rule.get("actor",  "") if isinstance(rule, dict) else "")
    article = (rule.get("article","") if isinstance(rule, dict) else "")

    subject = f"EstateMind — Alerte juridique {sev} ({risk}/100)"
    body = (
        f"Alerte de conformite juridique — EstateMind\n"
        f"{'='*50}\n\n"
        f"Score de risque : {risk}/100  [{sev}]\n"
        f"Type            : {alert.get('type','')}\n"
        f"Message         : {alert.get('message','')}\n\n"
        f"Acteur          : {actor}\n"
        f"Action interdite: {action}\n"
        f"Article CDR/CATU: {article}\n\n"
        f"{'='*50}\n"
        f"EstateMind — Plateforme juridique intelligente\n"
        f"CDR Loi n65-5 + Code Urbanisme 2011\n"
    )

    try:
        msg = MIMEMultipart()
        msg["From"]    = cfg.FROM_EMAIL
        msg["To"]      = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        ctx = ssl.create_default_context()
        with smtplib.SMTP(cfg.SMTP_HOST, cfg.SMTP_PORT) as s:
            s.starttls(context=ctx)
            s.login(cfg.SMTP_USER, cfg.SMTP_PASS)
            s.sendmail(cfg.FROM_EMAIL, to, msg.as_string())
        log.info(f"Email alerte envoye a {to} (risk={risk}/100)")
    except Exception as e:
        log.warning(f"Email alerte echec ({to}) : {e}")


def send_alert_notification(alert: dict, config: dict) -> bool:
    """
    Envoie une alerte selon la configuration utilisateur (log + email SMTP).
    """
    alert_type = alert.get("type", "")
    risk_score = alert.get("risk_score", 0)

    # Vérifier si ce type d'alerte est activé
    if alert_type == "regulatory_change":
        source = alert.get("source", "")
        if "CDR"  in source and not config.get("cdr_changes"):
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

    # Log
    log.warning(
        f"ALERTE [{alert_type.upper()}] risk={risk_score}/100 "
        f"-> {config.get('email','console')} | {alert.get('message','')}"
    )

    # Envoi email réel
    email = config.get("email", "").strip()
    if email and "@" in email:
        _send_email_alert(email, alert)

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