# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request

# RÉSERVÉ AU PROPRIÉTAIRE (01/08) : comparer la prod, la démo et le test,
# c'est voir l'intérieur de la tour. Même la démo : son compte admin EST
# celui de Patrick. On contrôle par le courriel, pas par le groupe admin —
# un autre admin (ou le compte démo d'un client) ne doit pas voir ça.
def _owner_ids():
    """Identifiants du propriétaire : config (hors git)."""
    val = (request.env["ir.config_parameter"].sudo().get_param(
        "tour_owner.identifiants", "") or "")
    return {x.strip().lower() for x in val.split(",") if x.strip()}


class PageEnvironnements(http.Controller):

    @http.route("/tour/environnements", type="http", auth="user", website=False)
    def environnements(self, projet=None, **kw):
        # Comparer prod/démo/test, c'est voir l'intérieur de la tour : réservé
        # au propriétaire (règle de Patrick, 01/08 — un invité ne voit que ses
        # données ; et ici même les autres admins sont exclus).
        if request.env.user.login.lower() not in _owner_ids():
            return request.redirect("/tour/dashboard")
        Env = request.env["tour.environnement"].sudo()
        Proj = request.env["project.project"].sudo()
        # Les projets qui ont au moins deux environnements : comparer une copie
        # avec elle-même n'apprend rien.
        avec = {e.projet_id.id for e in Env.search([])}
        projets = Proj.browse(list(avec))
        # Les projets qui n ont pas encore d environnement : affiches en grise,
        # pour qu on voie qu ils existent et qu on puisse leur en declarer.
        autres = Proj.search([("id", "not in", list(avec)),
                              ("active", "=", True)], limit=12)
        if projet:
            courant = Proj.browse(int(projet))
        else:
            courant = projets[:1]
        data = Env.comparer(courant.id) if courant else {
            "environnements": Env.browse(), "lignes": [], "identiques": 0,
            "manques": {}}
        return request.render("tour_environnements.page_environnements", {
            "projets": projets,
            "autres": autres,
            "courant": courant,
            "envs": data["environnements"],
            "lignes": data["lignes"],
            "identiques": data["identiques"],
            "manques": data.get("manques") or {},
            "anomalies": data.get("anomalies") or {},
            "avances": data.get("avances") or {},
        })
