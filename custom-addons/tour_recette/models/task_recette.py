# -*- coding: utf-8 -*-
"""Un bug corrigé devient une étape du cahier de Jimmy.

Le manque, dit par Patrick le 26/07 : quand il signale un bug, on le corrige —
et **rien ne garantit qu'il ne reviendra pas**. Un correctif sans vérification
qui le suit est un correctif qu'on refera, et souvent sans s'en rendre compte :
c'est ainsi qu'un même défaut revient trois fois en six mois.

Le geste est volontairement simple : sur la tâche du bug, un bouton. On donne
l'adresse à vérifier et ce qu'on doit y trouver, et l'étape entre dans le
cahier. Jimmy la rejoue chaque nuit avec les autres.

**Ce n'est pas automatique, et c'est délibéré.** Fabriquer une étape tout seul
à partir d'un titre de tâche produirait des vérifications creuses — « la page
répond » — qui passent toujours et ne prouvent rien. Celui qui a vu la panne
est le seul à savoir ce qu'il faut regarder pour être sûr qu'elle est partie.
"""

from odoo import _, fields, models
from odoo.exceptions import UserError


class ProjectTask(models.Model):
    _inherit = "project.task"

    recette_etape_ids = fields.One2many(
        "recette.etape", "tache_id", "Vérifications nées de ce bug")
    nb_recette = fields.Integer("Vérifications", compute="_compute_nb_recette")

    def _compute_nb_recette(self):
        for t in self:
            t.nb_recette = len(t.recette_etape_ids)

    def action_creer_etape_recette(self):
        """Ouvre le formulaire qui transforme ce bug en vérification."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Ne plus jamais revoir ce bug"),
            "res_model": "recette.depuis.bug",
            "view_mode": "form",
            "target": "new",
            "context": {"default_tache_id": self.id,
                        "default_name": self.name[:80]},
        }


class RecetteDepuisBug(models.TransientModel):
    _name = "recette.depuis.bug"
    _description = "Transformer un bug corrigé en vérification"

    tache_id = fields.Many2one("project.task", required=True, readonly=True)
    cahier_id = fields.Many2one("recette.cahier", "Cahier", required=True)
    name = fields.Char("Ce qu'on vérifie", required=True)
    chemin = fields.Char("Chemin de la page", default="/", required=True,
                         help="Exemple : /community")
    attendu = fields.Char(
        "Texte qui doit être présent",
        help="Le mot ou la phrase qui prouve que le bug est parti. Laisser "
             "vide pour ne vérifier que si la page répond.")
    critique = fields.Boolean(
        "C'était grave", default=True,
        help="Coché, sa réapparition sera traitée comme urgente. Un bug qu'on "
             "a pris la peine de signaler l'était généralement.")

    def action_creer(self):
        self.ensure_one()
        if not self.cahier_id:
            raise UserError(_("Choisis le cahier où ranger cette vérification."))
        etape = self.env["recette.etape"].create({
            "cahier_id": self.cahier_id.id,
            "name": self.name,
            "type_etape": "contient" if self.attendu else "page",
            "chemin": self.chemin or "/",
            "attendu": self.attendu or False,
            "critique": self.critique,
            "tache_id": self.tache_id.id,
        })
        self.tache_id.message_post(body=_(
            "<b>Ce bug ne reviendra plus en silence.</b><br/>"
            "Jimmy vérifie désormais chaque nuit : « %(quoi)s » sur "
            "<code>%(ou)s</code>.%(txt)s",
            quoi=etape.name, ou=etape.chemin,
            txt=_(" Il doit y trouver « %s ».") % etape.attendu if etape.attendu else ""))
        return {"type": "ir.actions.act_window_close"}
