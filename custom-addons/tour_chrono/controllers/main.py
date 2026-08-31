# -*- coding: utf-8 -*-
"""La page du Chrono : qui travaille MAINTENANT, et les totaux.

Le « temps réel » demandé par Patrick, sans une ligne de JavaScript
compliquée : la page se recharge toute seule toutes les 60 secondes
(balise meta refresh) et les missions en cours affichent leur temps
écoulé calculé au rendu. C'est assez réel pour un humain, et ça ne coûte
rien à personne.
"""
from odoo import fields, http
from odoo.http import request


class ChronoPage(http.Controller):

    @http.route("/tour/chrono", type="http", auth="user", website=False)
    def chrono(self, **kw):
        env = request.env
        maintenant = fields.Datetime.now()

        # Qui travaille en ce moment : les missions envoyées, avec l'écoulé.
        en_cours = []
        if "atelier.mission" in env:
            for m in env["atelier.mission"].sudo().search(
                    [("etat", "=", "envoyee")], order="envoyee_le"):
                minutes = 0
                if m.envoyee_le:
                    minutes = int(
                        (maintenant - m.envoyee_le).total_seconds() // 60)
                agent = m.AGENTS.get((m.moteur or "").strip(), "L atelier")
                en_cours.append({"agent": agent, "nom": m.name,
                                 "minutes": minutes})

        # Les totaux, mesures et estimations séparés — les mélanger sans le
        # dire serait fabriquer un chiffre.
        Temps = env["chrono.temps"].sudo()
        il_y_a_7j = fields.Datetime.subtract(maintenant, days=7)

        def totaux(domaine):
            lignes = Temps.read_group(
                domaine, ["minutes:sum"], ["agent"], orderby="minutes desc")
            return [(l["agent"], (l["minutes"] or 0) / 60.0) for l in lignes]

        par_agent = totaux([("source", "=", "mesure")])
        par_agent_7j = totaux([("source", "=", "mesure"),
                               ("quand", ">=", il_y_a_7j)])
        estimations = totaux([("source", "=", "estimation")])
        par_projet = [
            (l["projet"], (l["minutes"] or 0) / 60.0)
            for l in Temps.read_group([], ["minutes:sum"], ["projet"],
                                      orderby="minutes desc")]
        total_mesure = sum(h for _a, h in par_agent)
        total_estime = sum(h for _a, h in estimations)

        return request.render("tour_chrono.page_chrono", {
            "en_cours": en_cours,
            "par_agent": par_agent,
            "par_agent_7j": par_agent_7j,
            "estimations": estimations,
            "par_projet": par_projet[:12],
            "total_mesure": total_mesure,
            "total_estime": total_estime,
        })
