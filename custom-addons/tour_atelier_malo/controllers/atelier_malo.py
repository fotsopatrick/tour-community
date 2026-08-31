# -*- coding: utf-8 -*-
# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
from odoo import http
from odoo.http import request


class AtelierMalo(http.Controller):

    @http.route("/tour/atelier-malo", type="http", auth="user",
                website=False)
    def page(self, **kw):
        return request.render("tour_atelier_malo.page")

    @http.route("/tour/atelier-malo/envoyer", type="http", auth="user",
                methods=["POST"], csrf=False)
    def envoyer(self, titre=None, consigne=None, **kw):
        if consigne and consigne.strip():
            Demande = request.env["atelier.malo.demande"].sudo()
            Demande.create({
                "name": (titre or consigne)[:80],
                "consigne": consigne,
            }).action_envoyer()
        return request.redirect("/tour/atelier-malo")

    @http.route("/tour/atelier-malo/data", type="http", auth="user",
                website=False, csrf=False)
    def data(self, **kw):
        import json
        demandes = request.env["atelier.malo.demande"].sudo().search(
            [], order="create_date desc", limit=50)
        lignes = [{
            "id": d.id,
            "name": d.name,
            "consigne": d.consigne,
            "etat": d.etat,
            "reponse": d.reponse or "",
            "date": d.create_date.strftime("%d/%m %H:%M") if d.create_date
            else "",
        } for d in demandes]
        return request.make_response(
            json.dumps(lignes),
            headers=[("Content-Type", "application/json")])

    @http.route("/tour/atelier-malo/envoyer-tache", type="http", auth="user",
                methods=["POST"], csrf=False)
    def envoyer_tache(self, tache_id=None, **kw):
        import re
        if tache_id:
            t = request.env["project.task"].sudo().browse(int(tache_id))
            if t.exists():
                description = re.sub(r"<[^>]+>", " ",
                                     t.description or "").strip()
                consigne = "%s\n\n%s" % (t.name, description)
                request.env["atelier.malo.demande"].sudo().create({
                    "name": ("Tache : %s" % t.name)[:80],
                    "consigne": consigne,
                }).action_envoyer()
        return request.redirect("/tour/atelier-malo")

    @http.route("/tour/atelier-malo/taches", type="http", auth="user",
                website=False, csrf=False)
    def taches(self, **kw):
        import json
        Tache = request.env["project.task"].sudo()
        lignes = [{
            "id": t.id,
            "name": t.name,
            "projet": t.project_id.name or "",
        } for t in Tache.search([], order="create_date desc", limit=150)]
        return request.make_response(
            json.dumps(lignes),
            headers=[("Content-Type", "application/json")])

