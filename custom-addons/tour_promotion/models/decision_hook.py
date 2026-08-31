# -*- coding: utf-8 -*-
"""Le hook d'approbation, SANS toucher au decision.py partagé.

On hérite `decision.fiche` et on surveille son passage à « approuve ». Quand la
fiche approuvée est une demande de promotion, on demande à la demande de déposer
son ordre. Toute la logique reste ici, dans ce module : `decision.py` (édité par
d'autres sessions) n'est pas modifié.
"""

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class DecisionFichePromotion(models.Model):
    _inherit = "decision.fiche"

    def write(self, vals):
        res = super().write(vals)
        # L'approbation d'une fiche pose etat="approuve" (voir
        # decision.action_approuver). C'est là qu'on agit — une seule fois.
        if vals.get("etat") == "approuve":
            for d in self:
                if d.res_model == "promotion.demande" and d.res_id:
                    dem = self.env["promotion.demande"].sudo().browse(d.res_id)
                    if dem.exists() and dem.etat != "en_prod":
                        try:
                            dem._deposer_ordre()
                        except Exception:  # noqa: BLE001
                            _logger.exception(
                                "Promotion : depot d'ordre echoue pour la "
                                "fiche %s", d.id)
                            raise
        return res
