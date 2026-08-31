# -*- coding: utf-8 -*-
"""Chrono : le temps passé, par agent et par projet.

Demandé par Patrick le 28/07 : « un tracker de temps par projet avec l'IA…
tous les agents tracent le temps qu'ils passent sur une tâche, sauf si ça
ralentit ou crée des dépenses ».

Les deux contraintes sont des règles de construction, pas des intentions :

- **Zéro dépense** : aucune IA ne mesure quoi que ce soit. Le temps d'une
  mission, c'est l'écart entre son envoi et sa relève — deux horodatages qui
  existent déjà. Le temps de Chloe, c'est la durée réelle de l'appel. Rien
  n'est demandé à un modèle, donc rien ne coûte un jeton.
- **Zéro ralentissement** : chaque enregistrement est une seule écriture en
  base, dans un try silencieux — si le chrono casse, le travail continue,
  jamais l'inverse.

Et une honnêteté imposée par le champ `source` : ce qui est MESURÉ et ce qui
est ESTIMÉ ne se mélangent pas. Les heures de construction de la tour
(23-28/07) sont des estimations assumées, déduites des heures de commit — les
afficher comme des mesures serait fabriquer la donnée.
"""
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ChronoTemps(models.Model):
    _name = "chrono.temps"
    _description = "Temps passé"
    _order = "quand desc"

    agent = fields.Char("Qui", required=True, index=True,
                        help="Le prénom de l'agent, ou Patrick, ou Claude.")
    projet = fields.Char("Sur quoi", required=True, default="La tour",
                         index=True,
                         help="Le projet — « La tour » par défaut, ou le nom "
                              "de l'app construite.")
    minutes = fields.Float("Minutes", required=True)
    quand = fields.Datetime("Quand", required=True,
                            default=fields.Datetime.now, index=True)
    source = fields.Selection(
        [("mesure", "Mesuré"), ("estimation", "Estimation")],
        "Source", required=True, default="mesure",
        help="Mesuré = déduit d'horodatages réels. Estimation = un humain "
             "a évalué. Les deux ne se mélangent jamais dans les totaux "
             "sans le dire.")
    mission_id = fields.Many2one("atelier.mission", "Mission",
                                 ondelete="set null")
    user_id = fields.Many2one("res.users", "Compte", ondelete="set null")
    note = fields.Char("Note")

    @api.model
    def pointer(self, agent, minutes, projet=None, mission=None, note=None,
                source="mesure"):
        """Enregistre sans jamais casser l'appelant : le chrono est un
        greffon, pas une dépendance."""
        try:
            if minutes and minutes > 0:
                # Deux decimales : un echange de Chloe dure des secondes,
                # et round(0.03, 1) le transformait en 0,0 — une mesure
                # vraie ecrasee par l'arrondi (retest du 28/07).
                self.sudo().create({
                    "agent": agent or "?",
                    "minutes": round(minutes, 2),
                    "projet": projet or "La tour",
                    "mission_id": mission and mission.id or False,
                    "note": (note or "")[:200] or False,
                    "source": source,
                })
        except Exception:  # noqa: BLE001 — le chrono ne casse jamais le travail
            _logger.exception("Chrono : pointage rate (%s)", agent)
        return True


class AtelierMissionChrono(models.Model):
    """À la relève d'une mission, son temps se pointe tout seul."""
    _inherit = "atelier.mission"

    def write(self, vals):
        # On attrape la TRANSITION vers terminée/échec — pas les réécritures
        # ultérieures — et on lit l'envoi AVANT que le write ne bouge quoi
        # que ce soit.
        a_pointer = []
        if vals.get("etat") in ("terminee", "echec"):
            for m in self:
                if m.etat == "envoyee" and m.envoyee_le:
                    a_pointer.append((m.id, m.envoyee_le))
        res = super().write(vals)
        if a_pointer and "chrono.temps" in self.env:
            Chrono = self.env["chrono.temps"]
            maintenant = fields.Datetime.now()
            for mid, envoi in a_pointer:
                m = self.browse(mid)
                minutes = (maintenant - envoi).total_seconds() / 60.0
                agent = m.AGENTS.get((m.moteur or "").strip(), "L atelier")
                if "debat.avis" in self.env:
                    avis = self.env["debat.avis"].sudo().search(
                        [("mission_id", "=", mid)], limit=1)
                    if avis:
                        agent = avis.membre_id.name
                projet = "La tour"
                if m.publier and (m.slug or m.name):
                    projet = (m.slug or m.name)[:60]
                Chrono.pointer(agent, minutes, projet=projet, mission=m,
                               note=m.name and m.name[:120])
        return res
