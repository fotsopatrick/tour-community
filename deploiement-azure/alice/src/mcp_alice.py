#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Serveur MCP d'ALICE — expose Alice aux agents (opencode).
Fonctionne en stdio, exécuté localement ou dans le conteneur.

Outils exposés :
  - lire_carte()              : vue d'ensemble de la carte vivante
  - lancer_circuit(nom)       : lance le circuit de la carte (étapes/actions)
  - demander_alice(message)   : passe la requête au routeur d'Alice
  - ingerer_connaissance(contenu, source)
                              : ingère une connaissance (texte/SQLite/Postgres)
  - rechercher_connaissance(requete, n)
                              : retrouve les chunks les plus pertinents

Cerveau paramétrable par env (Qwen local | Gemini | Azure OpenAI), voir
routeur.call_model.
"""
import sys
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
for _chemin in (os.path.join(_HERE, "alicization"),
                os.path.join(_HERE, "..", "src", "alicization"),
                "/home/alice/alicization", "/home/alice", _HERE):
    if _chemin not in sys.path:
        sys.path.insert(0, _chemin)

from mcp.server.mcpserver import MCPServer  # noqa: E402

from routeur import Routeur          # noqa: E402
from knowledge import Connaissance   # noqa: E402

mcp = MCPServer("alice")

_routeur = None
_connaissance = None


def _get_routeur():
    global _routeur
    if _routeur is None:
        _routeur = Routeur(
            chemin_carte=os.environ.get(
                "ALICE_CARTE", "/home/alice/carte-vivante/cartes.json"),
            chemin_db=os.environ.get(
                "ALICE_DB", "/home/alice/alicization/state/alicization.db"),
        )
    return _routeur


def _get_connaissance():
    global _connaissance
    if _connaissance is None:
        _connaissance = Connaissance(
            url_bdd=os.environ.get("ALICE_DB_URL", "") or None,
            chemin_db=os.environ.get(
                "ALICE_DB", "/home/alice/alicization/state/alicization.db"),
        )
    return _connaissance


@mcp.tool()
def lire_carte() -> str:
    """Retourne une vue d'ensemble de la carte vivante d'Alice (zones, noeuds, circuits)."""
    try:
        r = _get_routeur()
        stats = r.carte_stats()
        noeuds = r.carte.get_tous_les_noeuds()
        resume = {
            "zones": stats["total_zones"],
            "noeuds": stats["total_noeuds"],
            "types": stats["types"],
            "liste": [
                {"nom": n["nom"], "type": n.get("type"), "zone": n.get("zone", "")}
                for n in noeuds[:60]
            ],
        }
        return json.dumps(resume, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"erreur": str(e)}, ensure_ascii=False)


@mcp.tool()
def lancer_circuit(nom: str) -> str:
    """Lance un circuit de la carte vivante (ex: "Trouver 712")."""
    try:
        r = _get_routeur()
        resultat = r.router(f"trouver {nom}")
        rep = {
            "decision": resultat.get("decision"),
            "source": resultat.get("source"),
            "message": resultat.get("message"),
            "resultat": resultat.get("resultat"),
        }
        return json.dumps(rep, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"erreur": str(e)}, ensure_ascii=False)


@mcp.tool()
def demander_alice(message: str) -> str:
    """Passe une demande libre au routeur d'Alice (carte -> memoire -> outils -> modèle)."""
    try:
        r = _get_routeur()
        resultat = r.router(message)
        rep = {
            "decision": resultat.get("decision"),
            "source": resultat.get("source"),
            "message": resultat.get("message") or resultat.get("reponse"),
            "resultat": resultat.get("resultat"),
        }
        return json.dumps(rep, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"erreur": str(e)}, ensure_ascii=False)


@mcp.tool()
def ingerer_connaissance(contenu: str, source: str = "manuel") -> str:
    """Ingère une connaissance dans la mémoire longue d'ALICE (table knowledge).

    Le contenu est découpé en chunks (ALICE_CHUNK_SIZE / ALICE_CHUNK_OVERLAP),
    stocké dans SQLite (ALICE_DB) ou PostgreSQL (ALICE_DB_URL) et indexé.
    Retourne {status: ok, titre, source, chunks}.
    """
    try:
        c = _get_connaissance()
        resultat = c.ingerer_contenu(contenu or "", source=source)
        return json.dumps({"status": "ok", **resultat}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "erreur", "erreur": str(e)},
                          ensure_ascii=False)


@mcp.tool()
def rechercher_connaissance(requete: str, n: int = 5) -> str:
    """Retrouve dans la mémoire longue d'ALICE les chunks les plus pertinents."""
    try:
        c = _get_connaissance()
        resultats = c.chercher(requete or "", n=n)
        return json.dumps({"requete": requete, "resultats": resultats},
                          ensure_ascii=False)
    except Exception as e:
        return json.dumps({"erreur": str(e)}, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()