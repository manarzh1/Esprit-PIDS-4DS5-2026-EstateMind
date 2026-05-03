"""
Extrait les règles du Code de l'Aménagement du Territoire
et les fusionne avec rules_clean.json existant.
"""
import json, sys, hashlib
sys.path.insert(0, '.')
from pipeline import extract_rules

print("Extraction des règles — Code Urbanisme...")

# Lire le texte urbanisme
with open('data/urbanisme_clean.txt', encoding='utf-8') as f:
    txt = f.read()

# Découper en articles
import re
articles = []
matches = list(re.finditer(r'Article\s+(\d+)', txt))
for i, m in enumerate(matches):
    start = m.start()
    end   = matches[i+1].start() if i+1 < len(matches) else start+2000
    art_text = txt[start:min(end, start+1500)].strip()
    if len(art_text) > 80:
        articles.append({
            'article_num': m.group(1),
            'text': art_text,
            'source': 'URBANISME'
        })

print(f"Articles trouvés : {len(articles)}")

# Sélectionner les articles pertinents (top 30)
keywords = ['construire', 'permis', 'autorisation', 'lotissement',
            'zone', 'constructible', 'démolir', 'morcellement',
            'alignement', 'voirie', 'infraction']

scored = []
for a in articles:
    txt_low = a['text'].lower()
    score = sum(txt_low.count(k) for k in keywords)
    if score > 0:
        scored.append((score, a))

scored.sort(key=lambda x: -x[0])
selected = [a for _, a in scored[:30]]
print(f"Articles sélectionnés : {len(selected)}")

# Extraire les règles avec Mistral
print("Extraction Mistral en cours...")
new_rules = []
for i, art in enumerate(selected):
    print(f"  [{i+1}/{len(selected)}] Art.{art['article_num']}...", end=' ')
    try:
        rules = extract_rules([art])
        for r in rules:
            r['source_code'] = 'URBANISME'
            r['law'] = "Code de l'Aménagement du Territoire — 2011"
        new_rules.extend(rules)
        print(f"{len(rules)} règles")
    except Exception as e:
        print(f"erreur: {e}")

print(f"\nNouvelles règles extraites : {len(new_rules)}")

# Fusionner avec rules_clean.json
with open('data/rules_clean.json', encoding='utf-8') as f:
    existing = json.load(f)

print(f"Règles existantes : {len(existing)}")

# Déduplication
def make_hash(r):
    key = f"{r.get('actor')}|{r.get('action')}|{r.get('target')}|{r.get('status')}"
    return hashlib.md5(key.encode()).hexdigest()

existing_hashes = {make_hash(r) for r in existing}
added = 0
for r in new_rules:
    h = make_hash(r)
    if h not in existing_hashes:
        existing.append(r)
        existing_hashes.add(h)
        added += 1

print(f"Règles ajoutées : {added}")
print(f"Total final : {len(existing)}")

with open('data/rules_clean.json', 'w', encoding='utf-8') as f:
    json.dump(existing, f, ensure_ascii=False, indent=2)

print("Sauvegardé dans data/rules_clean.json")
print("Prochaine étape : python main.py --step risk")