# -*- coding: utf-8 -*-
"""Réponses — page web à deux barres de recherche (02/08, Patrick).

« Branche ton système de recherche à la place de celui d'Odoo. Juste une
barre, ou tu mets celle d'Odoo en haut et la mienne en bas — on peut
utiliser soit l'une soit l'autre. »

- Barre du haut : la recherche du module (comme celle d'Odoo), sur les
  fiches Réponses elles-mêmes (question + réponse).
- Barre du bas : la recherche unifiée de la tour (Chloe / /tour/recherche),
  dans toutes les sources (tâches, guides, décisions, missions, réponses,
  discussions, équipe).
"""
import re

from odoo import http
from odoo.http import request

# Masque les termes internes à l'affichage (parallèle à deploy/masquer-internes.py).
# Les motifs les plus précis d'abord, le générique ensuite.
_REMPLACEMENTS = [
    (r"tour_circuits", "système interne"),
    (r"page_equipage_public", "la page publique de l'équipe"),
    (r"circuites? rejouables?", "procédure rejouable"),
    (r"circuits? automatiques", "procédures automatiques"),
    (r"circuit", "procédure"),
    (r"circuits", "procédures"),
    (r"\bodoo\b", "système"),
    (r"\bOdoo\b", "le système"),
    (r"garde[- ]fou[sx]?(?: ?\([^)]*\))?", "sécurité interne"),
    (r"tour_equipage", "page équipe"),
]


def _masquer(texte):
    if not texte:
        return texte
    for motif, neutre in _REMPLACEMENTS:
        try:
            texte = re.sub(motif, neutre, texte, flags=re.IGNORECASE)
        except re.error:
            continue
    return texte


class ReponsesWeb(http.Controller):

    @http.route("/tour/reponses", type="http", auth="user", website=False)
    def reponses(self, q="", q2="", **kw):
        if not request.env.user.has_group("base.group_system"):
            return request.redirect("/community")
        env = request.env
        q = (q or "").strip()
        q2 = (q2 or "").strip()

        resultats_fiches = []
        Fiche = env["reponse.fiche"].sudo()
        # Les dernières réponses d'abord, par défaut ; la saisie filtre.
        base = Fiche.search([], order="date desc, id desc", limit=40)
        if len(q) >= 2:
            mot = "%" + q + "%"
            base = Fiche.search(
                ["|", ("name", "ilike", mot), ("reponse", "ilike", mot)],
                order="date desc, id desc", limit=40)
        resultats_fiches = [{
            "id": f.id, "name": _masquer(f.name or ""), "date": f.date,
            "auteur": f.auteur or "",
            "resume": _masquer(f.resume or ""),
            "reponse": _masquer(f.reponse or ""),
        } for f in base]

        resultats_tour = {}
        if len(q2) >= 2:
            resultats_tour = self._recherche_unifiee(env, q2)
        resultats_tour_liste = [(cle, items)
                                for cle, items in resultats_tour.items() if items]

        return request.render("tour_reponses.page_reponses", {
            "q": q, "q2": q2,
            "resultats_fiches": resultats_fiches,
            "resultats_tour": resultats_tour_liste,
        })

    def _recherche_unifiee(self, env, q):
        """La recherche Postgres de la tour, partout (même patron que
        /tour/recherche du copilote). Rien n'est inventé : chaque résultat
        existe réellement et contient la demande."""
        mot = "%" + q + "%"
        sources = [
            ("taches", "project_task", "name", "project.task"),
            ("guides", "tour_guide", "name", "tour.guide"),
            ("decisions", "decision_fiche", "name", "decision.fiche"),
            ("missions", "atelier_mission", "name", "atelier.mission"),
            ("reponses", "reponse_fiche", "name", "reponse.fiche"),
            ("discussions", "discussion_fil", "name", "discussion.fil"),
            ("equipe", "equipe_membre", "name", "equipe.membre"),
        ]
        resultats = {}
        for cle, table, colonne, _modele in sources:
            try:
                env.cr.execute(
                    "SELECT id, %s AS nom FROM %s WHERE %s ILIKE %%s "
                    "ORDER BY id DESC LIMIT 8" % (colonne, table, colonne),
                    (mot,))
                resultats[cle] = [{"id": r[0], "nom": r[1]}
                                  for r in env.cr.fetchall()]
            except Exception:  # noqa: BLE001 — table absente = source absente
                resultats[cle] = []
        return resultats
