# -*- coding: utf-8 -*-
"""Braignak Community — l'observateur libre. L'utilisateur donne une URL ou
une question, Braignak lit ce qui est public et répond : ce que fait cette
app, ce qui manque, ce qu'on peut en tirer. Version autonome (clé DeepSeek
configurable), sans l'atelier du cœur."""
import json
import logging
import re

import requests

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

PARAM_CLE = "tour_community_braignak.api_key"
PARAM_MODELE = "tour_community_braignak.modele"

SYSTEME = (
    "Tu es Braignak, l'observateur de l'édition Community de la Tour de "
    "contrôle. Ton métier : regarder une application, un site ou une idée, "
    "et dire ce qu'elle fait, ce qui manque, ce qu'on peut en tirer. Tu "
    "réponds en français, simplement, niveau enfant de six ans si possible. "
    "Tu ne fais que constater ce qu'on te donne — tu n'inventes rien, tu ne "
    "prétends pas avoir lu ce que tu n'as pas vu."
)

_EXTRAIRE = re.compile(r"<[^>]+>")


def _texte_page(url):
    """Récupère le texte lisible d'une page (best effort)."""
    try:
        r = requests.get(url, timeout=25,
                         headers={"User-Agent": "Braignak-Community/1.0"})
        if r.status_code != 200:
            return None, "La page répond %s." % r.status_code
        html = r.text[:40000]
        corps = _EXTRAIRE.sub(" ", html)
        corps = re.sub(r"\s+", " ", corps).strip()
        return corps[:6000], None
    except Exception as exc:  # noqa: BLE001
        return None, "Impossible de lire la page : %s" % str(exc)[:100]


class BraignakCommunity(http.Controller):

    @http.route("/community/braignak", type="http", auth="user", website=False)
    def page(self, **kw):
        return request.render("tour_community_braignak.page_braignak", {
            "prenom": (request.env.user.name or "").split(" ")[0],
        })

    @http.route("/community/braignak/observer", type="json", auth="user")
    def observer(self, cible):
        cible = (cible or "").strip()
        if not cible:
            return {"erreur": "Donne-moi une adresse (URL) ou une question."}
        icp = request.env["ir.config_parameter"].sudo()
        cle = (icp.get_param(PARAM_CLE) or "").strip()
        if not cle:
            return {"erreur": (
                "La clé API n'est pas configurée (paramètre %s)." % PARAM_CLE)}
        modele = icp.get_param(PARAM_MODELE) or "deepseek-chat"

        # Si c'est une URL, on essaie de lire la page.
        contexte = cible
        if cible.startswith("http://") or cible.startswith("https://"):
            texte, err = _texte_page(cible)
            if err:
                return {"erreur": err}
            contexte = ("Page lue à %s :\n%s" % (cible, texte))

        msgs = [{"role": "system", "content": SYSTEME},
                {"role": "user",
                 "content": ("Observe ceci et dis ce que ça fait, ce qui "
                             "manque, ce qu'on peut en tirer.\n\n%s" % contexte)}]
        try:
            r = requests.post(
                "https://api.deepseek.com/chat/completions",
                headers={"Authorization": "Bearer %s" % cle},
                json={"model": modele, "messages": msgs, "max_tokens": 900},
                timeout=120)
        except requests.RequestException:
            return {"erreur": "Impossible de joindre l'API — réseau du serveur."}
        if r.status_code == 401:
            return {"erreur": "Clé DeepSeek invalide ou expirée — vérifie %s." % PARAM_CLE}
        if r.status_code == 429:
            return {"erreur": "Limite de débit DeepSeek atteinte — réessaie dans un instant."}
        if r.status_code >= 400:
            _logger.warning("Braignak Community : API %s : %s", r.status_code, r.text[:200])
            return {"erreur": "Erreur API DeepSeek (%s)." % r.status_code}
        data = r.json()
        reply = ((data.get("choices") or [{}])[0]
                 .get("message", {}).get("content") or "").strip()
        return {"reponse": reply or "(réponse vide)"}
