# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class PageProgression(http.Controller):

    @http.route("/tour/progression", type="http", auth="user", website=False)
    def progression(self, **kw):
        etat = request.env["tour.jalon"].sudo()._etat()
        return request.render("tour_progression.page_progression", etat)
