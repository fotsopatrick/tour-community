# -*- coding: utf-8 -*-
"""Les cloisons se reposent toutes seules.

POURQUOI CE FICHIER EXISTE. `post_init_hook` ne s'execute qu'a l'INSTALLATION.
Une mise a jour (`-u`) ne le rejoue pas : les regles supprimees a la main, ou
perdues par un menage d'Odoo, ne revenaient jamais. Mesure du premier essai :
module installe, zero regle en base, et personne pour le dire.

`_register_hook` est appele a chaque chargement du registre — donc a chaque
demarrage et a chaque mise a jour. Les cloisons se reparent seules.

Il ne fait rien quand tout est en place : un seul comptage, et il s'arrete.
On ne paie les 82 ecritures que le jour ou il manque quelque chose.
"""
from odoo import api, models

from . import CLOISONS, poser_les_cloisons


class CloisonnementAutoRepare(models.AbstractModel):
    _name = "tour.cloisonnement"
    _description = "Cloisonnement — se repose tout seul au demarrage"

    def _register_hook(self):
        res = super()._register_hook()
        try:
            attendu = 2 * len([m for m in CLOISONS if m in self.env])
            pose = self.env["ir.model.data"].sudo().search_count([
                ("module", "=", "tour_cloisonnement"),
                ("model", "=", "ir.rule"),
            ])
            if pose < attendu:
                poser_les_cloisons(self.env)
        except Exception:
            # Une cloison qui n'a pas pu se poser ne doit JAMAIS empecher la
            # tour de demarrer : on laisse le controle du grand passage le
            # dire, plutot que de tomber au chargement du registre.
            import logging
            logging.getLogger(__name__).exception(
                "tour_cloisonnement : les cloisons n ont pas pu etre posees")
        return res

    @api.model
    def reposer(self):
        """Reposer les cloisons a la demande (shell, cron, controle)."""
        return poser_les_cloisons(self.env)
