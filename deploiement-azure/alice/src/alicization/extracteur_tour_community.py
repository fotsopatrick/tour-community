#!/usr/bin/env python3
# Extrait les procédures de tour-community et les ajoute à la carte vivante
# (même logique que extracteur_tour.py mais avec le chemin exact)

import os, json, re
from pathlib import Path

CHEMIN_DEPOT = "/home/orel/Desktop/Alicization/tour-community/tour-community-main"
CHEMIN_CARTE = "/home/orel/carte-vivante/cartes.json"
ZONE_CONNAISSANCES = "connaissances"

def normaliser(texte):
    if not texte: return ""
    accents = {'é':'e','è':'e','ê':'e','ë':'e','à':'a','â':'a','ä':'a','ç':'c','ô':'o','ö':'o','î':'i','ï':'i','û':'u','ü':'u','ù':'u'}
    for o,f in accents.items(): texte = texte.replace(o,f)
    return texte.lower().strip()

def charger_carte():
    with open(CHEMIN_CARTE, 'r', encoding='utf-8') as f: return json.load(f)
def sauvegarder_carte(carte):
    with open(CHEMIN_CARTE, 'w', encoding='utf-8') as f: json.dump(carte, f, indent=2, ensure_ascii=False)

def existe_deja(carte, nom, mots_cles):
    nom_norm = normaliser(nom)
    mots_norm = {normaliser(m) for m in mots_cles}
    for zone in carte["zones"]:
        for noeud in zone.get("noeuds", []):
            if normaliser(noeud.get("nom","")) == nom_norm: return True
            existing = {normaliser(m) for m in noeud.get("mots_cles", [])}
            if len(mots_norm & existing) >= 3: return True
    return False

def ajouter_circuit(carte, nom, description, etapes, mots_cles, source):
    if existe_deja(carte, nom, mots_cles):
        print("Ignore, deja present: " + nom)
        return
    identifiant = normaliser(nom).replace(" ", "-").replace(":", "").replace("/", "-")
    zone = None
    for z in carte["zones"]:
        if z.get("id") == ZONE_CONNAISSANCES or z.get("nom") == ZONE_CONNAISSANCES:
            zone = z; break
    if zone is None:
        zone = {"id": ZONE_CONNAISSANCES, "nom": "Ce qu'Alice sait", "description": "Les tours de magie qu'elle connait", "noeuds": []}
        carte["zones"].insert(0, zone)
    zone.setdefault("noeuds", []).append({
        "id": identifiant, "nom": nom, "type": "circuit",
        "description": "Extrait de tour-community/" + str(source),
        "mots_cles": mots_cles, "etapes": etapes
    })
    print("AJOUT: " + nom)

def extraire_procedures_depot(chemin):
    procedures = []
    for fichier in Path(chemin).rglob("*"):
        if fichier.suffix in ['.md', '.txt'] and fichier.is_file():
            try:
                with open(fichier, 'r', encoding='utf-8', errors='ignore') as f:
                    contenu = f.read()
            except: continue
            sections = re.split(r'\n(?=[A-Z][a-z]+.*\n[0-9]+\.)', contenu)
            for section in sections:
                lignes = section.strip().split('\n')
                if len(lignes) < 3: continue
                titre = lignes[0].strip()[:80]
                etapes = []
                mots_cles = []
                for ligne in lignes[1:]:
                    match = re.match(r'^([0-9]+)\.\s*(.*)', ligne)
                    if match:
                        etapes.append(match.group(2).strip())
                    else:
                        mots = re.findall(r'\b[a-z]{3,}\b', ligne.lower())
                        mots_cles.extend(mots)
                if etapes:
                    procedures.append({
                        "source": str(fichier.relative_to(chemin)),
                        "titre": titre,
                        "etapes": etapes,
                        "mots_cles": list(set(mots_cles))[:10]
                    })
    return procedures

def main():
    if not os.path.exists(CHEMIN_DEPOT):
        print("Depot introuvable : " + CHEMIN_DEPOT)
        return
    carte = charger_carte()
    procs = extraire_procedures_depot(CHEMIN_DEPOT)
    print(str(len(procs)) + " procedures extraites.")
    for p in procs:
        ajouter_circuit(carte, p["titre"], "De " + p["source"], p["etapes"], p["mots_cles"], p["source"])
    sauvegarder_carte(carte)
    print("Extraction tour-community terminee.")

if __name__ == "__main__":
    main()