# -*- coding: utf-8 -*-
"""Limite de tentatives de connexion par IP (429).

Le build Odoo 18.0 ne limite pas les essais de connexion : un script peut
essayer sans fin. La reponse doit etre un vrai 429 (HTTP) pour qu'une sonde
voie qu'une limite existe — fail2ban, lui, bannit au pare-feu sans code.

On bloque AVANT le controle CSRF : une attaque par force brute n'envoie pas
de jeton CSRF, et sans cette position la limite ne verrait jamais rien
(Odoo repond 400 avant d'atteindre l'authentification).
"""

import logging
from datetime import timedelta

import werkzeug.exceptions

from odoo import SUPERUSER_ID, api, fields, models
from odoo.http import HttpDispatcher

_logger = logging.getLogger(__name__)

MAX_TENTATIVES = 6
FENETRE_MINUTES = 10


class TourRateLoginAttempt(models.Model):
    _name = "tour.rate.login.attempt"
    _description = "Tentative de connexion (limite anti force brute)"
    _order = "create_date desc"

    ip = fields.Char("IP", index=True, required=True)

    @api.model
    def _purger_anciennes(self):
        self.search([
            ("create_date", "<",
             fields.Datetime.now() - timedelta(days=1)),
        ]).unlink()
        return True


def _dispatch_rate_limit(self, endpoint, args):
    req = self.request
    httprequest = req.httprequest
    if (
        httprequest.method == "POST"
        and httprequest.path == "/web/login"
        and req.db
    ):
        ip = httprequest.environ.get("REMOTE_ADDR") or "?"
        try:
            # TRANSACTION SEPAREE : le compteur doit survivre a l'erreur CSRF
            # qui annule la transaction de la requete. On ecrit et on commite
            # sur un curseur a part, puis on rejoint le flux normal.
            with req.registry.cursor() as cr:
                Env = api.Environment(cr, SUPERUSER_ID, {})
                Modele = Env["tour.rate.login.attempt"]
                debut = fields.Datetime.now() - timedelta(
                    minutes=FENETRE_MINUTES)
                n = Modele.search_count(
                    [("ip", "=", ip), ("create_date", ">=", debut)])
                if n >= MAX_TENTATIVES - 1:
                    _logger.warning(
                        "429 : %s+ tentatives de connexion depuis %s "
                        "en %s min", n + 1, ip, FENETRE_MINUTES)
                    raise werkzeug.exceptions.TooManyRequests(
                        "Trop de tentatives de connexion. Attendez "
                        "%s minutes." % FENETRE_MINUTES)
                Modele.create({"ip": ip})
                cr.commit()
        except werkzeug.exceptions.TooManyRequests:
            raise
        except Exception:
            # La limite ne doit JAMAIS casser le login lui-meme : si le
            # comptage echoue, la requete passe comme avant.
            _logger.exception("limite de connexion indisponible")
    return _orig_dispatch(self, endpoint, args)


_orig_dispatch = HttpDispatcher.dispatch
HttpDispatcher.dispatch = _dispatch_rate_limit
