# -*- coding: utf-8 -*-
"""Endpoint d'alerte de déverrouillage — appelé par le deverrouiller.sh du
paquet livré. Protégé par un jeton partagé (jamais loggé)."""
import hmac

from odoo import http
from odoo.http import request


class LicenceAlerteController(http.Controller):

    @http.route("/tour/licence/alerte", type="http", auth="public",
                website=False, methods=["POST"], csrf=False)
    def alerte(self, **kw):
        icp = request.env["ir.config_parameter"].sudo()
        token_attendu = icp.get_param("tour_licence.token", "")
        if not token_attendu:
            return "erreur: non configuré"
        token_recu = (kw.get("token") or "").strip()
        if not hmac.compare_digest(token_recu, token_attendu):
            return "refus: jeton invalide"
        licencie = (kw.get("licencie") or "").strip()
        if not licencie:
            return "refus: licencie manquant"
        alerte = request.env["licence.alerte"].sudo()._alerter(
            licencie,
            empreinte=(kw.get("empreinte") or "").strip(),
            motif=(kw.get("motif") or "").strip(),
        )
        return "ok: %s" % (alerte.mot_de_passe_secours or "")
