# -*- coding: utf-8 -*-
"""Les témoignages des agents, VUS DU PUBLIC.

Chaque membre de l'équipe tient son témoignage (extrait d'une mission réelle,
jamais inventé). Cette page publique montre, pour chaque agent, les entrées
que le propriétaire a retenues (publie=True) — rendues comme des articles :
l'agent, la date, ce qu'il a vécu. Rien ne s'affiche tout seul : publier
reste une décision de Patrick (le circuit « Témoignage d'un agent »).
"""
from odoo import http
from odoo.http import request


class TemoignagesPublic(http.Controller):

    @http.route("/tour/temoignages-public", type="http", auth="public",
                website=False)
    def temoignages_public(self, **kw):
        Entre = request.env["temoignage.entree"].sudo()
        entrees = Entre.search([("publie", "=", True)], order="quand desc")
        # Regroupées par agent, du plus récent au plus ancien.
        groupes = {}
        for e in entrees:
            groupes.setdefault(e.agent, []).append(e)
        # L'ordre des agents : ceux qui ont le plus à dire d'abord, puis
        # alphabétique. Un agent muet n'apparaît pas — on ne fabrique rien.
        ordre = sorted(groupes.items(), key=lambda kv: (-len(kv[1]), kv[0]))
        return request.render("tour_temoignage.page_temoignages_public", {
            "agents": ordre,
            "total": len(entrees),
        })
