# -*- coding: utf-8 -*-
"""La page des guides — RÉSERVÉE AU PROPRIÉTAIRE (01/08).

Patrick veut voir ses guides depuis le menu Actions, et PERSONNE d'autre —
pas un autre admin, pas la démo, pas un invité. Les guides marqués
« interne » ne sont d'ailleurs montrés qu'à lui (ils contiennent des
références privées). Le contrôle se fait sur le courriel du propriétaire,
pas sur le groupe admin : le compte démo est admin (erp_manager) et ne
doit pas voir ça.
"""
from odoo import http
from odoo.http import request

def _owner_ids():
    """Identifiants du propriétaire : config (hors git)."""
    val = (request.env["ir.config_parameter"].sudo().get_param(
        "tour_owner.identifiants", "") or "")
    return {x.strip().lower() for x in val.split(",") if x.strip()}


class PageGuides(http.Controller):

    @http.route("/tour/guides", type="http", auth="user", website=False)
    def guides(self, **kw):
        if request.env.user.login.lower() not in _owner_ids():
            return request.redirect("/tour/dashboard")
        guides = request.env["tour.guide"].sudo().search(
            [], order="write_date desc, create_date desc, id desc")
        # Le groupement se fait ici, en Python, pas dans le gabarit : le QWeb
        # (guides.groupby) plantait en 500, et un groupement calculé en
        # Python est testable sans recharger un template.
        libelles = dict(request.env["tour.guide"]._fields["categorie"].selection)
        groupes = {}
        for g in guides:
            groupes.setdefault(g.categorie, []).append(g)
        ordre = [c for c in libelles if c in groupes]
        return request.render("tour_guides.page_guides", {
            "groupes": [(libelles[c], groupes[c]) for c in ordre],
            "total": len(guides),
        })
