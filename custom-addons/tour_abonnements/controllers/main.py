# -*- coding: utf-8 -*-
"""Le webhook Stripe, et la page de remerciement.

Le webhook doit être public — Stripe appelle depuis ses serveurs, sans
session. Ce qui le protège n'est donc pas l'authentification mais la
**signature** : sans elle, n'importe qui poste « paiement reçu » et obtient un
contrat actif, donc une instance livrée, sans qu'un euro soit entré.

Deux détails qui n'en sont pas :

- On répond **200 même quand on ne sait pas traiter** l'événement. Stripe
  réessaie pendant trois jours sur toute réponse d'erreur ; un événement qu'on
  ignore volontairement provoquerait des milliers de tentatives et finirait par
  faire désactiver le webhook — y compris pour les événements qui comptent.
- On répond **400 quand la signature est mauvaise**, et rien d'autre. Ne jamais
  dire *pourquoi* : ce serait indiquer à celui qui cherche s'il approche.
"""
import json
import logging

from odoo import fields, http
from odoo.http import request

_logger = logging.getLogger(__name__)

MERCI = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Merci — Tour de contrôle</title>
<style>
 body{margin:0;background:#020817;color:#e2e8f0;min-height:100vh;display:flex;
      align-items:center;justify-content:center;padding:1.5rem;
      font-family:system-ui,-apple-system,"Segoe UI",sans-serif}
 .c{max-width:28rem;text-align:center}
 .p{width:3.5rem;height:3.5rem;border-radius:50%;background:#22c55e;color:#04140a;
    margin:0 auto 1.25rem;display:flex;align-items:center;justify-content:center;
    font-size:1.7rem}
 h1{font-size:1.6rem;margin:0 0 .75rem}
 p{color:#94a3b8;line-height:1.6;margin:0 0 .6rem}
 a{color:#3b82f6}
</style></head><body><div class="c">
<div class="p">&#10003;</div>
<h1>C'est bon, merci</h1>
<p>Votre paiement est enregistr&eacute;. Vous recevez un re&ccedil;u de Stripe
par courriel dans la minute.</p>
<p>Votre instance est en cours de pr&eacute;paration. Vous recevrez son adresse
et vos acc&egrave;s &agrave; la m&ecirc;me adresse courriel.</p>
<p style="font-size:.85rem;color:#64748b;border-top:1px solid #1e293b;
padding-top:1rem;margin-top:1.5rem">
R&eacute;siliable &agrave; tout moment : un mot &agrave; votre assistante ou un courriel, et c'est fait sous 24 h ouvr&eacute;es.
Le mois entam&eacute; reste d&ucirc;.</p>
<p><a href="https://matourdecontrole.fr">Retour au site</a></p>
</div></body></html>"""


class TourAbonnements(http.Controller):

    @http.route("/abonnement/merci", type="http", auth="public", website=False)
    def merci(self, **kw):
        return request.make_response(
            MERCI, headers=[("Content-Type", "text/html; charset=utf-8")])


    @http.route("/instances/autorise", type="http", auth="public", csrf=False)
    def autorise(self, domain=None, **kw):
        """Caddy demande ici s'il a le droit d'obtenir un certificat.

        Sans ce garde-fou, n'importe qui pointant son domaine vers cette IP
        ferait demander un certificat en notre nom — et Let's Encrypt finirait
        par nous limiter, ce qui bloquerait aussi les vrais clients.

        On repond 200 uniquement pour un sous-domaine dont l'instance existe,
        et 404 pour tout le reste. On ne dit jamais pourquoi.
        """
        if not domain:
            return request.make_response("", status=404)
        hote = domain.split(":")[0].strip().lower()
        connu = request.env["abonnement.contrat"].sudo().search_count(
            [("instance_url", "ilike", "//%s" % hote)])
        if not connu:
            # Une demande en cours compte aussi : le certificat est demande a
            # la premiere visite, qui precede l'ecriture de l'adresse.
            #
            # On lit le CONTENU des demandes, pas leur nom. Le fichier
            # s'appelle « ABO-2026-0003.json » — le nom technique de
            # l'instance est DEDANS. Chercher dans le nom de fichier ne
            # trouvait jamais rien : Caddy refusait le certificat, et le
            # montage echouait a la derniere etape apres avoir tout reussi.
            # Trouve au premier vrai paiement, le 27/07.
            import json
            import os
            dossier = "/mnt/atelier/instances"
            slug = hote.split(".")[0]
            if os.path.isdir(dossier):
                for f in os.listdir(dossier):
                    if not f.endswith(".json"):
                        continue
                    try:
                        with open(os.path.join(dossier, f)) as fh:
                            if json.load(fh).get("slug") == slug:
                                connu = True
                                break
                    except Exception:
                        continue
        return request.make_response("", status=200 if connu else 404)

    @http.route("/zone-detresse/code/<code>", type="http", auth="public",
                csrf=False)
    def zone_detresse_code(self, code=None, **kw):
        """La balise SOS demande ici si un code d'acces est valide et actif.

        Adresse publique (appelee par la balise, sans session). La seule
        question posee est binaire : ce code donne-t-il le droit d'envoyer une
        position ? 200 si oui, 404 sinon. On ne dit jamais pourquoi : un code
        qui n'existe pas et un contrat resilie repondent pareil, un explorateur
        n'apprend rien.
        """
        if not code:
            return request.make_response("", status=404)
        Contrat = request.env["abonnement.contrat"].sudo()
        c = Contrat.search([("zone_detresse_code", "=", code.strip())], limit=1)
        ok = bool(c and c.etat == "actif")
        if ok and c.date_expiration:
            ok = c.date_expiration >= fields.Date.context_today(c)
        return request.make_response("", status=200 if ok else 404)

    @http.route("/abonnement/stripe", type="http", auth="public",
                methods=["POST"], csrf=False)
    def webhook(self, **kw):
        corps = request.httprequest.get_data(as_text=True)
        entete = request.httprequest.headers.get("Stripe-Signature", "")

        Webhook = request.env["abonnement.webhook"].sudo()
        ok, pourquoi = Webhook.verifier_signature(corps, entete)
        if not ok:
            _logger.warning("Webhook Stripe rejete : %s", pourquoi)
            return request.make_response("", status=400)

        try:
            evenement = json.loads(corps)
        except ValueError:
            return request.make_response("", status=400)

        try:
            resultat = Webhook.traiter(evenement)
            request.env.cr.commit()
            _logger.info("Webhook Stripe %s -> %s", evenement.get("type"), resultat)
        except Exception:
            # On journalise et on rend 200 quand meme. Rendre une erreur ferait
            # rejouer l'evenement toutes les heures pendant trois jours, et si
            # le bug est chez nous il se rejouera a l'identique. Mieux vaut un
            # evenement perdu et trace qu'une tempete qui fait desactiver le
            # webhook pour de bon.
            _logger.exception("Webhook Stripe : traitement impossible")

        return request.make_response("", status=200)
