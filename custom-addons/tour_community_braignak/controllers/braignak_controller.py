# -*- coding: utf-8 -*-
"""Braignak Community — l'observateur libre. L'utilisateur donne une URL ou
une question, Braignak lit ce qui est public et répond : ce que fait cette
app, ce qui manque, ce qu'on peut en tirer. Version autonome (clé DeepSeek
configurable), sans l'atelier du cœur.

Moteurs : DeepSeek par défaut (paramètre tour_community_braignak.moteur =
« deepseek »). Mis à « gemini », Braignak passe par Gemini
(generativelanguage.googleapis.com, clé tour_community_braignak.gemini_key
ou tour_webmcp.gemini_key)."""
import json
import logging
import re
import urllib.parse

import requests

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

PARAM_CLE = "tour_community_braignak.api_key"
PARAM_CLE_GEMINI = "tour_community_braignak.gemini_key"
PARAM_MOTEUR = "tour_community_braignak.moteur"
PARAM_MODELE = "tour_community_braignak.modele"
CLE_GEMINI_PARTAGEE = "tour_webmcp.gemini_key"
MODELE_GEMINI = "gemini-3.6-flash"
BASE_GEMINI = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent"

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
        return self._observer(cible)

    def _observer(self, cible, env=None):
        """Observe une URL ou une question et répond. Route et WebMCP l'utilisent."""
        env = env or request.env
        cible = (cible or "").strip()
        if not cible:
            return {"erreur": "Donne-moi une adresse (URL) ou une question."}
        icp = env["ir.config_parameter"].sudo()
        moteur = (icp.get_param(PARAM_MOTEUR) or "").strip().lower()

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
        if moteur == "gemini":
            cle = (icp.get_param(PARAM_CLE_GEMINI)
                   or icp.get_param(CLE_GEMINI_PARTAGEE) or "").strip()
            if not cle:
                return {"erreur": (
                    "Le moteur est réglé sur Gemini mais aucune clé n'est "
                    "posée (paramètre %s ou %s)." % (PARAM_CLE_GEMINI,
                                                     CLE_GEMINI_PARTAGEE))}
            return self._gemini(cle, msgs, icp, env)

        cle = (icp.get_param(PARAM_CLE) or "").strip()
        if not cle:
            return {"erreur": (
                "La clé API n'est pas configurée (paramètre %s)." % PARAM_CLE)}
        return self._deepseek(cle, msgs, icp)

    def _deepseek(self, cle, msgs, icp):
        modele = icp.get_param(PARAM_MODELE) or "deepseek-chat"
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

    def _gemini(self, cle, msgs, icp, env=None):
        modele = icp.get_param(PARAM_MODELE) or MODELE_GEMINI
        systeme = next((m["content"] for m in msgs
                        if m.get("role") == "system"), SYSTEME)
        contenu = next((m["content"] for m in reversed(msgs)
                        if m.get("role") == "user"), "")
        payload = {
            "systemInstruction": {"parts": [{"text": systeme}]},
            "contents": [{"role": "user", "parts": [{"text": contenu}]}],
            "generationConfig": {"maxOutputTokens": 900},
        }
        url = BASE_GEMINI % urllib.parse.quote(modele) + "?key=" + urllib.parse.quote(cle)
        try:
            r = requests.post(url, headers={"Content-Type": "application/json"},
                              json=payload, timeout=120)
        except requests.RequestException:
            return {"erreur": "Impossible de joindre l'API Gemini — réseau du serveur."}
        if r.status_code == 401:
            return {"erreur": "Clé Gemini invalide ou expirée."}
        if r.status_code == 429:
            return {"erreur": "Limite de débit Gemini atteinte — réessaie dans un instant."}
        if r.status_code >= 400:
            _logger.warning("Braignak Community : Gemini %s : %s", r.status_code, r.text[:200])
            return {"erreur": "Erreur API Gemini (%s)." % r.status_code}
        data = r.json()
        candidats = data.get("candidates") or []
        if not candidats:
            retour = data.get("promptFeedback") or {}
            return {"erreur": "Gemini n'a pas répondu (%s)." % (
                retour.get("blockReason") or "réponse vide")}
        parts = ((candidats[0].get("content") or {}).get("parts") or [])
        reply = " ".join(p.get("text", "") for p in parts
                         if "text" in p and not p.get("thought")).strip()
        return {"reponse": reply or "(réponse vide)"}