# -*- coding: utf-8 -*-
"""Le Jeu de la Tour â€” les pages et l'API.

MÃªme parti pris que la salle des dÃ©bats : des pages HTML rendues par le
serveur, robustes, sans OWL. L'API JSON est lÃ  pour la couche webapp : un
client pourra s'y brancher sans toucher aux pages.
"""

import json

from markupsafe import Markup

from odoo import http
from odoo.http import request

from odoo.addons.tour_jeu.models.tour_jeu import POIDS, ETAGES


def _jsonable(obj):
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(x) for x in obj]
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return obj


def _embarquer(donnee):
    """JSON sÃ»r Ã  embarquer dans une page : les < > sont Ã©chappÃ©s pour ne
    jamais casser le script, mÃªme si une donnÃ©e contient du HTML."""
    return Markup(json.dumps(_jsonable(donnee), ensure_ascii=False)
                  .replace("<", "\\u003c").replace(">", "\\u003e"))


class JeuTour(http.Controller):

    @http.route("/tour/jeu-de-la-tour", type="http", auth="user", website=False)
    def ma_tour(self, **kw):
        Jeu = request.env["jeu.tour"].sudo()
        tour = Jeu._calculer(request.env.user.id)
        return request.render("tour_jeu.page_ma_tour", {
            "tour": tour,
            "poids": POIDS,
        })

    @http.route("/tour/jeu-de-la-tour/tours", type="http", auth="user", website=False)
    def toutes_tours(self, **kw):
        Jeu = request.env["jeu.tour"].sudo()
        return request.render("tour_jeu.page_tours", {
            "tours": Jeu._toutes_tours(),
            "moi_id": request.env.user.id,
        })

    @http.route("/tour/jeu-de-la-tour-public", type="http", auth="public",
                website=False)
    def jeu_public(self, **kw):
        """Le royaume VU DE LA VITRINE : uniquement des métadonnées (niveaux,
        étages, paliers, vocation). Jamais de contenu interne — le jeu montre
        ce que la tour sait faire, jamais la clé de la porte."""
        Jeu = request.env["jeu.tour"].sudo()
        return request.render("tour_jeu.page_jeu_public", {
            "tours": Jeu._toutes_tours()[:12],
            "etages": ETAGES,
            "poids": POIDS,
        })

    @http.route("/tour/jeu-de-la-tour/royaume", type="http", auth="public",
                website=False)
    def jeu_2d(self, **kw):
        """Le Royaume en 2D — le jeu façon Pokémon (Génération 1/2) : carte en
        tuiles, avatar, rencontres, tours des autres en personnages. Zéro
        dépendance, canvas seul. Les données viennent de la vraie base par
        l'API publique (métadonnées uniquement)."""
        return request.render("tour_jeu.page_royaume_2d", {})

    @http.route("/tour/jeu-de-la-tour-public/api/royaume", type="json",
                auth="public", website=False)
    def api_royaume(self, **kw):
        """Les données du jeu 2D : les tours (métadonnées) +, si un interne est
        connecté, sa propre tour. Rien d'autre ne sort."""
        Jeu = request.env["jeu.tour"].sudo()
        tours = Jeu._toutes_tours()[:12]
        moi = None
        user = request.env.user
        if user.id and not user.share and user.login and "public" not in user.login:
            try:
                moi = Jeu._calculer(user.id)
            except Exception:  # noqa: BLE001
                moi = None
        return _jsonable({"moi": moi, "tours": tours})

    @http.route("/tour/jeu-de-la-tour/api/ma-tour", type="json", auth="user")
    def api_ma_tour(self, **kw):
        return _jsonable(request.env["jeu.tour"].sudo()
                         ._calculer(request.env.user.id))

    @http.route("/tour/jeu-de-la-tour/api/tours", type="json", auth="user")
    def api_tours(self, **kw):
        return _jsonable(request.env["jeu.tour"].sudo()._toutes_tours())

    @http.route("/tour/jeu-de-la-tour/regles", type="http", auth="user",
                website=False)
    def regles(self, **kw):
        """Les règles de chaque jeu, et l'idée d'où chacun vient."""
        return request.render("tour_jeu.page_regles", {})

    @http.route("/tour/jeu-de-la-tour/duel", type="http", auth="user",
                website=False)
    def duel(self, **kw):
        """Le Duel de la Tour — façon Yu-Gi-Oh : une table qui sépare les deux
        joueurs, et on attaque en jouant des cartes COMPÉTENCES dont la
        puissance est la valeur réelle mesurée dans la tour."""
        return request.render("tour_jeu.page_duel", {})

    @http.route("/tour/jeu-de-la-tour/api/duel", type="json", auth="user")
    def api_duel(self, **kw):
        """Les cartes du duel : tes cartes créées (jeu.carte) ou, à défaut, tes
        compétences réelles ; l'adversaire joue ses compétences réelles. Les
        avatars sont les vrais emblèmes de l'équipe."""
        env = request.env
        uid = env.user.id

        def cartes_competences(membre):
            out = []
            if "equipe.competence" in env and membre:
                Comp = env["equipe.competence"].sudo()
                for c in Comp.search([("membre_id", "=", membre.id)]):
                    xp = int(c.xp or 0)
                    if xp > 0:
                        out.append({
                            "name": (c.name or "Compétence")[:46],
                            "effet": "",
                            "attaque": max(1, min(10, int(round(xp ** 0.5)))),
                            "defense": max(0, min(10, int(round(xp ** 0.3)))),
                        })
                out.sort(key=lambda c: c["attaque"], reverse=True)
            return out

        # Des noms de jeu, jamais les libellés internes de la tour : une
        # carte d'arène ne doit rien raconter de ce qui se passe dedans.
        NOMS_DE_JEU = ["Griffe d'ombre", "Mur de ronces", "Éclat de givre",
                       "Souffle ardent", "Morsure vive", "Voile de brume",
                       "Pierre levée", "Trait sombre", "Aile de nuit",
                       "Poigne de fer"]

        def habiller(cartes):
            for i, c in enumerate(cartes):
                c["name"] = NOMS_DE_JEU[i % len(NOMS_DE_JEU)]
            return cartes

        def avatar(membre):
            embleme = (membre.embleme or "•") if membre else "?"
            couleur = {"Patrick": "#3b82f6", "Clark": "#f59e0b",
                       "Chloe": "#22c55e", "Braignak": "#a855f7",
                       "Raph": "#ef4444", "Victor": "#0ea5e9",
                       "Jimmy": "#f472b6", "Wags": "#f97316"}.get(
                           (membre.name if membre else ""), "#3b82f6")
            return {"nom": (membre.name if membre else "L'ombre"),
                    "embleme": embleme, "couleur": couleur}

        toi_m = adv_m = None
        if "equipe.membre" in env:
            Membres = env["equipe.membre"].sudo().search([("active", "=", True)])
            tri = Membres.sorted(key=lambda m: m.xp or 0, reverse=True)
            toi_m = next((m for m in tri if (m.name or "").lower() == "patrick"), None)
            if not toi_m and tri:
                toi_m = tri[0]
            adv_m = next((m for m in tri if m != toi_m), None)

        # Tes cartes : celles que tu as créées (jeu.carte), sinon tes compétences.
        toi_cartes = []
        if "jeu.carte" in env:
            toi_cartes = [{
                "name": c.name,
                "effet": c.effet or "",
                "attaque": min(10, c.attaque or 1),
                "defense": min(10, c.defense or 0),
            } for c in env["jeu.carte"].sudo().search(
                [("user_id", "=", uid), ("active", "=", True)],
                order="id desc")]
        if not toi_cartes:
            toi_cartes = habiller(cartes_competences(toi_m))
        adv_cartes = habiller(cartes_competences(adv_m))

        return _jsonable({
            "toi": dict(avatar(toi_m), cartes=toi_cartes) if toi_m else None,
            "adversaire": dict(avatar(adv_m), cartes=adv_cartes) if adv_m else None,
            "pt": 200,
        })

    @http.route("/tour/jeu-de-la-tour/cartes", type="http", auth="user",
                website=False, methods=["GET", "POST"])
    def cartes(self, **kw):
        """L'atelier de cartes : créer ses cartes (et ce qu'elles font) AVANT
        le combat. En POST, on crée une carte."""
        env = request.env
        if request.httprequest.method == "POST":
            nom = (kw.get("nom") or "").strip()
            if nom:
                env["jeu.carte"].sudo().create({
                    "name": nom[:60],
                    "effet": (kw.get("effet") or "").strip()[:300],
                    "attaque": max(1, min(10, int(kw.get("attaque") or 10))),
                    "defense": max(0, min(10, int(kw.get("defense") or 5))),
                    "user_id": env.user.id,
                })
            return request.redirect("/tour/jeu-de-la-tour/cartes")
        mes_cartes = env["jeu.carte"].sudo().search(
            [("user_id", "=", env.user.id), ("active", "=", True)],
            order="sequence, id")
        return request.render("tour_jeu.page_cartes", {
            "cartes": [{
                "id": c.id, "name": c.name, "effet": c.effet or "",
                "attaque": c.attaque, "defense": c.defense,
            } for c in mes_cartes],
        })

    @http.route("/tour/jeu-de-la-tour/cartes/<int:cid>/supprimer", type="http",
                auth="user", website=False, methods=["POST"])
    def carte_supprimer(self, cid, **kw):
        c = request.env["jeu.carte"].sudo().search(
            [("id", "=", cid), ("user_id", "=", request.env.user.id)])
        if c:
            c.write({"active": False})
        return request.redirect("/tour/jeu-de-la-tour/cartes")
