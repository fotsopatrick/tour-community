# -*- coding: utf-8 -*-
"""Se préparer à un entretien d'embauche, sur le principe de QuestForge.

Demandé par Patrick le 28/07 : « je vais postuler à beaucoup d'entretiens
cette semaine, il me faut pouvoir me préparer dans le module qui gère cela,
sur le principe de QuestForge ».

QuestForge (D:/PROJETS/QUESTFORGE) transforme des offres d'emploi en quêtes :
on ne recopie pas l'application (React + Supabase, un autre monde technique),
on reprend son PRINCIPE — une offre collée devient une préparation structurée,
et chaque entretien passé laisse une trace qu'on relit avant le suivant.

Le geste : coller l'offre, cliquer « Préparer ». Un agent de l'atelier lit
l'offre et rend la préparation — les questions probables, ce qu'il faut
raconter, ce qu'il faut réviser. Après l'entretien, on note ce qui a été
demandé POUR DE VRAI : c'est la partie qui prend de la valeur avec le temps,
parce que les questions reviennent d'un recruteur à l'autre.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class EntretienFiche(models.Model):
    _name = "entretien.fiche"
    _description = "Préparation d'un entretien"
    _inherit = ["mail.thread"]
    _order = "date_entretien asc, id desc"

    name = fields.Char("Le poste", required=True, tracking=True)
    entreprise = fields.Char("L'entreprise")
    date_entretien = fields.Datetime(
        "L'entretien a lieu le", tracking=True,
        help="Laisser vide tant que la date n'est pas fixée.")
    offre = fields.Text(
        "L'offre, collée telle quelle", required=True,
        help="Le texte brut de l'annonce. C'est la matière première de la "
             "préparation — plus il est complet, meilleure elle est.")

    etat = fields.Selection(
        [("a_preparer", "À préparer"),
         ("en_cours", "Préparation en route"),
         ("prepare", "Prêt"),
         ("passe", "Passé")],
        "État", default="a_preparer", tracking=True)

    preparation = fields.Text(
        "La préparation", readonly=True,
        help="Rendue par l'atelier : questions probables, quoi raconter, "
             "quoi réviser.")
    mission_id = fields.Many2one("atelier.mission", "Mission", readonly=True)

    # Ce champ est le vrai trésor du module. La préparation d'une IA est
    # générique ; les questions RÉELLEMENT posées, elles, reviennent d'un
    # recruteur à l'autre — les relire avant l'entretien suivant vaut mieux
    # que n'importe quelle fiche.
    verdict = fields.Text(
        "Ce qui s'est vraiment passé",
        help="Les questions posées pour de vrai, ce qui a marché, ce qui a "
             "coincé. À remplir juste après — le soir même on a déjà oublié.")

    @api.model
    def _consigne(self, fiche):
        return "\n".join([
            "Tu prepares un candidat a un entretien d embauche. Tu ne postules",
            "pas a sa place : tu le prepares.",
            "",
            "LE POSTE : %s%s" % (fiche.name,
                                 " chez %s" % fiche.entreprise
                                 if fiche.entreprise else ""),
            "",
            "L OFFRE, TELLE QUELLE :",
            (fiche.offre or "").strip(),
            "",
            "RENDS EXACTEMENT QUATRE SECTIONS, en francais simple :",
            "",
            "1. CE QU ILS CHERCHENT VRAIMENT — derriere les mots de l annonce,",
            "   les deux ou trois choses qui comptent pour eux. Si l annonce",
            "   sent le piege (poste non paye, associe sans salaire, perimetre",
            "   flou), DIS-LE en premier.",
            "2. LES QUESTIONS PROBABLES — dix maximum, les plus vraisemblables",
            "   d abord, avec pour chacune UNE ligne sur ce qu une bonne",
            "   reponse contient.",
            "3. QUOI RACONTER — trois histoires a preparer (situation, action,",
            "   resultat chiffre). Ancre-les dans le profil : developpeur",
            "   full-stack, Odoo/Python, Flutter, WinDev, plateforme",
            "   auto-hebergee avec agents IA construite en solo.",
            "4. QUOI REVISER LA VEILLE — cinq points techniques max, tires de",
            "   l offre, chacun avec une question d auto-controle.",
            "",
            "Vingt minutes de lecture maximum. Pas de flatterie, pas de",
            "generalites : tout doit etre specifique a CETTE offre.",
        ])

    def action_preparer(self):
        """Confie la préparation à l'atelier. Une relance écrase l'ancienne."""
        self.ensure_one()
        if not (self.offre or "").strip():
            raise UserError(_("Colle d'abord le texte de l'offre."))
        Mission = self.env["atelier.mission"].sudo()
        mission = Mission.create({
            "name": _("Préparer l'entretien : %s", self.name[:50]),
            "consigne": self._consigne(self),
            # Le moteur qui lit et rédige suffit ici — pas besoin de celui
            # qui construit. Règle du 28/07 : le modèle suffisant à la tâche.
            "moteur": "claude",
        })
        mission.action_envoyer()
        self.write({"mission_id": mission.id, "etat": "en_cours"})
        self.message_post(body=_(
            "Préparation demandée à l'atelier (mission %s). Elle arrive "
            "d'ici quelques minutes.", mission.id))
        return True

    def action_relever(self):
        """Ramène la préparation quand elle est prête. Appelée par le cron."""
        for f in self:
            m = f.mission_id
            if not m or f.etat != "en_cours":
                continue
            if m.etat == "terminee" and (m.reponse or "").strip():
                f.write({"preparation": m.reponse, "etat": "prepare"})
                f.message_post(body=_("La préparation est prête."))
            elif m.etat == "echec":
                # Un échec doit se voir, pas se déduire d'une attente sans
                # fin : c'est la leçon des missions de Braignak du matin.
                f.write({"etat": "a_preparer"})
                f.message_post(body=_(
                    "La préparation a échoué (mission %s). Relance le "
                    "bouton — le compte rendu d'échec est sur la mission.",
                    m.id))
        return True

    def action_passe(self):
        self.ensure_one()
        self.etat = "passe"
        return True

    @api.model
    def _cron_relever(self):
        self.search([("etat", "=", "en_cours")]).action_relever()
        return True
