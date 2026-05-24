"""
Estate Mind — Notifier
══════════════════════
Alertes email + webhook pour les événements BO1/BO2.

Configuration .env :
  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS
  NOTIFY_FROM, WEBHOOK_URL (optionnel Slack/Discord)
"""
from __future__ import annotations

import json, os, smtplib
from dataclasses import dataclass, field, asdict
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

import requests
from loguru import logger

SMTP_HOST   = os.getenv("SMTP_HOST",   "smtp.gmail.com")
SMTP_PORT   = int(os.getenv("SMTP_PORT","587"))
SMTP_USER   = os.getenv("SMTP_USER",   "")
SMTP_PASS   = os.getenv("SMTP_PASS",   "")
NOTIFY_FROM = os.getenv("NOTIFY_FROM", "noreply@estate-mind.tn")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
SUBS_PATH   = Path("data/state/subscriptions.json")
APP_URL     = os.getenv("APP_URL", "http://localhost:3000")


@dataclass
class AlertSubscription:
    sub_id:            str
    email:             str
    name:              str
    created_at:        str   = field(default_factory=lambda: datetime.utcnow().isoformat())
    active:            bool  = True
    watch_zones:       list  = field(default_factory=list)
    price_threshold:   float = 0.08
    alert_on_emerging: bool  = True
    alert_on_declining:bool  = False
    watch_cities:      list  = field(default_factory=list)
    budget_max:        Optional[float] = None
    surface_min:       Optional[float] = None
    property_types:    list  = field(default_factory=list)
    trust_min:         float = 0.70
    webhook_url:       Optional[str]   = None
    send_email:        bool  = True


class SubscriptionStore:
    def __init__(self):
        self._subs: list[AlertSubscription] = self._load()

    def _load(self):
        if not SUBS_PATH.exists(): return []
        try:
            return [AlertSubscription(**d) for d in json.loads(SUBS_PATH.read_text("utf-8"))]
        except Exception: return []

    def _save(self):
        SUBS_PATH.parent.mkdir(parents=True, exist_ok=True)
        SUBS_PATH.write_text(json.dumps([asdict(s) for s in self._subs],
                                         ensure_ascii=False, indent=2), "utf-8")

    def add(self, sub: AlertSubscription):
        self._subs = [s for s in self._subs if s.email != sub.email]
        self._subs.append(sub); self._save()

    def remove(self, email: str) -> bool:
        n = len(self._subs)
        self._subs = [s for s in self._subs if s.email != email]
        self._save(); return len(self._subs) < n

    def get_all_active(self): return [s for s in self._subs if s.active]
    def get_by_email(self, email): return next((s for s in self._subs if s.email == email), None)
    def all_as_dicts(self): return [asdict(s) for s in self._subs]


def _html_wrap(title: str, body: str, cta_text: str = "", cta_url: str = "") -> str:
    cta = f'<div style="text-align:center;margin-top:24px"><a href="{cta_url}" style="background:#C8A96E;color:#09090B;padding:10px 22px;border-radius:6px;text-decoration:none;font-weight:600;font-size:13px">{cta_text}</a></div>' if cta_text else ""
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="font-family:'Segoe UI',sans-serif;background:#0d0d0f;color:#F2F0EC;margin:0;padding:32px 16px">
<div style="max-width:540px;margin:0 auto">
  <div style="margin-bottom:20px"><span style="font-size:18px;font-weight:700;color:#C8A96E">🏛 Estate Mind</span></div>
  <div style="background:#18181C;border:1px solid rgba(255,255,255,.08);border-radius:12px;padding:28px">
    <h1 style="font-size:17px;margin:0 0 14px;color:#F2F0EC">{title}</h1>
    <div style="font-size:14px;line-height:1.7;color:#A8A6A0">{body}</div>
    {cta}
  </div>
  <p style="font-size:10px;color:#6B6966;text-align:center;margin-top:16px">Estate Mind PropTech</p>
</div></body></html>"""


class Notifier:
    def __init__(self):
        self.store = SubscriptionStore()
        self._email_ok   = bool(SMTP_USER and SMTP_PASS)
        self._webhook_ok = bool(WEBHOOK_URL)

    def send_email(self, to: str, subject: str, html: str, text: str) -> bool:
        if not self._email_ok:
            logger.info(f"[Notifier] Console — {subject}")
            return True
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject; msg["From"] = NOTIFY_FROM; msg["To"] = to
            msg.attach(MIMEText(text, "plain", "utf-8"))
            msg.attach(MIMEText(html,  "html",  "utf-8"))
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
                s.ehlo(); s.starttls(); s.login(SMTP_USER, SMTP_PASS)
                s.sendmail(NOTIFY_FROM, to, msg.as_string())
            logger.info(f"[Notifier] Email → {to}")
            return True
        except Exception as e:
            logger.warning(f"[Notifier] Email échoué : {e}")
            return False

    def send_webhook(self, subject: str, text: str, url: str = "") -> bool:
        target = url or WEBHOOK_URL
        if not target: return False
        try:
            requests.post(target, json={"text": subject, "attachments": [{"text": text[:400], "color":"#C8A96E"}]}, timeout=8).raise_for_status()
            return True
        except Exception as e:
            logger.warning(f"[Notifier] Webhook échoué : {e}")
            return False

    def notify_territorial_alert(self, alert: dict, sub: AlertSubscription) -> bool:
        zone     = alert.get("zone","")
        msg      = alert.get("message","")
        reco     = alert.get("recommendation","")
        pg       = alert.get("price_growth")
        price_r  = alert.get("median_price_recent")
        horizon  = alert.get("action_horizon_days", 60)
        severity = alert.get("severity","medium")
        sev_col  = {"critical":"#E05C5C","high":"#E8A84C","medium":"#6B9FE8"}.get(severity,"#6B9FE8")
        icon     = {"emerging":"🚀","price_surge":"📈","volume_surge":"📊","declining":"📉"}.get(alert.get("alert_type",""),"📌")
        pg_str   = f"+{pg*100:.1f}%" if pg and pg > 0 else (f"{pg*100:.1f}%" if pg else "—")
        price_str= f"{price_r:,.0f} TND" if price_r else "—"
        body     = f"""<div style="background:rgba(255,255,255,.04);border-left:3px solid {sev_col};padding:12px 14px;margin-bottom:14px;border-radius:0 6px 6px 0">
          <strong style="color:#F2F0EC">{icon} {zone}</strong>
          <span style="font-size:11px;background:{sev_col}22;color:{sev_col};padding:2px 8px;border-radius:999px;margin-left:8px">{severity.upper()}</span>
        </div>
        <p>{msg}</p>
        <p style="font-size:12px"><b style="color:#C8A96E">Prix médian :</b> {price_str} &nbsp;·&nbsp; <b style="color:#52C896">Variation :</b> {pg_str}</p>
        {"<p><b style='color:#C8A96E'>Recommandation :</b><br>" + reco + "</p>" if reco else ""}
        <p style="font-size:11px;color:#6B6966">⏰ Horizon d'action : {horizon} jours</p>"""
        subject = f"[Estate Mind] {icon} Alerte {severity} — {zone}"
        text    = f"{subject}\n{msg}\nRecommandation : {reco}\nHorizon : {horizon}j"
        html    = _html_wrap(f"Alerte territoriale — {zone}", body, "Voir les alertes", f"{APP_URL}/territoire")
        ok = self.send_email(sub.email, subject, html, text)
        if sub.webhook_url: self.send_webhook(subject, text, sub.webhook_url)
        return ok

    def notify_new_listing(self, listing: dict, sub: AlertSubscription) -> bool:
        title   = listing.get("title","Nouvelle annonce")
        city    = listing.get("city","—")
        price   = listing.get("price",0) or 0
        surface = listing.get("surface",0) or 0
        trust   = listing.get("trust_score",0) or 0
        ptype   = listing.get("property_type","autre").replace("_"," ")
        url     = listing.get("url","")
        tc      = "#52C896" if trust>=.75 else "#E8A84C" if trust>=.5 else "#E05C5C"
        body    = f"""<p>Une nouvelle annonce correspond à vos critères :</p>
        <div style="background:rgba(255,255,255,.04);border-radius:8px;padding:16px;margin:12px 0">
          <div style="font-size:15px;font-weight:600;color:#F2F0EC;margin-bottom:6px">{title}</div>
          <div style="font-size:12px;color:#6B6966">📍 {city} · {ptype}</div>
          <div style="margin-top:12px;font-size:22px;font-weight:700;color:#C8A96E">{price:,.0f} TND</div>
          {"<div style='font-size:13px;color:#A8A6A0'>" + str(surface) + " m²</div>" if surface else ""}
          <div style="font-size:12px;color:{tc};margin-top:6px">Trust score : {trust:.2f}</div>
        </div>"""
        subject = f"[Estate Mind] 🏠 Nouvelle annonce à {city} — {price:,.0f} TND"
        text    = f"{subject}\n{title}\n{city} · {ptype}\nPrix : {price:,.0f} TND · Trust : {trust:.2f}\n{url}"
        html    = _html_wrap("Nouvelle annonce", body, "Voir l'annonce", url or APP_URL)
        return self.send_email(sub.email, subject, html, text)

    def dispatch_territorial_alerts(self, alerts: list[dict]) -> dict:
        subs = self.store.get_all_active()
        sent = skipped = 0
        for alert in alerts:
            zone = alert.get("zone","")
            for sub in subs:
                if sub.watch_zones and zone not in sub.watch_zones: skipped+=1; continue
                if alert.get("alert_type")=="declining" and not sub.alert_on_declining: skipped+=1; continue
                self.notify_territorial_alert(alert, sub); sent += 1
        logger.info(f"[Notifier] {sent} alertes envoyées, {skipped} ignorées")
        return {"sent": sent, "skipped": skipped}

    def dispatch_new_listing_alerts(self, listings: list[dict]) -> dict:
        subs = self.store.get_all_active()
        sent = 0
        for listing in listings:
            for sub in subs:
                if self._matches(listing, sub):
                    self.notify_new_listing(listing, sub); sent += 1
        return {"sent": sent}

    def _matches(self, listing: dict, sub: AlertSubscription) -> bool:
        city  = str(listing.get("city","")).lower()
        price = listing.get("price",0) or 0
        surf  = listing.get("surface",0) or 0
        ptype = listing.get("property_type","")
        trust = listing.get("trust_score",0) or 0
        if sub.watch_cities and not any(c.lower() in city for c in sub.watch_cities): return False
        if sub.budget_max   and price > sub.budget_max:  return False
        if sub.surface_min  and surf  < sub.surface_min: return False
        if sub.property_types and ptype not in sub.property_types: return False
        if trust < sub.trust_min: return False
        return True
