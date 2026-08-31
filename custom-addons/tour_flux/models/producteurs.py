# -*- coding: utf-8 -*-
from odoo import api, models


class DecisionFicheFlux(models.Model):
    """Chaque nouvelle decision a trancher est une action d agent : au flux."""
    _inherit = "decision.fiche"

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for r in recs:
            self.env["agent.evenement"].publier(
                r.origine or "agent",
                "Decision a trancher : %s" % (r.name or ""),
                detail="Priorite %s, etat %s" % (r.priorite, r.etat),
                categorie="decision", ref=r)
        return recs


class BraignakEtudeFlux(models.Model):
    """Chaque nouvelle etude Braignak est un travail d agent : au flux."""
    _inherit = "braignak.etude"

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for r in recs:
            self.env["agent.evenement"].publier(
                "Braignak",
                "Nouvelle etude : %s" % (r.display_name or ""),
                categorie="etude", ref=r)
        return recs
