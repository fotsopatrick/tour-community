# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request

VITRINE = "/home/ubuntu/vitrine/prod"
PAGES = {
    "qui": ("À propos", "qui.html"),
    "realisations": ("Réalisations", "realisations.html"),
    "temoignage": ("Témoignage", "temoignage.html"),
    "cv": ("CV", "cv.html"),
}


class TourPerso(http.Controller):
    """Mes pages personnelles, dans le thème de la tour.

    Le menu « Moi » a quitté la vitrine publique (décision Patrick,
    10/08/2026). Ces pages sont servies ici, sous /tour/perso, à qui est
    connecté ET identifié comme propriétaire (comme les guides internes).
    Le contenu vient des pages de la vitrine, servies telles quelles avec
    leurs ressources en adresses complètes.
    """

    def _est_proprietaire(self):
        val = (request.env["ir.config_parameter"].sudo().get_param(
            "tour_owner.identifiants", "") or "")
        ids = {x.strip().lower() for x in val.split(",") if x.strip()}
        return (request.env.user.email or "").strip().lower() in ids

    def _contenu(self, page):
        import os
        chemin = os.path.join(VITRINE, PAGES[page][1])
        try:
            html = open(chemin, encoding="utf-8").read()
        except OSError:
            return "Page introuvable."
        html = html.replace('href="vitrine.css"',
                            'href="https://matourdecontrole.fr/vitrine.css"')
        html = html.replace('href="vitrine-theme.css"',
                            'href="https://matourdecontrole.fr/vitrine-theme.css"')
        html = html.replace('src="vitrine-lang.js?v=20260810"',
                            'src="https://matourdecontrole.fr/vitrine-lang.js?v=20260810"')
        html = html.replace('src="vitrine-theme.js"',
                            'src="https://matourdecontrole.fr/vitrine-theme.js"')
        fin_nav = html.find("</header>")
        debut_pied = html.rfind("<footer")
        if fin_nav != -1 and debut_pied != -1 and debut_pied > fin_nav:
            html = html[fin_nav + len("</header>"):debut_pied]
        return html

    @http.route("/tour/perso", type="http", auth="user", website=False)
    def index(self, **kw):
        if not self._est_proprietaire():
            return request.not_found()
        return request.render("tour_perso.page_perso", {"pages": PAGES})

    @http.route("/tour/perso/contenu/<page>", type="http", auth="user",
                website=False)
    def contenu(self, page=None, **kw):
        if not self._est_proprietaire():
            return request.not_found()
        if page not in PAGES:
            return request.not_found()
        return request.make_response(self._contenu(page))
