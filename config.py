"""
config.py
─────────────────────────────────────────────────────────────────
Configuration centrale BO5 — Code des Droits Réels tunisien
Loi n°65-5 du 12 février 1965 (éd. 2024)
"""

from pathlib import Path

# ─── Chemins ──────────────────────────────────────────────────────────────────
ROOT      = Path(__file__).parent
DATA_DIR  = ROOT / "data"
NEO4J_DIR = ROOT / "neo4j_export"
LOG_DIR   = ROOT / "logs"

for _d in [DATA_DIR, NEO4J_DIR, LOG_DIR]:
    _d.mkdir(exist_ok=True)

# ─── Fichiers ─────────────────────────────────────────────────────────────────
PDF_INPUT     = ROOT / "pdf_francais.pdf"
TXT_CLEAN     = DATA_DIR / "code_clean.txt"
ARTICLES_JSON = DATA_DIR / "articles.json"
RULES_RAW     = DATA_DIR / "rules_raw.json"
RULES_CLEAN   = DATA_DIR / "rules_clean.json"

# ─── Source juridique ─────────────────────────────────────────────────────────
SOURCE_NAME    = "Code des Droits Réels tunisien"
SOURCE_VERSION = "2024"
SOURCE_LAW     = "Loi n°65-5 du 12 février 1965"

# ─── LLM Ollama ───────────────────────────────────────────────────────────────
OLLAMA_URL  = "http://localhost:11434/api/generate"
LLM_MODEL   = "mistral"
LLM_TEMP    = 0.3
LLM_RETRIES = 3
LLM_SLEEP   = 1.0

# ─── Domaine autorisé (Code des Droits Réels) ─────────────────────────────────
DOMAIN_KW = {
    # Propriété
    "propriété", "propriétaire", "propriete", "proprietaire",
    "immeuble", "foncier", "terrain", "fonds",
    "bien immobilier", "biens immobiliers",
    "droit réel", "droit reel",
    # Servitudes / droits réels démembrés
    "servitude", "hypothèque", "hypotheque",
    "usufruit", "usufruitier",
    "emphytéose", "emphyteose", "emphytéote",
    "superficie", "enzel", "kirdar",
    "copropriété", "copropriete", "coindivisaire",
    "parties communes", "mitoyen", "mitoyenneté", "mitoyennete",
    # Possession / prescription
    "possession", "possesseur", "prescription", "accession",
    # Immatriculation
    "immatriculation", "titre foncier", "inscription", "conservation",
    "registre foncier",
    # Bail / location
    "bail", "locataire", "bailleur", "preneur",
    "louer", "sous-louer", "sous louer", "location",
    # Sûretés réelles
    "créancier", "creancier",
    "débiteur", "debiteur",
    "sûreté", "gage", "nantissement", "privilège",
    # Parties / acteurs
    "acquéreur", "acquereur",
    "succession", "héritier", "heritier", "donation",
    "cession", "cessionnaire",
    "voisin", "nu-propriétaire",
    # Construction
    "construction", "construire", "construire sans",
    "bâtiment", "batiment", "travaux", "lotissement",
    "permis de construire", "autorisation de construire",
    "rénovation", "renovation", "extension", "mur", "clôture",
    "meuble", "sol",
    # Démolition / destruction
    "démolir", "demolir",
    "démolition", "demolition",
    "détruire", "detruire",
    "destruction",
    # Vente / transfert
    "vendre", "vente",
    "acheter", "achat",
    "acquérir", "acquerir",
    "aliéner", "aliener",
    "céder", "ceder",
    "saisir", "saisie",
    "expropriation", "exproprier",
    "mutation", "transfert",
    "acte authentique", "notaire",
    # Actions juridiques CDR
    "interdire", "interdit",
    "revendiquer", "restituer",
    "prêter", "preter",
    "réparer", "reparation",
    "partager", "partage",
    "hériter", "heriter",
    "résilier", "resilier",
    "renouveler",
    # Autres
    "morcellement", "division parcellaire",
    "réparation", "rehabilitation",
    "monument historique",
    "fruits", "jouissance",
    "mise en valeur", "développement agricole",
}

# ─── Mots hors domaine (à rejeter) ────────────────────────────────────────────
NOISE_KW = {
    "permis de conduire", "code de la route", "tabac", "cigarette",
    "code du travail", "salariés", "licenciement",
    "pharmacien", "médicament", "stéroïdes", "stupéfiants",
    "carte d'identité nationale", "passeport", "visa", "droit d'asile",
    "avocat", "barreau", "code de l'avocat",
    "biens importés", "douane", "cesu",
    "centre commercial", "vente au détail",
    "voiture électrique", "porte-plaque", "circuler en voiture",
    "chasse", "autorisation de chasse", "alcool", "bar",
}

# ─── Signaux d'hallucination LLM ──────────────────────────────────────────────
HALLUCINATION_SIGNALS = {
    "code du travail", "permis de conduire", "csg", "crds",
    "impôt sur le revenu", "sécurité sociale", "assurance maladie",
    "données personnelles", "rgpd", "syndicat",
}

# ─── Mapping acteurs → catégories standard ────────────────────────────────────
ACTOR_MAP: dict[str, str] = {
    # Propriétaire
    "le propriétaire":          "proprietaire",
    "propriétaire":             "proprietaire",
    "les propriétaires":        "proprietaire",
    "nu-propriétaire":          "proprietaire",
    "le nu-propriétaire":       "proprietaire",
    # Possesseur
    "le possesseur":            "possesseur",
    "possesseur":               "possesseur",
    "possesseur de bonne foi":  "possesseur",
    "possesseur de mauvaise foi": "possesseur",
    # Usufruitier
    "l'usufruitier":            "usufruitier",
    "usufruitier":              "usufruitier",
    # Bailleur
    "le bailleur":              "bailleur",
    "bailleur":                 "bailleur",
    # Locataire
    "le locataire":             "locataire",
    "locataire":                "locataire",
    # Preneur
    "le preneur":               "preneur",
    "preneur":                  "preneur",
    # Emphytéote
    "emphytéote":               "emphytéote",
    "l'emphytéote":             "emphytéote",
    # Copropriétaire
    "le copropriétaire":        "copropriétaire",
    "copropriétaire":           "copropriétaire",
    "les copropriétaires":      "copropriétaire",
    # Coindivisaire
    "le coindivisaire":         "coindivisaire",
    "coindivisaire":            "coindivisaire",
    # Créancier
    "le créancier":             "créancier",
    "créancier":                "créancier",
    "créancier hypothécaire":   "créancier",
    "créancier gagiste":        "créancier",
    "établissements de crédits": "créancier",
    "établissement de crédit":  "créancier",
    # Débiteur
    "le débiteur":              "débiteur",
    "débiteur":                 "débiteur",
    # Acquéreur
    "l'acquéreur":              "acquéreur",
    "acquéreur":                "acquéreur",
    "l'acheteur":               "acquéreur",
    "acheteur":                 "acquéreur",
    "adjudicataire":            "acquéreur",
    # Vendeur
    "le vendeur":               "vendeur",
    "vendeur":                  "vendeur",
    # Héritier
    "l'héritier":               "héritier",
    "héritier":                 "héritier",
    "les héritiers":            "héritier",
    "curateur de la succession": "héritier",
    # Voisin
    "le voisin":                "voisin",
    "voisin":                   "voisin",
    # État
    "l'état":                   "etat",
    "état":                     "etat",
    "l'état tunisien":          "etat",
    "ministre chargé des domaines de l'etat": "etat",
    "collectivité publique expropriante": "etat",
    # Autorité locale
    "la collectivité":          "autorite_locale",
    "collectivité locale":      "autorite_locale",
    "commune":                  "autorite_locale",
    "commission":               "autorite_locale",
    "gouverneur":               "autorite_locale",
    # Tribunal
    "le tribunal":              "tribunal",
    "tribunal":                 "tribunal",
    # Notaire
    "le notaire":               "notaire",
    "notaire":                  "notaire",
    # Conservateur
    "le conservateur":          "conservateur",
    "conservateur foncier":     "conservateur",
    # Autres
    "toute personne":           "personne",
    "le tiers":                 "tiers",
    "les tiers":                "tiers",
    "tiers":                    "tiers",
    "les particuliers":         "particulier",
    "particulier":              "particulier",
    "les citoyens":             "citoyen",
    "citoyen":                  "citoyen",
    "requérant":                "personne",
    "partie qui a constitué le gage": "débiteur",
    # Acteurs non-standard normalisés
    "le titulaire d'un permis de construire":   "proprietaire",
    "titulaire d'un permis de construire":       "proprietaire",
    "le bénéficiaire d'un permis de construire": "proprietaire",
    "bénéficiaire d'un permis de construire":    "proprietaire",
    "le titulaire de la propriété immeuble":     "proprietaire",
    "titulaire de la propriété immeuble":        "proprietaire",
    "les émetteurs de biens immobiliers":        "vendeur",
    "émetteurs de biens immobiliers":            "vendeur",
    "les entreprises":                           "particulier",
    "une entreprise":                            "particulier",
    "les entreprises commerciales":              "particulier",
    "partie civile":                             "personne",
}

KNOWN_ACTORS = set(ACTOR_MAP.values())

# ─── Risk Scoring ─────────────────────────────────────────────────────────────
STATUS_BASE: dict[str, int] = {
    "interdit":   60,
    "obligation": 40,
    "permis":     10,
}

ACTOR_WEIGHT: dict[str, float] = {
    "créancier":       1.4,
    "débiteur":        1.3,
    "proprietaire":    1.2,
    "copropriétaire":  1.2,
    "coindivisaire":   1.1,
    "acquéreur":       1.1,
    "vendeur":         1.1,
    "locataire":       1.1,
    "bailleur":        1.1,
    "preneur":         1.1,
    "emphytéote":      1.1,
    "héritier":        1.0,
    "possesseur":      1.0,
    "usufruitier":     1.0,
    "voisin":          1.0,
    "conservateur":    0.9,
    "notaire":         0.9,
    "personne":        0.9,
    "particulier":     0.9,
    "etat":            0.8,
    "autorite_locale": 0.8,
    "tribunal":        0.7,
}

HIGH_RISK_VERBS = {
    "hypothéquer", "saisir", "exproprier", "démolir", "détruire",
    "résilier", "annuler", "inscrire hypothèque", "forclore",
    "sous-louer", "prêter",
}

# ─── API ──────────────────────────────────────────────────────────────────────
API_HOST = "0.0.0.0"
API_PORT = 8000

# ─── Seuils ───────────────────────────────────────────────────────────────────
COMPLIANCE_THRESHOLD = 0.45   # seuil matching DS04
ALERT_THRESHOLD      = 70     # risk ≥ 70 → alerte

# ─── Webhook (optionnel) ──────────────────────────────────────────────────────
WEBHOOK_URL = ""

# ─── Email SMTP (pour envoi rapports PDF) ─────────────────────────────────────
# Configurer avec votre compte email pour activer l'envoi
# Pour Gmail : activer "Mots de passe d'application" dans les paramètres Google
SMTP_HOST  = "smtp.gmail.com"   # Gmail
SMTP_PORT  = 587                 # TLS
SMTP_USER  = "yosserbenmahmoud45@gmail.com"                  # votre.email@gmail.com
SMTP_PASS  = "lxyiguzdbtnmimmm"                  # mot de passe d'application Gmail
FROM_EMAIL = SMTP_USER           # même que SMTP_USER