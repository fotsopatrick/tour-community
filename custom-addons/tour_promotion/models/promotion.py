# -*- coding: utf-8 -*-
"""La demande de mise en production : un nom de module, une case « vu en test ».

Le geste que Patrick voulait : « je bosse en test, puis je déploie en prod par
Décisions ». Ici, promouvoir = appliquer à la base `tour` le code déjà présent
(test et prod partagent les mêmes fichiers) via `-u <module>`. La seule porte
est l'approbation dans Décisions ; l'exécution appartient au cron de l'hôte.
"""

import logging
import os
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Le MÊME canal que l'atelier et la vitrine : la tour dépose un fichier, l'hôte
# le ramasse. Jamais une commande, seulement un nom de module validé.
DOSSIER_ORDRES = "/mnt/atelier/ordres"
RE_MODULE = re.compile(r"^[a-z][a-z0-9_]*$")


class PromotionDemande(models.Model):
    _name = "promotion.demande"
    _description = "Mettre un module en production"
    _inherit = ["mail.thread"]
    _order = "create_date desc"

    module = fields.Char(
        "Module à promouvoir", required=True, tracking=True,
        help="Le nom technique du module, ex : tour_debat. Il doit déjà être "
             "validé sur tour_test.")
    note = fields.Text("Ce qui a été validé en test",
                       help="Ce que tu as vérifié à l'écran sur tour_test.")
    valide_en_test = fields.Boolean(
        "Vu et validé sur tour_test", tracking=True,
        help="Ne coche que si tu as regardé le résultat sur tour_test. "
             "On ne promeut jamais ce qu'on n'a pas vu.")
    etat = fields.Selection(
        [("brouillon", "Brouillon"),
         ("demande", "En attente d'approbation"),
         ("en_prod", "Ordre déposé (déploiement en cours)")],
        "État", default="brouillon", readonly=True, tracking=True)
    decision_id = fields.Many2one("decision.fiche", "Fiche Décision",
                                  readonly=True)

    @api.constrains("module")
    def _verif_module(self):
        for r in self:
            if r.module and not RE_MODULE.match((r.module or "").strip()):
                raise UserError(_(
                    "Nom de module invalide : minuscules, chiffres et « _ » "
                    "seulement (ex : tour_debat). Pas d'espace, pas de « / »."))

    def action_demander(self):
        """Crée la fiche dans Décisions et s'arrête. Rien ne part en prod ici :
        c'est l'approbation qui déposera l'ordre."""
        self.ensure_one()
        if not self.valide_en_test:
            raise UserError(_(
                "Coche d'abord « Vu et validé sur tour_test » : on ne promeut "
                "que ce qui a été regardé en test."))
        if self.etat == "en_prod":
            raise UserError(_("Ce module a déjà un ordre de déploiement déposé."))
        fiche = self.env["decision.fiche"].sudo().create({
            "name": _("Mettre %s en production ?") % self.module,
            "origine": _("Promotion (validée en test)"),
            "resume": _(
                "<p>Le module <b>%s</b> a été validé sur tour_test.</p>"
                "<p>Approuver = le déployer en production (base <b>tour</b>) : "
                "un ordre est déposé, l'hôte fait <code>-u %s</code> et "
                "redémarre, puis contrôle.</p><p>%s</p>"
            ) % (self.module, self.module, self.note or ""),
            "res_model": "promotion.demande",
            "res_id": self.id,
            "priorite": "2",
        })
        self.write({"etat": "demande", "decision_id": fiche.id})
        self.message_post(body=_(
            "Demande de mise en production déposée dans Décisions."))
        return True

    def _deposer_ordre(self):
        """Appelée à l'approbation de la fiche (par le hook decision_hook).
        Dépose l'ordre pour l'hôte. Idempotent : un module déjà « en_prod » ne
        redépose pas."""
        self.ensure_one()
        mod = (self.module or "").strip()
        if not RE_MODULE.match(mod):
            raise UserError(_("Nom de module invalide au moment du dépôt."))
        try:
            os.makedirs(DOSSIER_ORDRES, exist_ok=True)
            chemin = os.path.join(DOSSIER_ORDRES, "promotion-%s.ordre" % mod)
            with open(chemin, "w", encoding="utf-8") as fh:
                fh.write("promouvoir %s en prod ; approuve par uid %s le %s\n"
                         % (mod, self.env.user.id, fields.Datetime.now()))
        except OSError as exc:
            raise UserError(_(
                "Impossible de déposer l'ordre de promotion (l'atelier "
                "est-il monté dans ce conteneur ?) : %s") % exc)
        self.write({"etat": "en_prod"})
        self.message_post(body=_(
            "Ordre déposé — %s sera mis à jour sur la prod dans la minute, "
            "puis le service redémarré.") % mod)
