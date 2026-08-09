from odoo import http
from odoo.http import request


class RetoursController(http.Controller):
    @http.route("/retours/envoyer", type="json", auth="user", csrf=False, methods=["POST"])
    def envoyer(self, nom=None, message=None, **kw):
        msg = (message or "").strip()
        if len(msg) < 3 or len(msg) > 2000:
            return {"ok": False, "erreur": "Message invalide (3 a 2000 caracteres)."}
        Proj = request.env["project.project"].sudo()
        p = Proj.search([("name", "=", "Retours")], limit=1)
        pid = p.id if p else 1
        request.env["project.task"].sudo().create({
            "name": "[RETOUR] " + msg[:60],
            "project_id": pid,
            "description": "De: " + (nom or "anonyme") + "\n\n" + msg,
        })
        return {"ok": True}
