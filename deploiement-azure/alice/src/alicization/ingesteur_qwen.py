#!/usr/bin/env python3
# /home/alice/alicization/ingesteur_qwen.py
# Ingestion de documents PDF en circuits via Alice (Qwen)
# AVEC DEDOUBLONNAGE ET SCHEMA REEL (noeuds + type: circuit)

import os
import json
import re
import subprocess
import urllib.request

# Chemins
DOSSIER_DOCS = "/home/alice/Desktop/Alicization/topdown/"
CHEMIN_CARTE = "/home/alice/carte-vivante/cartes.json"
URL_ALICE = "http://192.168.1.61:8081/v1/chat/completions"
ZONE_CONNAISSANCES = "connaissances"
LIMITE_CARACTERES = 3000  # Tronquer les sections trop longues


def normaliser(texte):
    """Normalise les accents pour comparer (e-->e, a-->a...)."""
    if not texte:
        return ""
    accents = {
        'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
        'à': 'a', 'â': 'a', 'ä': 'a',
        'ç': 'c', 'ô': 'o', 'ö': 'o',
        'î': 'i', 'ï': 'i', 'û': 'u', 'ü': 'u', 'ù': 'u'
    }
    for origin, fin in accents.items():
        texte = texte.replace(origin, fin)
    return texte.lower().strip()


def charger_carte():
    with open(CHEMIN_CARTE, 'r', encoding='utf-8') as f:
        return json.load(f)


def sauvegarder_carte(carte):
    with open(CHEMIN_CARTE, 'w', encoding='utf-8') as f:
        json.dump(carte, f, indent=2, ensure_ascii=False)


def extraire_texte_pdf(chemin_pdf):
    """Extrait le texte d'un PDF : pypdf (pure Python) en primaire, sinon pdftotext."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(chemin_pdf)
        return "\n".join((p.extract_text() or "") for p in reader.pages).strip()
    except Exception:
        pass
    try:
        resultat = subprocess.run(
            ["pdftotext", chemin_pdf, "-"],
            capture_output=True, text=True, timeout=120
        )
        if resultat.returncode != 0:
            print("pdftotext a echoue pour " + chemin_pdf)
            return ""
        return resultat.stdout
    except Exception as e:
        print("Erreur d'extraction: " + str(e))
        return ""


def decouper_texte_en_sections(texte):
    """Decoupe le texte en sections significatives (chapitres, sections)."""
    if not texte:
        return []
    texte = re.sub(r'\n\s*\n', '\n\n', texte)
    patterns = [
        r'\n(?=Chapter\s+\d+\.\s*[A-Z])',
        r'\n(?=[0-9]+\.[0-9]+\.\s*[A-Z])',
        r'\n(?=LFS\s+[0-9]+\.[0-9]+\s*[A-Z])',
        r'\n(?=Section\s+\d+\.\s*[A-Z])',
        r'\n(?=[A-Z][a-z]+ +[0-9]+\.[0-9]+\.?)'
    ]
    sections = [texte]
    for pattern in patterns:
        new_sections = []
        for section in sections:
            parts = re.split(pattern, section)
            new_sections.extend(parts)
        sections = new_sections
    # Filtrer les sections trop petites
    return [s.strip() for s in sections if len(s.strip()) > 500]


def generer_prompt_circuit(texte_section, nom_fichier):
    """Construit le prompt pour Alice (Qwen)."""
    if len(texte_section) > LIMITE_CARACTERES:
        texte_section = texte_section[:LIMITE_CARACTERES] + "..."
    return """
Tu es un assistant qui extrait des procedures de documents techniques.

Voici un extrait de documentation extrait de {fichier} :

---
{texte}
---

A partir de ce texte, identifie UNE procedure (un "circuit") :
1. Donne un titre court (max 80 caracteres).
2. Extraire les etapes (une liste d'actions concretes, maximum 10).
3. Identifie les mots-cles (5 a 10 termes importants).

Reponds UNIQUEMENT au format JSON valide :
{{"titre": "...", "etapes": ["etape1", "etape2", ...], "mots_cles": ["mot1", "mot2", ...]}}

Si le texte ne contient pas de procedure identifiable, reponds : {{"titre": null, "etapes": [], "mots_cles": []}}
""".format(fichier=nom_fichier, texte=texte_section)


def interroger_alice(prompt):
    """Envoie le prompt a Qwen directement (llama-server, port 8081).
    On contourne le routeur car son contenu declencherait un match carte."""
    try:
        payload = json.dumps({
            "model": "qwen2.5-3b-instruct",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": 600
        }).encode('utf-8')
        req = urllib.request.Request(
            URL_ALICE,
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            reponse = data["choices"][0]["message"]["content"]
            match = re.search(r'\{.*\}', reponse, re.DOTALL)
            if match:
                return json.loads(match.group())
            return None
    except Exception as e:
        print("Erreur d'interrogation d'Alice: " + str(e))
        return None


def circuit_existe(carte, nouveau_circuit):
    """Verifie si un circuit existe deja (nom, id ou mots-cles)."""
    nom_norm = normaliser(nouveau_circuit.get("titre", ""))
    id_norm = nom_norm.replace(" ", "-").replace(":", "").replace("/", "-")
    mots_cles = {normaliser(m) for m in nouveau_circuit.get("mots_cles", [])}
    for zone in carte["zones"]:
        for noeud in zone.get("noeuds", []):
            if noeud.get("id") == id_norm or normaliser(noeud.get("nom", "")) == nom_norm:
                return True
            existing = {normaliser(m) for m in noeud.get("mots_cles", [])}
            if len(mots_cles & existing) >= 3:
                return True
    return False


def ajouter_circuit(carte, circuit, source_fichier):
    """Ajoute un circuit a la carte s'il n'existe pas deja."""
    if not circuit.get("titre"):
        return

    if circuit.get("mots_cles"):
        circuit["mots_cles"] = list(set(circuit["mots_cles"]))

    if circuit_existe(carte, circuit):
        print("Ignore, deja present: " + circuit["titre"])
        return

    identifiant = normaliser(circuit["titre"]).replace(" ", "-").replace(":", "").replace("/", "-")

    zone_cible = None
    for zone in carte["zones"]:
        if zone.get("id") == ZONE_CONNAISSANCES or zone.get("nom") == ZONE_CONNAISSANCES:
            zone_cible = zone
            break
    if zone_cible is None:
        zone_cible = {"id": ZONE_CONNAISSANCES, "nom": "Ce qu'Alice sait",
                      "description": "Les tours de magie qu'elle connait", "noeuds": []}
        carte["zones"].insert(0, zone_cible)

    zone_cible.setdefault("noeuds", []).append({
        "id": identifiant,
        "nom": circuit["titre"],
        "type": "circuit",
        "description": "Extrait par Alice de " + os.path.basename(source_fichier),
        "mots_cles": circuit.get("mots_cles", []),
        "etapes": circuit.get("etapes", [])
    })
    print("AJOUT: " + circuit["titre"])


def ingerer_document(chemin_pdf):
    """Inge re un document PDF complet."""
    nom_fichier = os.path.basename(chemin_pdf)
    print("Traitement de " + nom_fichier + "...")
    texte = extraire_texte_pdf(chemin_pdf)
    if not texte:
        print("Aucun texte extrait de " + nom_fichier)
        return
    sections = decouper_texte_en_sections(texte)
    if not sections:
        print("Aucune section identifiee dans " + nom_fichier)
        return
    print("   " + str(len(sections)) + " section(s) identifiee(s).")
    carte = charger_carte()
    circuits_ajoutes = 0
    max_sections = min(len(sections), 15)
    for i in range(max_sections):
        section = sections[i]
        print("  Section " + str(i + 1) + "/" + str(max_sections) + "...")
        prompt = generer_prompt_circuit(section, nom_fichier)
        circuit = interroger_alice(prompt)
        if circuit and circuit.get("titre"):
            ajouter_circuit(carte, circuit, nom_fichier)
            circuits_ajoutes += 1
        else:
            print("  Aucun circuit identifie.")
    sauvegarder_carte(carte)
    print("Document " + nom_fichier + " ingere. " + str(circuits_ajoutes) + " circuit(s) ajoute(s).")


if __name__ == "__main__":
    if not os.path.exists(DOSSIER_DOCS):
        print("Dossier " + DOSSIER_DOCS + " introuvable.")
        exit(1)

    try:
        req = urllib.request.Request(URL_ALICE, method='POST',
                                     data=b'{"model":"qwen2.5-3b-instruct","messages":[{"role":"user","content":"ping"}]}',
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            print("Qwen repond OK (HTTP " + str(resp.status) + ").")
    except Exception as e:
        print("Alice injoignable (" + str(e) + ").")

    for fichier in sorted(os.listdir(DOSSIER_DOCS)):
        if fichier.endswith(".pdf"):
            ingerer_document(os.path.join(DOSSIER_DOCS, fichier))

    print("Ingestion terminee.")