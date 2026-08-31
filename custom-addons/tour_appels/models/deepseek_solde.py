# -*- coding: utf-8 -*-
"""Le solde DeepSeek RÉEL, relevé sur l'API — pour comparer ce qu'on ESTIME
avoir consommé (copilote + appels agents) avec ce qu'on a VRAIMENT consommé
(la chute du solde). Une estimation non confrontée au réel est un vœu pieux.
"""
import json
import logging
import urllib.request

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

URL_SOLDE = "https://api.deepseek.com/user/balance"


class DeepseekSolde(models.Model):
    _name = "deepseek.solde"
    _description = "Relevé du solde DeepSeek"
    _order = "releve_le desc"

    releve_le = fields.Datetime("Relevé le", default=fields.Datetime.now,
                                readonly=True, index=True)
    solde_usd = fields.Float("Solde (USD)", readonly=True, digits=(10, 2))
    note = fields.Char("Note", readonly=True)

    # ------------------------------------------------------------------
    @api.model
    def _relever(self):
        """Interroge l'API DeepSeek (balance) avec la clé du Coffre.

        La clé vit dans vault.secret « deepseek-api-key » (le paramètre
        tour_copilote.deepseek_key est vide — le copilote la lit aussi au
        Coffre). Source absente -> aucun enregistrement, jamais de chiffre
        inventé.
        """
        cle = ""
        if "vault.secret" in self.env:
            try:
                cle = (self.env["vault.secret"].sudo()._lire(
                    "deepseek-api-key", motif="relevé du solde") or "").strip()
            except Exception:  # noqa: BLE001
                cle = ""
        if not cle:
            _logger.warning("Solde DeepSeek : clé absente du Coffre.")
            return self.browse()
        try:
            req = urllib.request.Request(
                URL_SOLDE, headers={"Authorization": "Bearer " + cle,
                                    "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=20) as reponse:
                donnees = json.loads(reponse.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            _logger.warning("Solde DeepSeek : API injoignable (%s)", exc)
            return self.browse()
        total = 0.0
        for b in donnees.get("balance_infos", []):
            total += float(b.get("total_balance") or 0.0)
        return self.sudo().create({
            "solde_usd": round(total, 2), "note": "API DeepSeek"})

    # ------------------------------------------------------------------
    @api.model
    def _comparatif(self):
        """{solde_actuel, consomme_reel, consomme_estime, ecart, nb_releves}.

        Consommé RÉEL = chute du solde depuis le premier relevé.
        Consommé ESTIMÉ = copilote.usage + api.appel (tarifs internes).
        L'écart dit honnêtement si l'estimation ment.
        """
        releves = self.sudo().search([], order="releve_le asc")
        if len(releves) < 1:
            return False
        dernier = releves[-1]
        premier = releves[0]
        consomme_reel = round(max(0.0, premier.solde_usd - dernier.solde_usd), 2)
        estime = 0.0
        if "copilote.usage" in self.env:
            estime += sum(self.env["copilote.usage"].sudo()
                          .search([]).mapped("cout_estime") or [0])
        if "api.appel" in self.env:
            estime += sum(self.env["api.appel"].sudo()
                          .search([]).mapped("cout_estime") or [0])
        estime = round(estime, 2)
        return {
            "solde_actuel": dernier.solde_usd,
            "solde_debut": premier.solde_usd,
            "nb_releves": len(releves),
            "dernier": dernier.releve_le,
            "consomme_reel": consomme_reel,
            "consomme_estime": estime,
            "ecart": round(abs(estime - consomme_reel), 2),
            "sur_estime": estime > consomme_reel,
        }

    @api.model
    def _cron_relever_solde(self):
        return bool(self._relever())
