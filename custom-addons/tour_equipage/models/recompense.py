# -*- coding: utf-8 -*-
"""Le jeu de la récompense — ADMIN SEULEMENT.

Patrick récompense un agent pour son travail en lui ATTRIBUANT une
compétence. À l'attribution, la tour intervient et met tout ce qu'il faut
pour cette compétence :
  1. la fiche de compétence (equipe.competence), ancrée AUJOURD'HUI — elle
     compte à partir de maintenant, jamais l'historique d'avant (garde-fou
     anti-rétroactif) ;
  2. le circuit de validation correspondant, proposé EN BROUILLON (détection)
     — Patrick l'active s'il veut en faire une vraie chaîne de portes ;
  3. une ligne dans le registre des récompenses (equipe.recompense), datée,
     avec le motif — chaque point de reconnaissance a une date et une raison.

L'expérience (XP) reste MESURÉE, jamais posée à la main : la compétence
créée partira du compteur du catalogue (code), et la relève comptera le
travail réel qui vient. Récompenser, ce n'est pas fabriquer des points —
c'est reconnaître une compétence et l'outiller.
"""

from odoo import fields, models


class EquipeMembre(models.Model):
    _inherit = "equipe.membre"

    recompense_ids = fields.One2many(
        "equipe.recompense", "membre_id", "Récompenses")

    def _recompenser(self, nom, code, motif):
        """Attribue une compétence en récompense, et tout ce qu'elle entraîne.

        Retourne la fiche de récompense créée (ou une fiche vide si le nom
        est vide). Idempotente : récompenser deux fois avec la même
        compétence réutilise la fiche de compétence existante et ne crée
        qu'une nouvelle ligne de récompense (deux reconnaissances datées,
        pas deux compétences jumelles).
        """
        self.ensure_one()
        nom = (nom or "").strip()[:120]
        if not nom:
            return self.env["equipe.recompense"].browse()
        comp = self.competence_ids.filtered(lambda c: c.name == nom)[:1]
        if not comp:
            comp = self.env["equipe.competence"].create({
                "membre_id": self.id,
                "name": nom,
                "code": (code or "").strip() or "manuel",
                # L'ancrage à aujourd'hui : la compétence compte ce qui vient
                # APRÈS la récompense, pas tout ce que l'agent a fait avant.
                "depuis": fields.Date.context_today(self),
                "sequence": 10,
            })
        # Le circuit de la compétence, proposé en brouillon (détection).
        if "circuit.modele" in self.env:
            try:
                self.env["circuit.modele"].sudo()._proposer_circuit(
                    "Circuit — %s" % nom,
                    note="Récompense attribuée le %s : %s" % (
                        fields.Date.context_today(self), (motif or "")[:400]))
            except Exception:  # noqa: BLE001 — proposer reste optionnel
                pass
        return self.env["equipe.recompense"].create({
            "membre_id": self.id,
            "competence_id": comp.id,
            "name": (motif or nom).strip()[:300],
        })


class EquipeRecompense(models.Model):
    """Le registre des récompenses : chaque compétence attribuée a une date,
    un agent, un motif et un attribuant. Le pendant humain du registre des
    exploits — là où le registre compte des POINTS mesurés, celui-ci compte
    des RECONNAISSANCES décidées par Patrick."""

    _name = "equipe.recompense"
    _description = "Récompense — compétence attribuée à un agent"
    _order = "accorde_le desc, id desc"

    membre_id = fields.Many2one(
        "equipe.membre", "Membre", required=True, ondelete="cascade", index=True)
    competence_id = fields.Many2one(
        "equipe.competence", "Compétence", ondelete="set null",
        help="La compétence attribuée. Elle a été créée (ou retrouvée) à la "
             "récompense, avec son circuit en brouillon.")
    name = fields.Char("Ce qu'il a fait", required=True)
    accorde_le = fields.Datetime("Accordé le", default=fields.Datetime.now,
                                 readonly=True)
    par_id = fields.Many2one("res.users", "Attribué par", readonly=True,
                             default=lambda self: self.env.user)
