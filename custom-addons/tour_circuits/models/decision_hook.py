# -*- coding: utf-8 -*-
"""La porte « Patrick » du circuit passe par Décisions, sans toucher au
decision.py partagé : on hérite decision.fiche et on réagit à son approbation
ou son rejet quand elle porte une instance de circuit."""

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class DecisionFicheCircuit(models.Model):
    _inherit = "decision.fiche"

    def _circuit_repondre(self, approuve):
        for d in self:
            if d.res_model != "circuit.instance" or not d.res_id:
                continue
            inst = self.env["circuit.instance"].sudo().browse(d.res_id)
            if not inst.exists():
                continue
            passage = inst.passage_ids.filtered(
                lambda p: p.decision_id.id == d.id and p.etat == "attente")[:1]
            if passage:
                avis = "(approuvé par Patrick)" if approuve else (
                    d.commentaire or "(refusé par Patrick)")
                try:
                    inst._porte_repondue(passage, approuve, avis=avis)
                except Exception:  # noqa: BLE001
                    _logger.exception("Circuit : reponse porte Patron ratee")

    def write(self, vals):
        res = super().write(vals)
        if vals.get("etat") == "approuve":
            self._circuit_repondre(True)
        elif vals.get("etat") == "rejete":
            self._circuit_repondre(False)
        return res
