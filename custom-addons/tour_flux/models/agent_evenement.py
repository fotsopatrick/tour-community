# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class AgentEvenement(models.Model):
    _name = "agent.evenement"
    _description = "Flux des agents : ce que font Clark, atelier, Braignak, Jonathan"
    _order = "create_date desc, id desc"

    agent = fields.Char("Agent", required=True, index=True,
                        help="Qui a agi : Clark, atelier, Braignak, Jonathan...")
    categorie = fields.Char("Categorie", index=True,
                            help="Genre : mission, etude, decision, message...")
    sujet = fields.Char("Sujet", required=True)
    detail = fields.Text("Detail")
    ref_model = fields.Char("Modele lie", index=True)
    ref_id = fields.Integer("Id lie", index=True)
    base = fields.Char("Base", index=True,
                       default=lambda self: self.env.cr.dbname)
    traite = fields.Boolean("Vu par Raphael", default=False, index=True)
    vu_le = fields.Datetime("Vu le", readonly=True)

    @api.model
    def publier(self, agent, sujet, detail=None, categorie=None, ref=None):
        """Un agent depose ici ce qu il vient de faire.

        Ne casse JAMAIS le travail de l appelant : un savepoint isole
        l ecriture, et toute erreur est avalee (un flux qui plante serait
        pire que pas de flux). Rend l enregistrement, ou un vide en echec.
        """
        try:
            with self.env.cr.savepoint():
                vals = {
                    "agent": (agent or "?")[:120],
                    "sujet": (sujet or "(sans sujet)")[:250],
                    "detail": detail or "",
                    "categorie": (categorie or "")[:60],
                }
                if ref is not None and getattr(ref, "_name", None) and ref.id:
                    vals["ref_model"] = ref._name
                    vals["ref_id"] = ref.id
                return self.sudo().create(vals)
        except Exception:  # noqa: BLE001 -- le flux ne casse jamais l appelant
            _logger.exception("Flux agents : publication ratee")
            return self.browse()

    @api.model
    def drainer(self, limite=300, marquer=True):
        """Lu par Raphael a chaque connexion : rend ce qui est neuf, en
        texte, et le marque vu (sauf si marquer=False pour un simple coup
        d oeil). L ordre est chronologique : on relit dans le sens du temps.
        """
        evs = self.sudo().search([("traite", "=", False)],
                                 order="create_date asc, id asc", limit=limite)
        lignes = []
        for e in evs:
            bout = (" -- " + (e.detail or "")[:200]) if e.detail else ""
            lignes.append("[%s] (%s) %s | %s : %s%s" % (
                e.create_date, e.base or "?", e.agent,
                e.categorie or "-", e.sujet, bout))
        if marquer and evs:
            evs.write({"traite": True, "vu_le": fields.Datetime.now()})
        return "\n".join(lignes) if lignes else "(rien de neuf)"

    def action_marquer_vu(self):
        self.write({"traite": True, "vu_le": fields.Datetime.now()})
