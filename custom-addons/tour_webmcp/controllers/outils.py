# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
"""Les outils WebMCP : définition et exécution.

Chaque outil est un couple {schema, fonction} :
- schema : le JSON Schema MCP (name, description, inputSchema) ;
- fonction : env(sudo), arguments -> (texte, est_une_erreur).

Les outils manipulent les briques réelles de la Tour. Rien n'est simulé :
la carte vient du JSON relevé, Chloé et Braignak passent par leur moteur
(DeepSeek ou Gemini), executer_circuit crée de vraies tâches.
"""

import datetime
import json
import logging
import os

_logger = logging.getLogger(__name__)

CARTE_PARAM_DASHBOARD = "tour_dashboard.cartes_path"
CARTE_PARAM_WEBMCP = "tour_webmcp.cartes_path"
CHEMINS_CARTE_FALLBACK = [
    "/opt/odoo/deploy/cartes.json",
    "/etc/tour/cartes.json",
]


def _param(env, nom, defaut=""):
    return (env["ir.config_parameter"].sudo().get_param(nom)
            or defaut).strip()


def _chemin_carte(env):
    """Le chemin du JSON de la carte vivante, en priorité les paramètres."""
    for chemin_param in (CARTE_PARAM_DASHBOARD, CARTE_PARAM_WEBMCP):
        chemin = _param(env, chemin_param)
        if chemin and os.path.isfile(chemin):
            return chemin
    for chemin in CHEMINS_CARTE_FALLBACK:
        if os.path.isfile(chemin):
            return chemin
    return None


def _lire_carte(env, args):
    chemin = _chemin_carte(env)
    if chemin:
        with open(chemin, encoding="utf-8", errors="replace") as f:
            try:
                data = json.load(f)
            except ValueError as exc:
                return ("Carte présente mais illisible (%s) : %s"
                        % (chemin, exc)), True
        return json.dumps(data, ensure_ascii=False, indent=2), False
    # Repli : une carte générée depuis la base, honnêtement datée.
    noeuds = []
    for module in env["ir.module.module"].search(
            [("state", "=", "installed"), ("name", "like", "tour_%")],
            order="name"):
        noeuds.append({"id": "mod-%s" % module.name, "type": "module",
                       "nom": module.name,
                       "detail": module.shortdesc or ""})
    for cron in env["ir.cron"].search([("active", "=", True)], limit=15):
        noeuds.append({"id": "cron-%s" % cron.id, "type": "cron",
                       "nom": cron.name or "", "detail": "ir.cron"})
    return json.dumps({
        "releve_le": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "générée par tour_webmcp (aucun cartes.json configuré)",
        "zones": [{"id": "tour", "nom": "Tour de contrôle — Community",
                   "description": "Modules et crons relevés dans la base",
                   "noeuds": noeuds}],
    }, ensure_ascii=False, indent=2), False


def _statut_tour(env, args):
    etats = {"modules": [], "compteurs": {}, "cles": {}, "crons": 0}
    etats["modules"] = [m.name for m in env["ir.module.module"].search(
        [("state", "=", "installed"), ("name", "like", "tour_%")],
        order="name")]
    etats["crons"] = env["ir.cron"].search_count([("active", "=", True)])
    if "project.task" in env:
        etats["compteurs"]["taches"] = env["project.task"].search_count([])
    if "actus.article" in env:
        etats["compteurs"]["actus"] = env["actus.article"].search_count([])
    if "tour.rappel" in env:
        etats["compteurs"]["rappels"] = env["tour.rappel"].search_count([])
    if "vault.secret" in env:
        etats["compteurs"]["secrets_au_coffre"] = \
            env["vault.secret"].search_count([])
    if "webmcp.circuit" in env:
        etats["compteurs"]["circuits"] = env["webmcp.circuit"].search_count([])
    icp = env["ir.config_parameter"].sudo()
    etats["cles"]["chloe_deepseek"] = bool(
        icp.get_param("tour_community_chat.api_key"))
    etats["cles"]["braignak_deepseek"] = bool(
        icp.get_param("tour_community_braignak.api_key"))
    etats["cles"]["gemini"] = bool(
        icp.get_param("tour_webmcp.gemini_key") or
        icp.get_param("tour_community_chat.gemini_key"))
    etats["moteurs"] = {
        "chloe": icp.get_param("tour_community_chat.moteur") or "deepseek",
        "braignak": icp.get_param("tour_community_braignak.moteur")
        or "deepseek",
    }
    return json.dumps(etats, ensure_ascii=False, indent=2), False


def _demander_a_chloe(env, args):
    from odoo.addons.tour_community_chat.controllers.chat_controller \
        import ChloéCommunity
    question = (args.get("question") or "").strip()
    if not question:
        return "Il faut une question.", True
    contexte = (args.get("contexte") or "").strip()
    historique = []
    if contexte:
        historique.append({"role": "user", "content": contexte})
    rep = ChloéCommunity()._repondre(question, historique, invite=False,
                                     env=env)
    if "erreur" in rep:
        return rep["erreur"], True
    return rep.get("reponse") or "(réponse vide)", False


def _observer_braignak(env, args):
    from odoo.addons.tour_community_braignak.controllers.braignak_controller \
        import BraignakCommunity
    cible = (args.get("cible") or "").strip()
    if not cible:
        return "Donne-moi une adresse (URL) ou une question.", True
    rep = BraignakCommunity()._observer(cible, env=env)
    if "erreur" in rep:
        return rep["erreur"], True
    return rep.get("reponse") or "(réponse vide)", False


def _fil_actus(env, args):
    if "actus.article" not in env:
        return "Le module tour_actus n'est pas installé.", True
    limite = min(int(args.get("limite") or 10), 50)
    langue = (args.get("langue") or "").strip()
    domaine = []
    if langue:
        domaine.append(("langue", "=", langue))
    articles = env["actus.article"].search(
        domaine, order="date_pub desc", limit=limite)
    fil = [{"titre": a.name, "lien": a.lien, "resume": a.resume,
            "date": (a.date_pub or "").strftime("%Y-%m-%d") if a.date_pub else ""}
           for a in articles]
    return json.dumps({"count": len(fil), "articles": fil},
                      ensure_ascii=False, indent=2), False


def _lister_projets(env, args):
    if "project.project" not in env:
        return "Le module project n'est pas installé.", True
    projets = []
    for p in env["project.project"].search([], order="name"):
        projets.append({"nom": p.name, "taches": p.task_count or 0,
                        "active": p.active})
    return json.dumps({"count": len(projets), "projets": projets},
                      ensure_ascii=False, indent=2), False


def _creer_tache(env, args):
    if "project.task" not in env:
        return "Le module project n'est pas installé.", True
    titre = (args.get("titre") or "").strip()
    if not titre:
        return "Il faut un titre pour la tâche.", True
    vals = {"name": titre}
    desc = (args.get("description") or "").strip()
    if desc:
        vals["description"] = "<p>%s</p>" % desc.replace("\n", "<br/>")
    tache = env["project.task"].create(vals)
    return json.dumps({"ok": True, "tache_id": tache.id, "titre": titre},
                      ensure_ascii=False), False


def _lister_rappels(env, args):
    if "tour.rappel" not in env:
        return "Le module tour_rappels n'est pas installé.", True
    actifs = bool(args.get("actifs") or True)
    rappels = env["tour.rappel"].search([("active", "=", actifs)], order="name")
    liste = [{"id": r.id, "note": r.name, "periodicite": r.periodicite or "",
              "prochaine_echeance": r.prochaine_echeance}
             for r in rappels]
    return json.dumps({"count": len(liste), "rappels": liste},
                      ensure_ascii=False, indent=2), False


def _executer_circuit(env, args):
    if "webmcp.circuit" not in env:
        return "Le module tour_webmcp n'est pas installé correctement.", True
    nom = (args.get("nom") or "").strip()
    circuit = env["webmcp.circuit"].search([("name", "=", nom)],
                                           limit=1)
    if not circuit:
        connus = [c.name for c in env["webmcp.circuit"].search(
            [("active", "=", True)], order="name")]
        return ("Circuit inconnu : %s. Connus : %s"
                % (nom, ", ".join(connus) or "aucun")), True
    creees = circuit.executer()
    return json.dumps({"ok": True, "circuit": nom,
                       "etapes_executees": len(creees), "taches": creees},
                      ensure_ascii=False, indent=2), False


OUTILS = {
    "lire_carte": {
        "schema": {"name": "lire_carte",
                   "description": "La carte vivante de la Tour : le JSON "
                                  "d'infrastructure relevé (machines, "
                                  "conteneurs, agents, outils). Si aucun "
                                  "relevé n'est configuré, une carte "
                                  "générée sur-le-champ depuis la base.",
                   "inputSchema": {"type": "object", "properties": {}}},
        "fonction": _lire_carte,
    },
    "statut_tour": {
        "schema": {"name": "statut_tour",
                   "description": "L'état de la Tour : modules installés, "
                                  "crons actifs, compteurs (tâches, actus, "
                                  "rappels), clés présentes, moteurs choisis.",
                   "inputSchema": {"type": "object", "properties": {}}},
        "fonction": _statut_tour,
    },
    "demander_a_chloe": {
        "schema": {"name": "demander_a_chloe",
                   "description": "Pose une question à Chloé, l'assistante "
                                  "de la Tour. Elle répond en français et "
                                  "peut créer des tâches ou des apps.",
                   "inputSchema": {"type": "object",
                                   "properties": {
                                       "question": {"type": "string",
                                                    "description": "La question à poser."},
                                       "contexte": {"type": "string",
                                                    "description": "Contexte optionnel à fournir."}},
                                   "required": ["question"]}},
        "fonction": _demander_a_chloe,
    },
    "observer_braignak": {
        "schema": {"name": "observer_braignak",
                   "description": "Demande à Braignak, l'observateur, "
                                  "d'analyser une URL ou une question et de "
                                  "dire ce que ça fait, ce qui manque, ce "
                                  "qu'on peut en tirer.",
                   "inputSchema": {"type": "object",
                                   "properties": {
                                       "cible": {"type": "string",
                                                 "description": "Une URL http(s) ou une question."}},
                                   "required": ["cible"]}},
        "fonction": _observer_braignak,
    },
    "fil_actus": {
        "schema": {"name": "fil_actus",
                   "description": "Le fil d'actualités collecté par la Tour "
                                  "(flux RSS).",
                   "inputSchema": {"type": "object",
                                   "properties": {
                                       "limite": {"type": "integer",
                                                  "description": "Nombre d'articles (max 50)."},
                                       "langue": {"type": "string",
                                                  "description": "Code langue (ex. fr, en)."}}}},
        "fonction": _fil_actus,
    },
    "lister_projets": {
        "schema": {"name": "lister_projets",
                   "description": "Les projets et leurs nombres de tâches.",
                   "inputSchema": {"type": "object", "properties": {}}},
        "fonction": _lister_projets,
    },
    "creer_tache": {
        "schema": {"name": "creer_tache",
                   "description": "Crée une tâche dans la Tour (ce qu'il y a "
                                  "à faire).",
                   "inputSchema": {"type": "object",
                                   "properties": {
                                       "titre": {"type": "string",
                                                 "description": "Le titre de la tâche."},
                                       "description": {"type": "string",
                                                       "description": "Ce qu'il faut faire (optionnel)."}},
                                   "required": ["titre"]}},
        "fonction": _creer_tache,
    },
    "lister_rappels": {
        "schema": {"name": "lister_rappels",
                   "description": "Les rappels récurrents de la Tour.",
                   "inputSchema": {"type": "object",
                                   "properties": {
                                       "actifs": {"type": "boolean",
                                                  "description": "Rappels actifs seulement (défaut oui)."}}}},
        "fonction": _lister_rappels,
    },
    "executer_circuit": {
        "schema": {"name": "executer_circuit",
                   "description": "Exécute un circuit connu de la Tour : "
                                  "chaque étape du circuit devient une vraie "
                                  "tâche.",
                   "inputSchema": {"type": "object",
                                   "properties": {
                                       "nom": {"type": "string",
                                               "description": "Le nom du circuit (ex. Decouverte)."}},
                                   "required": ["nom"]}},
        "fonction": _executer_circuit,
    },
}


def outils_liste():
    """La liste MCP des outils (schemas)."""
    return [o["schema"] for o in OUTILS.values()]


def appeler_outil(env, nom, args):
    """Exécute un outil. Retourne (texte, est_erreur)."""
    outil = OUTILS.get(nom)
    if not outil:
        return ("Outil inconnu : %s. Connus : %s."
                % (nom, ", ".join(sorted(OUTILS)))), True
    try:
        return outil["fonction"](env, args or {})
    except Exception as exc:  # noqa: BLE001
        _logger.exception("WebMCP : échec de l'outil %s", nom)
        return "Erreur interne à l'outil %s : %s" % (nom, exc), True