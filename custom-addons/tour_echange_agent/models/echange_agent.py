# -*- coding: utf-8 -*-
"""L'échange entre agents : une demande, une réponse, un retour au demandeur.

Patrick, 31/07 : « les agents doivent communiquer tout seuls — si Chloe
demande un truc à Clark, une fois fini il doit renvoyer la réponse à Chloe ».
C'est la pièce qui manquait à la discussion : le fil de discussion (module
tour_discussion) sait parler À un agent, mais c'est un HUMAIN qui ouvre le
fil. Ici, un AGENT peut demander à un autre, et la réponse revient au
demandeur, notifiée dans le flux commun.

On réutilise ce qui existe, on ne réinvente pas :
- l'envoi passe par le fil de discussion (moteur « discussion », mémoire par
  fil, autonomie selon le chantier) ;
- le relevé étend discussion.echange._relever : quand l'échange passe à
  « terminé », la réponse est recopiée ici et le flux publie
  « <agent> a répondu à <demandeur> » ;
- la sécurité : chaque échange utilise le moteur du destinataire, jamais un
  autre (même règle que discussion.fil).

Le garde-fou du périmètre : l'agent qui demande reste dans son périmètre, il
n'écrit jamais en production. L'échange est tracé (agent.evenement) pour
qu'on puisse relire qui a demandé quoi à qui.
"""

import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class EchangeAgent(models.Model):
    _name = "echange.agent"
    _description = "Une demande d'un agent à un autre agent"
    _inherit = ["mail.thread"]
    _order = "create_date desc"

    name = fields.Char("Demande", required=True)
    demandeur_id = fields.Many2one(
        "equipe.membre", "Demandé par", required=True,
        help="L'agent qui pose la question. Vide = Patrick (un humain).")
    demandeur_nom = fields.Char(
        "Demandeur (libre)", help="Si le demandeur n'est pas un agent "
        "d'équipe (ex. un module ou Patrick), son nom en clair.")
    destinataire_id = fields.Many2one(
        "equipe.membre", "Destinataire", required=True,
        help="L'agent à qui on demande. Doit avoir un moteur pour répondre.")
    question = fields.Text("La demande", required=True)
    reponse = fields.Text("Réponse", readonly=True)
    etat = fields.Selection(
        [("envoye", "Envoyée — en attente de réponse"),
         ("termine", "Réponse reçue"),
         ("echec", "Échec")],
        "État", default="envoye", required=True, readonly=True, tracking=True)
    autonomie = fields.Boolean(
        "Autonomie totale",
        help="Décoché, l'agent destinataire écrit des fichiers mais demande "
             "la permission pour lancer des commandes — et comme personne "
             "n'est là pour la donner, il s'arrête. À réserver au dépôt de "
             "travail, jamais à la production.")
    fil_id = fields.Many2one(
        "discussion.fil", "Fil de discussion", readonly=True,
        help="Le fil qui porte l'échange réellement parti à l'agent.")
    echange_id = fields.Many2one(
        "discussion.echange", "Échange", readonly=True)
    source = fields.Char(
        "Lien avec le travail",
        help="Ce qui a motivé la demande : mission, tâche, étude… en clair.")
    reponse_le = fields.Datetime("Réponse le", readonly=True)
    # À qui ce retour s'affiche : le demandeur, ou tout le monde si vide.
    publie_flux = fields.Boolean(
        "Publié dans le flux", default=False, readonly=True,
        help="Quand la réponse arrive, elle est annoncée dans le flux commun "
             "des agents (agent.evenement).")

    # ------------------------------------------------------------------
    def _moteur_destinataire(self):
        self.ensure_one()
        mot = (self.destinataire_id.moteur or "").strip()
        if not mot:
            raise UserError(_(
                "« %s » n'a pas de moteur : il ne peut pas répondre à une "
                "demande. Choisir un agent dont la fiche porte un moteur.",
                self.destinataire_id.name))
        return mot

    def _question_batie(self):
        """La demande telle qu'elle part au destinataire.

        Cinq lignes maximum en réponse : entre agents, les réponses courtes
        gardent le fil clair et réduisent le bruit (livre AI Agents in
        Action, ch. 2 — c'est aussi moins de jetons à chaque relais).
        """
        self.ensure_one()
        # Le contexte de la demande, pour que l'agent réponde sans deviner.
        contexte = ""
        if self.source:
            contexte = "\n\n(Contexte : %s)" % self.source
        return (
            "Tu es %s (%s). %s te demande :\n\n%s%s\n\n"
            "Réponds directement, sans écrire de fichier. COMMENCE par une "
            "phrase qui dit si c'est fait ou ce qui bloque, puis le détail. "
            "Ta réponse tient en CINQ lignes au maximum : entre agents, une "
            "réponse courte garde l'échange clair."
            % (self.destinataire_id.name,
               self.destinataire_id.poste or "membre de l'équipe",
               self.demandeur_nom or self.demandeur_id.name or "un agent",
               self.question, contexte))

    def action_envoyer(self):
        """Crée le fil de discussion vers le destinataire et envoie la question."""
        self.ensure_one()
        if self.etat != "envoye":
            raise UserError(_("Cet échange est déjà terminé."))
        if self.fil_id:
            raise UserError(_("Cet échange a déjà été envoyé."))
        mot = self._moteur_destinataire()
        question = self._question_batie()

        fil = self.env["discussion.fil"].sudo().create({
            "name": _("Demande de %s à %s") % (
                self.demandeur_nom or self.demandeur_id.name,
                self.destinataire_id.name),
            "agent_id": self.destinataire_id.id,
            "user_id": 1,  # compte système : c'est un agent qui parle
            "question": question,
            "autonomie": self.autonomie,
        })
        try:
            fil.action_envoyer()
        except Exception as exc:  # noqa: BLE001
            raise UserError(_(
                "La demande n'est pas partie : %s", exc))
        echange = fil.echange_ids[:1]
        self.write({
            "fil_id": fil.id,
            "echange_id": echange.id if echange else False,
        })
        self.message_post(body=_(
            "Demande envoyée à %s via le fil de discussion.",
            self.destinataire_id.name))
        return True

    def action_relever(self):
        """Bouton : va chercher la réponse si elle est prête."""
        self._relever()
        return True

    def _relever(self):
        """Va chercher la réponse de l'agent destinataire."""
        for ech in self:
            if ech.etat != "envoye" or not ech.echange_id:
                continue
            e = ech.echange_id
            if e.etat == "envoye":
                # Le fil est encore en route : on laisse _cron_relever du
                # module discussion faire le travail, on revient plus tard.
                continue
            if e.etat == "echec":
                ech.write({"etat": "echec"})
                continue
            ech.write({
                "etat": "termine",
                "reponse": e.reponse or "",
                "reponse_le": fields.Datetime.now(),
            })
            self._notifier_reponse(ech)

    def _notifier_reponse(self, ech):
        """Annonce la réponse dans le flux commun, au nom du destinataire."""
        ech.ensure_one()
        if ech.publie_flux:
            return
        destinataire = ech.destinataire_id.name
        demandeur = ech.demandeur_nom or ech.demandeur_id.name
        self.env["agent.evenement"].sudo().publier(
            destinataire,
            "Réponse à %s : %s" % (demandeur, (ech.name or "")[:100]),
            detail=(ech.reponse or "")[:500],
            categorie="echange", ref=ech)
        ech.write({"publie_flux": True})

    # ------------------------------------------------------------------
    @api.model
    def _cron_relever(self):
        """Ramène les réponses des agents aux demandes en attente."""
        for ech in self.search([("etat", "=", "envoye"),
                                ("echange_id", "!=", False)]):
            ech._relever()
        return True


# --------------------------------------------------------------------------
# La boucle : quand un échange de discussion passe à « terminé », on remonte
# la réponse dans l'échange d'agent correspondant.
# --------------------------------------------------------------------------
class DiscussionEchangeRetour(models.Model):
    _inherit = "discussion.echange"

    def _relever(self):
        super()._relever()
        # Après le relevé, tout échange « terminé » lié à un échange d'agent
        # remonte sa réponse au demandeur.
        for e in self:
            if e.etat != "termine":
                continue
            ech = self.env["echange.agent"].sudo().search(
                [("echange_id", "=", e.id)], limit=1)
            if ech:
                ech._relever()
        return True
