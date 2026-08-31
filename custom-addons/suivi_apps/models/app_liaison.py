# -*- coding: utf-8 -*-
"""Relier les agents aux apps (tâche #765).

Une tâche ou une mission peut être rattachée à une app suivie (app.suivi).
À la fin d'une mission liée, la relève écrit un item DATÉ dans le champ
« Fait » de l'app — et JAMAIS de chiffre auto : la progression reste une
main humaine, parce qu'une barre qui monte toute seule gonfle sans rien
prouver (règle posée dans la tâche #765).
"""
import logging
import re

from markupsafe import escape

from odoo import _, fields, models

_logger = logging.getLogger(__name__)


class ProjectTask(models.Model):
    _inherit = "project.task"

    app_id = fields.Many2one(
        "app.suivi", string="App liée", index=True, ondelete="set null",
        help="L'app dont cette tâche fait avancer la fiche. À la fin de la "
             "mission qui la traite, un item daté s'ajoute dans le « Fait » "
             "de l'app — la progression, elle, reste à la main.")


class AtelierMission(models.Model):
    _inherit = "atelier.mission"

    app_id = fields.Many2one(
        "app.suivi", string="App liée", index=True, ondelete="set null",
        help="L'app que cette mission fait avancer. Quand la relève la "
             "termine, un item daté s'ajoute dans le « Fait » de l'app.")
    app_remontee = fields.Boolean(
        "Remontée dans l'app", readonly=True, copy=False, default=False,
        help="Une fois l'item daté écrit dans le « Fait » de l'app, la "
             "mission ne le réécrit plus — même si la relève repasse.")

    def action_relever(self):
        super().action_relever()
        for mission in self.filtered(
                lambda m: m.etat == "terminee" and m.app_id
                and not m.app_remontee):
            try:
                mission._remonter_app()
            except Exception:  # noqa: BLE001
                # Une remontée ratée ne doit jamais faire perdre un compte
                # rendu : la relève passe avant l'écriture dans l'app.
                _logger.exception(
                    "Atelier : remontee app ratee (mission %s)", mission.id)

    def _remonter_app(self):
        """Écrit l'item daté dans le « Fait » de l'app liée, une seule fois.

        Daté par `livree_le` (l'heure de livraison, posée une seule fois par
        la relève) — pas par la date du jour : une mission créée lundi et
        relevée mardi doit porter la date de livraison, pas celle de la
        relecture.
        """
        self.ensure_one()
        app = self.app_id
        if not app or self.app_remontee:
            return False

        texte = (self.resume or "").strip()
        if not texte:
            texte = self._resumer_local(self.reponse or "")
        if not texte:
            texte = (self.reponse or "").strip()
        if not texte:
            texte = (self.name or "")[:200]
        # Le resume peut laisser passer les marqueurs === d'une section quand
        # le moteur de condensation retombe : on les jette, on aplatit.
        texte = re.sub(r"===\s*[^=]*?===", "", texte)
        texte = re.sub(r"\s+", " ", texte).strip()[:300]

        date = self.livree_le or fields.Datetime.now()
        base = (self.env["ir.config_parameter"].sudo()
                .get_param("web.base.url") or "").rstrip("/")
        lien = ("<a href='%s/web#id=%s&model=atelier.mission"
                "&view_type=form'>mission n°%s</a>") % (base, self.id, self.id)
        ligne = "<li><b>%s</b> — %s : %s</li>" % (
            date.strftime("%d/%m/%Y"), lien, escape(texte))

        # str(...) d'abord : le champ Html est un Markup dont le replace
        # (markupsafe avec C speedups) ne remplace RIEN — la manipulation
        # de chaîne se fait en str brut, puis Odoo re-sanitise à l'écriture.
        fait = str(app.fait or "").strip()
        if "<ul>" in fait and "</ul>" in fait:
            nouveau = fait.replace("</ul>", ligne + "\n            </ul>", 1)
        else:
            nouveau = "<ul>\n            %s\n        </ul>" % ligne
        app.write({"fait": nouveau})
        self.write({"app_remontee": True})
        self.message_post(body=_(
            "Item daté ajouté dans le « Fait » de l'app <b>%s</b>.",
            app.name))
        return True
