# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
"""La tour en cartes par zones (06/08, Patrick).

Patrick : « il nous faudrait plusieurs cartes comme celle de packet tracer ».
Six zones, chacune sa carte, dans le langage du cockpit.

La donnée est RELEVÉE sur l'hôte par `deploy/carte-zones.sh` et posée dans
l'atelier (monté dans le conteneur). Le contrôleur lit le fichier : il ne
relève rien lui-même. Si le fichier n'existe pas ou est illisible, la page
le dit clairement — jamais un relevé faux présenté comme vrai.

Même verrou que le reste du cockpit : base.group_system.
"""
import json
import os

from markupsafe import Markup

from odoo import http
from odoo.http import request

JSON_PATH = "/mnt/atelier/cartes.json"


class TourCartes(http.Controller):

    @http.route("/tour/cockpit/cartes", type="http", auth="user",
                website=False, csrf=False)
    def cartes(self, **kw):
        env = request.env
        if not env.user.has_group("base.group_system"):
            return request.redirect("/tour/dashboard")

        donnees = None
        erreur = ""
        try:
            if os.path.exists(JSON_PATH):
                with open(JSON_PATH, "r", encoding="utf-8") as f:
                    brut = f.read()
                donnees = json.loads(brut)
        except Exception as e:  # noqa: BLE001 — on montre l'erreur, pas un blanc
            erreur = str(e)

        zones = (donnees or {}).get("zones") or []
        releve = (donnees or {}).get("releve_le") or ""
        # Markup : t-out NE doit PAS re-echapper le JSON. Passe en str simple,
        # les guillemets sortent en &#34; et, dans un <script>, le navigateur
        # ne decode pas les entites : JSON.parse echoue et la carte reste vide.
        # (meme patron que circuits.py avec board_json.)
        json_donnees = Markup(brut) if donnees is not None else Markup("")
        return request.render("tour_cartes.page_cartes", {
            "json_donnees": json_donnees,
            "releve_le": releve,
            "nb_zones": len(zones),
            "nb_noeuds": sum(len(z.get("noeuds") or []) for z in zones),
            "nb_liens": sum(len(z.get("liens") or []) for z in zones),
            "erreur": erreur,
            "chemin": JSON_PATH,
        })
