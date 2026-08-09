# -*- coding: utf-8 -*-
"""Accueil de l'édition Community : Bonjour + prénom, accès à Chloé et
Braignak, les briques installées, et le fil d'actualités. Après connexion,
l'utilisateur atterrit ici au lieu du backend Odoo générique."""
from odoo import http
from odoo.http import request
from odoo.addons.web.controllers.utils import is_user_internal
from odoo.addons.web.controllers.home import Home


class CommunityAccueil(http.Controller):

    @http.route("/community", type="http", auth="user", website=False)
    def accueil(self, **kw):
        modules = request.env["ir.module.module"].sudo().search(
            [("state", "=", "installed"), ("name", "like", "tour%")],
            order="name")
        tuiles = []
        pour = {
            "tour_actus": ("Actus", "Le fil d'actualités", "/community"),
            "tour_apprentissage": ("Apprentissage", "Des leçons par thème", "/web"),
            "tour_condense_community": ("Condensation", "Résumer un texte", "/web"),
            "tour_cookie_secure": ("Cookie sécurisé", "Session HTTPS", "/web"),
            "tour_cv": ("Mon CV", "Un CV en page web", "/web"),
            "tour_messages": ("Messages", "Des messages à copier", "/web"),
            "tour_nouveautes": ("Quoi de neuf", "Les nouveautés", "/web"),
            "tour_projets": ("Projets", "Un kanban", "/web"),
            "tour_rappels": ("Rappels", "Des rappels récurrents", "/web"),
            "tour_rate_login": ("Anti-bruteforce", "Limite le login", "/web"),
            "tour_recette": ("Recette", "Tester les sites", "/web"),
            "tour_reponses": ("Réponses", "Les réponses gardées", "/web"),
            "tour_retours": ("Retours", "Déposer un bug", "/web"),
            "tour_sauvegardes": ("Sauvegardes", "Voir les sauvegardes", "/web"),
            "tour_webapps": ("Webapps", "Les pages web", "/web"),
        }
        for m in modules:
            if m.name in pour:
                nom, desc, lien = pour[m.name]
                tuiles.append({"nom": nom, "desc": desc, "module": m.name,
                               "lien": lien})

        # Le fil d'actualités (tour_actus) si présent
        actus = []
        if "actus.article" in request.env:
            articles = request.env["actus.article"].sudo().search(
                [], order="date_pub desc", limit=6)
            for a in articles:
                actus.append({"titre": a.name, "date": str(a.date_pub or "")[:10],
                              "lien": a.lien or ""})

        return request.render("tour_community_theme.page_accueil", {
            "prenom": (request.env.user.name or "").split(" ")[0],
            "tuiles": tuiles,
            "actus": actus,
        })


class LoginCommunity(Home):
    """Après connexion, atterrir sur l'accueil de la tour (le dashboard,
    comme la démo), pas dans le backend Odoo générique."""

    def _login_redirect(self, uid, redirect=None):
        if not redirect and is_user_internal(uid):
            redirect = "/tour/dashboard"
        return super()._login_redirect(uid, redirect=redirect)
