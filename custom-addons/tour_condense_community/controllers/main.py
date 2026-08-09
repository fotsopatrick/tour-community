# -*- coding: utf-8 -*-
"""La page Condensation : tous les textes longs, résumé d'abord, détail à un clic.

Même parti pris que la Salle des débats : une page HTML rendue par le serveur,
sans OWL, sans JavaScript — le détail s'ouvre avec la balise native <details>.
Robuste, lisible sur téléphone, et rien ne casse à la mise à jour.
"""

from odoo import http
from odoo.http import request


class CondensePage(http.Controller):

    @http.route("/tour/condense", type="http", auth="user", website=False)
    def condense(self, **kw):
        env = request.env
        Cible = env["condense.cible"].sudo()
        Resume = env["condense.resume"].sudo()
        Engine = env["condense.engine"].sudo()

        # Rattrapage à la volée si l'inventaire est vide (première visite).
        if Cible.search_count([("active", "=", True)]) == 0:
            Engine._inventorier()

        cibles = Cible.search([("active", "=", True)], order="nom_modele")
        cartes = []
        for c in cibles:
            modele = c.nom_modele
            if modele not in env:
                continue
            model = env[modele]
            if c.champ not in model._fields:
                continue
            # Les textes longs de cette cible, sans résumé encore.
            records = model.sudo().search([], order="id desc", limit=500)
            champ = c.champ
            for r in records:
                brut = r[champ]
                if not brut:
                    continue
                longueur = len(Engine._nettoyer(brut))
                if longueur <= c.seuil:
                    continue
                resume = Resume.search([
                    ("cible_id", "=", c.id), ("res_id", "=", r.id)], limit=1)
                texte = resume.texte if resume else "(pas encore résumé)"
                mode = resume.mode if resume else ""
                nom = r.display_name or r.name or ("#%s" % r.id)
                cartes.append({
                    "modele": modele,
                    "nom": str(nom)[:90],
                    "longueur": longueur,
                    "texte": texte,
                    "mode": mode,
                    "detail": str(brut),
                    "lien": "%s/web#id=%s&model=%s&view_type=form" % (
                        env["ir.config_parameter"].sudo().get_param(
                            "web.base.url", "").rstrip("/"),
                        r.id, modele),
                })

        cartes.sort(key=lambda c: -c["longueur"])
        nb = len(cartes)
        return request.render("tour_condense_community.page_condense", {
            "cartes": cartes,
            "nb": nb,
        })
