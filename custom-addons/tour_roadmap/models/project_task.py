# -*- coding: utf-8 -*-
"""La version vit sur la TÂCHE, pas dans une liste à part.

On a découvert le 28/07 que les 134 cartes de « Versions » étaient toutes des
copies de tâches (une par tâche, même titre). Deux listes à tenir à jour pour
la même chose : à la première divergence, on ne sait plus laquelle croit.

La correction, choisie par Patrick : un seul objet, la tâche. La version n'est
qu'une étiquette dessus. L'écran Versions affiche les tâches d'un projet rangées
par version — et « par projet » vient tout seul, puisqu'une tâche appartient
déjà à un projet. La V2 de la tour et la V2 de Duelle ne se croisent jamais :
ce sont des tâches de projets différents.

Une tâche sans version n'est pas dans l'arbitrage : c'est juste une tâche du
journal. On ne met dans la feuille de route que ce qu'on veut vraiment trancher.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .roadmap import VERSIONS

EFFORTS = [
    ("petit", "Petit — une session"),
    ("moyen", "Moyen — deux ou trois"),
    ("gros", "Gros — un chantier"),
]
VALEURS = [
    ("debloque", "Débloque autre chose"),
    ("promesse", "Tient une promesse déjà faite"),
    ("confort", "Confort"),
    ("exploration", "Exploration"),
]


class ProjectTask(models.Model):
    _inherit = "project.task"

    tdc_version = fields.Selection(
        VERSIONS, "Version", index=True, tracking=True,
        group_expand="_tdc_versions",
        help="Range cette tâche dans la feuille de route de son projet. "
             "Vide = hors arbitrage, une tâche ordinaire du journal.")
    tdc_version_proposee = fields.Selection(
        VERSIONS, "Ce que je proposais", readonly=True,
        help="Trace de ma proposition initiale, pour voir ce qui a été arbitré "
             "autrement.")
    tdc_arbitre = fields.Boolean(
        "Arbitré autrement", compute="_tdc_compute_arbitre", store=True)
    tdc_propose_claude = fields.Boolean(
        "Proposé par moi, à valider", default=False,
        help="Vrai quand c'est moi qui ai posé la version, pas Patrick. Dès "
             "qu'il déplace la tâche lui-même, le drapeau tombe : il a tranché.")
    tdc_sans_patrick = fields.Boolean(
        "Je peux la faire seul", default=False,
        help="Vrai quand je peux la construire, déployer et vérifier sans "
             "intervention de Patrick.")
    tdc_pourquoi = fields.Text("Pourquoi cette version")
    tdc_avis = fields.Text("Mon avis sur ton choix")
    tdc_effort = fields.Selection(EFFORTS, "Effort")
    tdc_valeur = fields.Selection(VALEURS, "Ce que ça apporte")
    tdc_couleur = fields.Integer("Couleur", compute="_tdc_compute_couleur", store=True)

    @api.model
    def _tdc_versions(self, stages, domain):
        """Toutes les colonnes, même vides — sinon on ne peut plus y déposer."""
        return [v[0] for v in VERSIONS]

    @api.depends("tdc_version", "tdc_version_proposee")
    def _tdc_compute_arbitre(self):
        for rec in self:
            rec.tdc_arbitre = bool(
                rec.tdc_version_proposee
                and rec.tdc_version != rec.tdc_version_proposee
                and rec.tdc_version not in (False, "a_trier"))

    @api.depends("tdc_valeur")
    def _tdc_compute_couleur(self):
        teintes = {"debloque": 2, "promesse": 4, "confort": 0, "exploration": 7}
        for rec in self:
            rec.tdc_couleur = teintes.get(rec.tdc_valeur, 0)

    def write(self, vals):
        if "tdc_version" in vals:
            libelles = dict(VERSIONS)
            Version = self.env["roadmap.version"]
            for rec in self:
                avant, apres = rec.tdc_version, vals["tdc_version"]
                if avant == apres:
                    continue
                # Une version validée ne laisse plus rien entrer ni sortir —
                # dans les deux sens, et PAR PROJET : figer la V2 de la tour ne
                # fige pas celle de Duelle.
                for code, sens in ((avant, _("sortir de")),
                                   (apres, _("entrer dans"))):
                    if code and Version._figee(rec.project_id.id, code):
                        raise UserError(_(
                            "« %(v)s » de « %(p)s » est validée : on ne peut "
                            "plus %(sens)s elle. Rouvre la version si la liste "
                            "doit vraiment changer — ça demande d'écrire "
                            "pourquoi, et ça reste inscrit.",
                            v=libelles.get(code, code),
                            p=rec.project_id.display_name, sens=sens))
                contre = ""
                if rec.tdc_version_proposee and apres != rec.tdc_version_proposee:
                    contre = _(" — je proposais « %s »") % libelles.get(
                        rec.tdc_version_proposee, rec.tdc_version_proposee)
                rec.message_post(body=_(
                    "Version : « %(a)s » → « %(b)s »%(c)s.",
                    a=libelles.get(avant, avant or "—"),
                    b=libelles.get(apres, apres or "—"), c=contre))
        res = super().write(vals)
        # Quand Patrick déplace lui-même, ma proposition n'est plus en attente.
        if "tdc_version" in vals and "tdc_propose_claude" not in vals:
            self.filtered("tdc_propose_claude").write({"tdc_propose_claude": False})
        return res
