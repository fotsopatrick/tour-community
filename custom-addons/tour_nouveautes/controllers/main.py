from datetime import timedelta

from odoo import fields, http
from odoo.http import request


class TourNouveautes(http.Controller):
    @http.route("/tour/nouveautes", type="http", auth="user", website=False)
    def nouveautes(self, **kw):
        Nouveaute = request.env["tour.nouveaute"].sudo()
        toutes = Nouveaute.search([])
        seuil = fields.Date.context_today(request.env.user) - timedelta(days=30)
        return request.render("tour_nouveautes.page_nouveautes", {
            "recentes": toutes.filtered(lambda n: n.date >= seuil),
            "toutes": toutes,
            "seuil": seuil,
        })
