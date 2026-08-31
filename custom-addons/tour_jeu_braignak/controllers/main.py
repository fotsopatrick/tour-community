# -*- coding: utf-8 -*-
"""La page publique du Jeu de Braignak.

Règle « rien d'interne ne sort » : le public voit la vision, le mode
d'emploi, l'état de l'édition et les pseudos — jamais les prompts ni les
verdicts détaillés. Les prompts se lisent connecté, dans l'application.
"""
from odoo import http
from odoo.http import request


class JeuBraignakController(http.Controller):

    @http.route("/tour/jeu-braignak", type="http", auth="public",
                website=False)
    def page(self, **kw):
        Edition = request.env["braignak.jeu.edition"].sudo()
        edition = Edition.edition_courante() or Edition.search([], limit=1)
        interne = bool(request.env.user.id) and not request.env.user.share \
            and request.env.user.login != "public"
        return request.render("tour_jeu_braignak.page_jeu", {
            "edition": edition,
            "interne": interne,
            "envoye": kw.get("envoye"),
        })

    @http.route("/tour/jeu-braignak/participer", type="http", auth="user",
                methods=["POST"], website=False, csrf=True)
    def participer(self, pseudo=None, prompt=None, **kw):
        Edition = request.env["braignak.jeu.edition"].sudo()
        edition = Edition.edition_courante()
        if edition and (pseudo or "").strip() and (prompt or "").strip():
            request.env["braignak.jeu.participation"].sudo().create({
                "edition_id": edition.id,
                "name": pseudo.strip()[:40],
                "prompt": prompt.strip()[:500],
                "user_id": request.env.user.id,
            })
        return request.redirect("/tour/jeu-braignak?envoye=1")
