# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
"""Endpoint MCP Streamable HTTP de la Tour.

Point d'entrée : POST /mcp/tour
- Transport : Model Context Protocol « Streamable HTTP » (JSON-RPC 2.0).
- Méthodes : initialize, ping, notifications/initialized, tools/list,
  tools/call.
- Authentification : en-tête `Authorization: Bearer <tour_webmcp.api_key>`.
  Sans jetons paramétré, l'endpoint répond 503 : il est inerte par défaut.

Ce serveur est volontairement sans dépendance pip : le protocole est
implémenté nativement (JSON-RPC 2.0 + HTTP), tout passe par les modèles
Odoo. Les clients MCP standards (opencode, Claude, etc.) s'y connectent en
remote — voir le README.
"""

import datetime
import hmac
import json
import logging

from odoo import http
from odoo.http import request

from . import outils

_logger = logging.getLogger(__name__)

PARAM_API_KEY = "tour_webmcp.api_key"

VERSION_MCP = "2025-06-18"
VERSIONS_SUPPORTEES = ["2024-11-05", "2025-03-26", "2025-06-18"]
NOM_SERVEUR = "tour-webmcp"
VERSION_SERVEUR = "18.0.1.0.0"


def _negotiate_version(demandee):
    if demandee in VERSIONS_SUPPORTEES:
        return demandee
    if not demandee or demandee > VERSION_MCP:
        return VERSION_MCP
    return VERSIONS_SUPPORTEES[0]


class TourWebMCP(http.Controller):

    @http.route("/mcp/tour", type="http", auth="public", website=False,
                csrf=False, methods=["POST"], save_session=False)
    def mcp_post(self, **kw):
        req = request.httprequest
        cle = (request.env["ir.config_parameter"].sudo()
               .get_param(PARAM_API_KEY) or "").strip()
        if not cle:
            return self._http_erreur(
                503, "Endpoint MCP non configuré : posez %s "
                     "dans Réglages." % PARAM_API_KEY)
        auth = req.headers.get("Authorization") or ""
        attendu = "Bearer " + cle
        if not hmac.compare_digest(auth, attendu):
            return self._http_erreur(401, "Clé d'accès MCP manquante ou "
                                           "invalide (Authorization: Bearer).")

        try:
            corps = req.get_data(as_text=True)
            if not corps.strip():
                return self._http_erreur(400, "Corps vide.")
            message = json.loads(corps)
        except ValueError:
            return self._http_erreur(400, "JSON invalide.")
        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
            return self._http_erreur(400, "Message JSON-RPC 2.0 attendu.")

        id_req = message.get("id")
        if id_req is None:
            # Notification : on acquitte sans répondre.
            reponse = request.make_response(
                "", headers=[("Content-Type",
                              "application/json; charset=utf-8")])
            reponse.status = "202 Accepted"
            return reponse

        resultat = None
        erreur = None
        try:
            methode = message.get("method") or ""
            params = message.get("params") or {}
            if methode == "initialize":
                resultat = {
                    "protocolVersion": _negotiate_version(
                        params.get("protocolVersion")),
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": NOM_SERVEUR,
                                   "version": VERSION_SERVEUR},
                    "instructions": (
                        "La Tour de contrôle de l'édition Community. Les "
                        "outils exposent ses vraies briques : carte vivante, "
                        "agents (Chloé, Braignak), actus, projets, rappels, "
                        "circuits. Tout est scellé par la clé WebMCP."),
                }
            elif methode == "ping":
                resultat = {}
            elif methode == "notifications/initialized":
                resultat = {}
            elif methode == "tools/list":
                resultat = {"tools": outils.outils_liste(),
                            "listChanged": False}
            elif methode == "tools/call":
                nom = params.get("name") or ""
                arguments = params.get("arguments") or {}
                texte, est_erreur = outils.appeler_outil(
                    request.env(su=True), nom, arguments)
                resultat = {"content": [{"type": "text", "text": texte}],
                            "isError": est_erreur}
            else:
                erreur = {"code": -32601,
                          "message": "Méthode inconnue : %s" % methode}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("WebMCP : erreur interne")
            erreur = {"code": -32603,
                      "message": "Erreur interne : %s" % exc}

        enveloppe = {"jsonrpc": "2.0", "id": id_req}
        if erreur is not None:
            enveloppe["error"] = erreur
        else:
            enveloppe["result"] = resultat
        texte = json.dumps(enveloppe, ensure_ascii=False)

        reponse = request.make_response(
            texte,
            headers=[("Content-Type", "application/json; charset=utf-8"),
                     ("Cache-Control", "no-store"),
                     ("Access-Control-Allow-Origin", "*")])
        return reponse

    def _http_erreur(self, code, message, detail=None):
        corps = json.dumps({"jsonrpc": "2.0", "id": None,
                            "error": {"code": code, "message": message}},
                           ensure_ascii=False)
        reponse = request.make_response(
            corps,
            headers=[("Content-Type", "application/json; charset=utf-8"),
                     ("Access-Control-Allow-Origin", "*")])
        reponse.status = str(code)
        return reponse