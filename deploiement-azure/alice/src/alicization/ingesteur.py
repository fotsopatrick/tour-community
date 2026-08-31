#!/usr/bin/env python3
# /home/orel/alicization/ingesteur.py
# Ingestion de documents texte vers circuits pour Alice

import os
import json
import re

# Chemin de la carte vivante
CHEMIN_CARTE = "/home/alice/carte-vivante/cartes.json"

# La carte réelle utilise "noeuds" (pas "circuits") et les circuits ont "type": "circuit"
ZONE_CONNAISSANCES = "connaissances"


def normaliser(texte):
    """Normalise les accents pour comparer (é→e, à→a...)."""
    accents = {
        'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
        'à': 'a', 'â': 'a', 'ä': 'a',
        'ç': 'c', 'ô': 'o', 'ö': 'o', 'î': 'i', 'ï': 'i',
        'û': 'u', 'ü': 'u', 'ù': 'u',
        'É': 'e', 'È': 'e', 'Ê': 'e', 'Ë': 'e',
        'À': 'a', 'Â': 'a', 'Ä': 'a', 'Ç': 'c', 'Ô': 'o',
        'Ö': 'o', 'Î': 'i', 'Ï': 'i', 'Û': 'u', 'Ü': 'u', 'Ù': 'u'
    }
    for origin, fin in accents.items():
        texte = texte.replace(origin, fin)
    return texte.lower()


def charger_carte():
    with open(CHEMIN_CARTE, 'r', encoding='utf-8') as f:
        return json.load(f)


def sauvegarder_carte(carte):
    with open(CHEMIN_CARTE, 'w', encoding='utf-8') as f:
        json.dump(carte, f, indent=2, ensure_ascii=False)


def extraire_procedures_texte(contenu):
    """
    Extrait des procédures à partir d'un texte structuré.
    Détecte les sections avec des étapes numérotées.
    """
    procedures = []
    # Regex pour trouver des sections avec étapes
    sections = re.split(r'\n(?=[A-Z][a-z]+.*\n[0-9]+\.)', contenu)
    for section in sections:
        lignes = section.strip().split('\n')
        if not lignes:
            continue
        titre = lignes[0].strip()
        etapes = []
        mots_cles = []
        for ligne in lignes[1:]:
            # Détecter les étapes numérotées
            match = re.match(r'^([0-9]+)\.\s*(.*)', ligne)
            if match:
                etapes.append(match.group(2).strip())
            else:
                # Ajouter des mots-clés à partir des lignes non numérotées
                mots = re.findall(r'\b[a-z]{3,}\b', ligne.lower())
                mots_cles.extend(mots)
        if etapes:
            procedures.append({
                "titre": titre,
                "etapes": etapes,
                "mots_cles": list(set(mots_cles))[:10]  # 10 premiers mots-clés uniques
            })
    return procedures


def ajouter_circuit(carte, nom, description, etapes, mots_cles):
    """Ajoute un circuit à la carte vivante, dans la zone 'connaissances'."""
    identifiant = normaliser(nom).replace(" ", "-").replace(":", "").replace("/", "-")

    # Vérifier si le circuit existe déjà (même id ou même nom)
    for zone in carte["zones"]:
        for noeud in zone.get("noeuds", []):
            if noeud.get("id") == identifiant or noeud.get("nom") == nom:
                print(f"⚠️ Circuit '{nom}' existe déjà.")
                return False

    # Trouver la zone 'connaissances'
    zone_cible = None
    for zone in carte["zones"]:
        if zone.get("id") == ZONE_CONNAISSANCES or zone.get("nom") == ZONE_CONNAISSANCES:
            zone_cible = zone
            break
    if zone_cible is None:
        zone_cible = {"id": ZONE_CONNAISSANCES, "nom": "Ce qu'Alice sait",
                      "description": "Les tours de magie qu'elle connaît", "noeuds": []}
        carte["zones"].insert(0, zone_cible)

    zone_cible.setdefault("noeuds", []).append({
        "id": identifiant,
        "nom": nom,
        "type": "circuit",
        "description": description,
        "mots_cles": mots_cles,
        "etapes": etapes
    })
    print(f"✅ Circuit '{nom}' ajouté.")
    return True


def ingerer_document(chemin_fichier):
    """Lit un fichier texte et extrait des circuits."""
    with open(chemin_fichier, 'r', encoding='utf-8', errors='ignore') as f:
        contenu = f.read()
    procedures = extraire_procedures_texte(contenu)
    carte = charger_carte()
    for proc in procedures:
        # Nettoyer le titre
        titre = proc['titre'][:80]
        ajouter_circuit(carte, titre, f"Extrait de {os.path.basename(chemin_fichier)}",
                        proc['etapes'], proc['mots_cles'])
    sauvegarder_carte(carte)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 ingesteur.py <fichier_texte>")
        sys.exit(1)
    ingerer_document(sys.argv[1])