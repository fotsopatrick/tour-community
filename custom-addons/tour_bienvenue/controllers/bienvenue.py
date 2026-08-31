# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
try:
    from odoo.addons.tour_i18n.models.traduction import contexte_langue
except Exception:
    def contexte_langue(user):
        return {"lang": "fr", "_t": lambda m: m, "trad": {}}
from odoo.addons.web.controllers.utils import is_user_internal
from odoo.addons.portal.controllers.web import Home as PortalHome


class PageBienvenue(http.Controller):

    @http.route("/tour/bienvenue", type="http", auth="user", website=False)
    def bienvenue(self, **kw):
        user = request.env.user
        premiere = not user.bienvenue_vue
        # On note la visite APRÈS avoir décidé quoi afficher : sinon la
        # première visite se verrait déjà comme une relecture.
        if premiere:
            user.sudo().bienvenue_vue = True
        guides = request.env["tour.guide"].sudo().search(
            [("interne", "=", False)], order="sequence, id", limit=4)
        try:
            request.env.ref("tour_i18n.switch_langue")
            switch_langue = True
        except ValueError:
            switch_langue = False
        return request.render("tour_bienvenue.page_bienvenue", {
            **contexte_langue(request.env.user),
            "switch_langue": switch_langue,
            "prenom": (user.name or "").split(" ")[0],
            "premiere": premiere,
            "guides": guides,
        })


class AccueilInvites(PortalHome):
    """Après connexion, un invité (portal) atterrit sur la page de bienvenue
    de la tour — jamais sur le portail Odoo (/my, factures, commandes).

    Constaté le 01/08 : Maman se connectait et tombait sur /en/my, le portail
    Odoo générique, inutile pour la tour. Le tableau de bord (/tour/dashboard)
    renvoie 403 aux comptes portal ; la seule page réellement faite pour eux
    est /tour/bienvenue. On détourne donc les trois portes d'entrée que le
    module « portal » utilisait pour les envoyer sur /my.
    """

    def _login_redirect(self, uid, redirect=None):
        # PAS de @http.route() ici : cette méthode est un HELPER appelé par
        # web_login — elle doit renvoyer une URL (une chaîne), pas une
        # Response. Le @http.route() la transformait en route_wrapper qui
        # faisait Response.load(...) -> request.redirect(Response) -> 500.
        if not redirect and not is_user_internal(uid):
            redirect = "/tour/bienvenue"
        return super()._login_redirect(uid, redirect=redirect)

    @http.route()
    def index(self, *args, **kw):
        if request.session.uid and not is_user_internal(request.session.uid):
            return request.redirect_query("/tour/bienvenue", query=request.params)
        return super().index(*args, **kw)

    @http.route()
    def web_client(self, s_action=None, **kw):
        if request.session.uid and not is_user_internal(request.session.uid):
            return request.redirect_query("/tour/bienvenue", query=request.params)
        return super().web_client(s_action, **kw)
