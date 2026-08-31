# -*- coding: utf-8 -*-
"""Endpoint de la skill Alexa custom.

Alexa POSTe du JSON brut (pas du JSON-RPC) sur une URL HTTPS publique :
    https://ton-domaine/tour_alexa/skill?token=LE_JETON

Sécurité : jeton secret obligatoire dans l'URL + filtre optionnel sur
l'applicationId de la skill. Les requêtes s'exécutent au nom de l'admin
(usage personnel — voir README-ALEXA.md avant d'ouvrir à d'autres).
"""
import json
import logging
import re

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

MAX_VOIX = 600  # Alexa lit mal les pavés : on tronque proprement


def _reponse_alexa(texte, fin_de_session=False):
    corps = {
        "version": "1.0",
        "response": {
            "outputSpeech": {"type": "PlainText", "text": texte},
            "shouldEndSession": fin_de_session,
        },
    }
    return request.make_response(
        json.dumps(corps), headers=[("Content-Type", "application/json")]
    )


def _pour_la_voix(texte):
    """Nettoie une réponse écrite pour qu'Alexa la lise naturellement."""
    texte = re.sub(r"[*_#`>|]", "", texte)
    texte = re.sub(r"https?://\S+", "", texte)
    texte = re.sub(r"\s+", " ", texte).strip()
    if len(texte) > MAX_VOIX:
        texte = texte[:MAX_VOIX].rsplit(" ", 1)[0] + "…"
    return texte or "Je n'ai pas de réponse."


class TourAlexa(http.Controller):

    @http.route("/tour_alexa/skill", type="http", auth="public",
                methods=["POST"], csrf=False, save_session=False)
    def skill(self, token=None, **kwargs):
        icp = request.env["ir.config_parameter"].sudo()
        attendu = (icp.get_param("tour_alexa.token") or "").strip()
        if not attendu or token != attendu:
            return request.make_response("forbidden", status=403)

        try:
            corps = json.loads(request.httprequest.get_data(as_text=True) or "{}")
        except ValueError:
            return request.make_response("bad request", status=400)

        skill_id = (icp.get_param("tour_alexa.skill_id") or "").strip()
        recu = (((corps.get("context") or {}).get("System") or {})
                .get("application") or {}).get("applicationId", "")
        if skill_id and recu != skill_id:
            return request.make_response("forbidden", status=403)

        type_req = (corps.get("request") or {}).get("type", "")

        if type_req == "LaunchRequest":
            return _reponse_alexa(
                "La tour de contrôle t'écoute. Demande-moi par exemple : "
                "où en est Duelle, ou : note que je dois rappeler Imane."
            )

        if type_req == "SessionEndedRequest":
            return _reponse_alexa("À bientôt.", fin_de_session=True)

        if type_req == "IntentRequest":
            intent = (corps["request"].get("intent") or {})
            nom = intent.get("name", "")
            if nom in ("AMAZON.StopIntent", "AMAZON.CancelIntent"):
                return _reponse_alexa("À bientôt.", fin_de_session=True)
            if nom == "AMAZON.HelpIntent":
                return _reponse_alexa(
                    "Je suis le copilote de la tour. Pose une question sur "
                    "tes apps, tes offres ou tes tâches, ou dicte une note."
                )

            question = ((intent.get("slots") or {}).get("question") or {}).get("value", "")
            if not question:
                return _reponse_alexa("Je n'ai pas compris. Reformule ta demande.")

            # Le copilote agit au nom de l'admin (skill personnelle).
            from odoo.addons.tour_copilote.controllers.main import executer_chat
            env = request.env(user=request.env.ref("base.user_admin").id)
            resultat = executer_chat(env, [{"role": "user", "content": question}])
            if resultat.get("error"):
                _logger.warning("Alexa : %s", resultat["error"])
                return _reponse_alexa(
                    "Le copilote a un souci : " + _pour_la_voix(resultat["error"])
                )
            return _reponse_alexa(_pour_la_voix(resultat["reply"]))

        return _reponse_alexa("Je n'ai pas compris la demande.")
