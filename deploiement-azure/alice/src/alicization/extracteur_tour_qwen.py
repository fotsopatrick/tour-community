#!/usr/bin/env python3
# /home/orel/alicization/extracteur_tour_qwen.py
# Extraction robuste (Qwen direct) des circuits de tour-community
# Reutilise la logique de ingesteur_qwen.py

import os
import re
import sys

from ingesteur_qwen import (
    normaliser, charger_carte, sauvegarder_carte,
    interroger_alice, circuit_existe, ajouter_circuit
)

CHEMIN_GIT = "/home/orel/Desktop/Alicization/tour-community/tour-community-main"

DOCUMENTS = [
    "README.md",
    "TEST-MODULES.txt",
    "custom-addons/tour_condense_community/README.md",
]


def decouper_doc(contenu, nom_fichier):
    """Decoupe un document en sections exploitables (tetes ##, paragraphes)."""
    if not contenu:
        return []
    texte = re.sub(r'\r\n', '\n', contenu)
    texte = re.sub(r'\n\s*\n+', '\n\n', texte)
    sections = [texte]
    patterns = [
        r'\n(?=#{1,3}\s)',
        r'\n(?=\*\*\w)',
        r'\n(?=Le cad|Ce qu)',
    ]
    for pattern in patterns:
        nouveau = []
        for s in sections:
            nouveau.extend(re.split(pattern, s))
        sections = nouveau
    gardes = []
    for s in sections:
        s = s.strip()
        if 300 < len(s) <= 3500 and len(s.split('\n')) >= 3:
            gardes.append(s)
    return gardes


def prompt_circuit(texte_section, nom_fichier, type_doc):
    return """
Tu es un assistant qui extrait des procedures et des savoir-faire depuis la documentation du projet "Tour de controle" (plateforme de pilotage avec agents IA, edition Community).

Voici un extrait du document {fichier} :

---
{texte}
---

A partir de ce texte, identifie UN savoir-faire or procedure (un "circuit") :
1. Donne un titre court (max 80 caracteres).
2. Extraire les etapes (une liste d'actions concretes, maximum 10).
3. Identifie les mots-cles (5 a 10 termes importants).

Reponds UNIQUEMENT au format JSON valide :
{{"titre": "...", "etapes": ["etape1", "etape2", ...], "mots_cles": ["mot1", "mot2", ...]}}

Si le texte ne contient rien de procedural ou de savoir-faire, reponds : {{"titre": null, "etapes": [], "mots_cles": []}}
""".format(fichier=nom_fichier, texte=texte_section)[:6000]


def main():
    for doc in DOCUMENTS:
        chemin = os.path.join(CHEMIN_GIT, doc)
        if not os.path.exists(chemin):
            print("Introuvable: " + doc)
            continue
        with open(chemin, 'r', encoding='utf-8', errors='ignore') as f:
            contenu = f.read()
        sections = decouper_doc(contenu, doc)
        print("=== " + doc + " : " + str(len(sections)) + " section(s)")
        carte = charger_carte()
        for i, section in enumerate(sections):
            print("  Section " + str(i + 1) + "/" + str(len(sections)) + "...")
            prompt = prompt_circuit(section[:3000], doc, "doc")
            circuit = interroger_alice(prompt)
            if circuit and circuit.get("titre"):
                ajouter_circuit(carte, circuit, "tour-community/" + doc)
            else:
                print("    (aucun circuit)")
            sauvegarder_carte(carte)
    print("Extraction tour-community (Qwen) terminee.")


if __name__ == "__main__":
    main()