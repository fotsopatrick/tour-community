# -*- coding: utf-8 -*-
"""La cagnotte : ce que Stripe a encaissé, sur la page d'accueil.

Une règle, et elle explique tout le reste : **l'accueil n'appelle jamais
Stripe**. Il lit le dernier relevé enregistré. Un appel réseau au chargement
d'une page, c'est une page qui devient lente quand le fournisseur rame et
blanche quand il tombe — pour un chiffre qu'on regarde en passant.

Le relevé, lui, tourne tout seul toutes les 4 heures. S'il échoue, l'accueil
affiche simplement le dernier chiffre connu avec sa date : « 340 € au
26/07 à 18h » est une information honnête, « erreur » n'en est pas une.

La clé est lue dans le Coffre au moment de servir, jamais stockée ici.
"""
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from datetime import timedelta

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

# Le libelle exact de la fiche du Coffre. Surtout PAS « mot de passe stripe » :
# cette fiche-la contient le mot de passe de connexion au tableau de bord, que
# Stripe rejette en 401. Un mot de passe et une cle d API ne sont pas la meme
# chose, et les confondre coute une soiree de diagnostic.
CLE_COFFRE = "stripe-secret-key"


class StripeReleve(models.Model):
    _name = "stripe.releve"
    _description = "Relevé Stripe"
    _order = "create_date desc"

    devise = fields.Char("Devise", default="EUR")
    disponible = fields.Float("Disponible", help="Ce que Stripe peut virer maintenant.")
    en_attente = fields.Float("En attente", help="Encaissé, pas encore disponible.")
    mois = fields.Float("Encaissé ce mois-ci")
    nb_paiements = fields.Integer("Paiements ce mois-ci")
    mode_test = fields.Boolean("Mode test",
                               help="Vrai si la clé est une clé de test : les montants ne sont pas réels.")
    erreur = fields.Char("Dernière erreur", readonly=True)

    # ------------------------------------------------------------------
    @api.model
    def _appel_stripe(self, cle, chemin, params=None):
        url = "https://api.stripe.com/v1/%s" % chemin
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url)
        req.add_header("Authorization", "Bearer %s" % cle)
        # Même piège que pour Supabase : un client qui ne se présente pas se
        # fait parfois refuser par les protections en amont de l'API.
        req.add_header("User-Agent", "tour-de-controle/1.0 (+https://matourdecontrole.fr)")
        try:
            with urllib.request.urlopen(req, timeout=25) as rep:
                return json.loads(rep.read().decode())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:200]
            raise UserWarning(_("Stripe a répondu %s : %s") % (exc.code, detail)) from exc

    @api.model
    def _cron_relever(self):
        """Toutes les 4 heures. Ne lève jamais : un cron qui plante s'éteint."""
        cle = self.env["vault.secret"]._lire(CLE_COFFRE, motif=_("le relevé Stripe"))
        if not cle:
            # UN CRON QUI NE TROUVE PAS SA CLE DOIT CRIER, PAS CHUCHOTER.
            #
            # Le 28/07, ce secret a ete RENOMME au Coffre pour le marquer
            # perime. La lecture se fait sur le nom EXACT : elle n a plus rien
            # trouve. Le cron a continue de tourner toutes les 4 heures,
            # rendant sagement None, et le releve s est arrete pendant SEPT
            # JOURS sans qu une seule alerte parte. Un `_logger.info` dans un
            # fichier que personne ne lit, c est du silence.
            #
            # Desormais : un releve en erreur est ECRIT en base (il apparait
            # donc sur l accueil), et le signal reveille quelqu un.
            _logger.warning(
                "Cagnotte : cle « %s » absente du Coffre — releve impossible.",
                CLE_COFFRE)
            self.sudo().create({
                "erreur": "Clé « %s » absente du Coffre. Le relevé ne peut pas "
                          "se faire. Ne pas renommer cette fiche : la lecture "
                          "se fait sur le nom exact." % CLE_COFFRE,
                "mode_test": False,
            })
            if "tour.signal" in self.env:
                try:
                    self.env["tour.signal"]._signaler(
                        agent="La cagnotte",
                        titre="Relevé Stripe impossible : clé absente du Coffre",
                        corps_html=(
                            "<p>Le relevé Stripe cherche le secret "
                            "<b>%s</b> au Coffre, par son nom exact.</p>"
                            "<p>Il ne l'y trouve pas. Le relevé est à l'arrêt "
                            "tant que ce n'est pas corrigé — et sans ce "
                            "message, l'arrêt serait invisible.</p>"
                            % CLE_COFFRE),
                        ton="echec")
                except Exception:  # noqa: BLE001
                    _logger.exception("Cagnotte : signal impossible")
            return

        vals = {"mode_test": cle.startswith("sk_test_"), "erreur": False}
        try:
            solde = self._appel_stripe(cle, "balance")
            def somme(bloc):
                # Stripe rend les montants en centimes, et une liste par
                # devise. On ne garde que l'euro : melanger des devises dans
                # un total donnerait un chiffre qui ne veut rien dire.
                return sum(x["amount"] for x in (solde.get(bloc) or [])
                           if x.get("currency") == "eur") / 100.0
            vals["disponible"] = somme("available")
            vals["en_attente"] = somme("pending")

            debut = fields.Date.context_today(self).replace(day=1)
            horodatage = int(fields.Datetime.to_datetime(debut).timestamp())
            total, nb, page, curseur = 0.0, 0, 0, None
            # On pagine, mais pas indefiniment : un compteur d'accueil ne
            # justifie pas de parcourir dix mille lignes a chaque relevé.
            while page < 5:
                params = {"limit": 100, "created[gte]": horodatage, "type": "charge"}
                if curseur:
                    params["starting_after"] = curseur
                lot = self._appel_stripe(cle, "balance_transactions", params)
                donnees = lot.get("data") or []
                for t in donnees:
                    if t.get("currency") == "eur":
                        total += t.get("net", 0) / 100.0
                        nb += 1
                if not lot.get("has_more") or not donnees:
                    break
                curseur = donnees[-1]["id"]
                page += 1
            vals["mois"] = total
            vals["nb_paiements"] = nb
        except Exception as exc:  # noqa: BLE001 — le cron doit survivre
            _logger.warning("Cagnotte : releve impossible (%s)", exc)
            vals["erreur"] = str(exc)[:200]

        self.create(vals)
        # On garde un mois d'historique : de quoi tracer une courbe plus tard
        # sans laisser la table grossir sans fin.
        vieux = self.search([("create_date", "<", fields.Datetime.now() - timedelta(days=31))])
        vieux.unlink()

    @api.model
    def dernier(self):
        """Le dernier relevé RÉUSSI, ou False. Jamais un relevé en erreur.

        Sans ce filtre, une panne de Stripe remplacerait un chiffre juste par
        un zéro — et un zéro sur une page d'accueil se lit comme « tu n'as
        rien gagné », pas comme « je n'ai pas pu demander ».
        """
        return self.search([("erreur", "=", False)], limit=1) or False
