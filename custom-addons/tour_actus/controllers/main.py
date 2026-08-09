# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class TourActusController(http.Controller):

    @http.route("/tour_actus/langue", type="http", auth="user", website=False)
    def langue(self, choix="toutes", suite="/", **kw):
        """Enregistre la langue d'actus choisie, puis revient d'où on vient.

        Un choix de préférence n'est pas une action risquée : une simple
        redirection suffit, pas de formulaire. Valeur inconnue → « toutes »,
        jamais une erreur.
        """
        if choix not in ("toutes", "fr", "en", "es"):
            choix = "toutes"
        request.env.user.actus_langue = choix
        if not suite.startswith("/") or suite.startswith("//"):
            suite = "/"  # jamais de redirection hors de la tour
        return request.redirect(suite)

    def _domaine_langue(self):
        pref = request.env.user.actus_langue
        return [("langue", "=", pref)] if pref and pref != "toutes" else []

    @http.route("/tour_actus/fil", type="json", auth="user")
    def fil(self):
        """Le fil groupé par centre d'intérêt, prêt à afficher."""
        articles = request.env["actus.article"].search(
            [("flux_id.actif", "=", True)] + self._domaine_langue(),
            limit=200)
        categories = {}
        for art in articles:
            categories.setdefault(art.categorie, []).append({
                "id": art.id,
                "titre": art.name,
                "lien": art.lien,
                "resume": art.resume or "",
                "image": art.image_url or "",
                "source": art.flux_id.name,
                "date": art.date_pub and art.date_pub.isoformat() or "",
            })
        return {
            "categories": [
                {"nom": nom, "articles": arts}
                for nom, arts in sorted(categories.items())
            ],
        }

    @http.route("/tour_actus/rafraichir", type="json", auth="user")
    def rafraichir(self):
        request.env["actus.flux"].search([("actif", "=", True)]).action_rafraichir()
        return self.fil()
