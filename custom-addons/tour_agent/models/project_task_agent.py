# -*- coding: utf-8 -*-
"""L'agent : exécute seul les tâches qu'on lui confie.

Périmètre volontairement étroit pour cette première version : il dispose des
outils du copilote — créer des notes, créer des tâches, mettre à jour le suivi
des apps. Il ne sait ni écrire de code ni déployer, et c'est délibéré : donner
un accès au serveur à une boucle autonome demande un bac à sable qui n'existe
pas encore.

Quatre garde-fous, parce qu'une boucle autonome qui consomme de l'argent et
modifie des données ne se lance pas sans frein :
  - interrupteur général, coupé par défaut ;
  - nombre de tâches traitées par passage, plafonné ;
  - une tâche n'est tentée qu'un nombre limité de fois ;
  - tout ce qu'il fait est écrit dans le fil de la tâche, jamais en silence.
"""
import logging
import re

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

PARAM_ACTIF = "tour_agent.actif"
PARAM_MAX = "tour_agent.max_par_passage"
PARAM_TOUT = "tour_agent.tout_ce_qui_est_assigne"
MAX_DEFAUT = 3
MAX_TENTATIVES = 3

CONSIGNE = """Tu es l'agent de la tour de contrôle. On te confie une tâche à
traiter seul, sans personne pour te répondre. Ton compte rendu sera collé tel
quel dans le fil de la tâche, et lu par Patrick.

CE QUE TU PEUX FAIRE
Tu travailles dans un dossier jetable, sur le serveur. Tu peux réfléchir,
rédiger, produire des fichiers, analyser un problème et proposer une marche à
suivre précise.

CE QUE TU NE PEUX PAS FAIRE
Tu n'as accès ni à la base de la tour, ni à son code en production, ni à
Internet. Tu ne peux donc ni créer une tâche, ni modifier une fiche, ni
déployer quoi que ce soit. Si la tâche demande ça, dis-le : ce n'est pas un
échec, c'est un renvoi vers quelqu'un qui a les moyens.

RÈGLES
1. Si la tâche est faisable avec ce que tu as, fais-la et dis précisément ce
   que tu as produit.
2. Sinon, ne fais RIEN et explique en une phrase ce qui te manque. Ne fais pas
   semblant, ne livre pas une version dégradée sans le dire.
3. Si la tâche est ambiguë, ne devine pas : dis quelle information manque.
4. N'invente aucun fait. Si tu as besoin d'une donnée que tu n'as pas, dis-le.
5. LIS LES NOTES ci-dessous avant d'agir. Elles viennent du fil de la tâche et
   contiennent souvent la précision qui change tout : une correction, un refus,
   un détail ajouté après coup. Une tâche se lit avec son historique — le titre
   dit le sujet, les notes disent la décision.
6. Écris comme à quelqu'un de pressé : phrases courtes, pas de jargon. Ton
   compte rendu doit être compris sans relire la tâche.

Voici la tâche :

TITRE : %(titre)s

DESCRIPTION : %(description)s

%(notes)s
"""


class ProjectTask(models.Model):
    _inherit = "project.task"

    pour_agent = fields.Boolean(
        "Confier à l'agent", default=False, index=True,
        help="Cochée : l'agent tentera de traiter cette tâche tout seul, à son "
             "prochain passage.")
    agent_tentatives = fields.Integer("Tentatives de l'agent", readonly=True,
                                      default=0, copy=False)
    agent_dernier_retour = fields.Text("Dernier retour de l'agent",
                                       readonly=True, copy=False)
    agent_mission_id = fields.Many2one(
        "atelier.mission", "Mission en cours", readonly=True, copy=False,
        help="La mission deposee a l'atelier. L'atelier travaille sur "
             "l'abonnement, pas sur une cle d'API.")
    agent_derniere_mission = fields.Many2one(
        "atelier.mission", "Derniere mission (meme en echec)", readonly=True,
        copy=False,
        help="La mission precedente, gardee quand elle echoue. Permet de "
             "poser #!chantier: sur la relance : l'agent reprend le dossier "
             "de travail au lieu de repartir de zero.")

    # ------------------------------------------------------------------
    @api.model
    def _cron_agent(self):
        icp = self.env["ir.config_parameter"].sudo()
        if (icp.get_param(PARAM_ACTIF) or "").strip().lower() not in ("1", "true"):
            _logger.info("Agent : interrupteur coupe, rien a faire.")
            return

        fait = self.env.ref("tour_dashboard.stage_fait", raise_if_not_found=False)
        domaine = [("agent_tentatives", "<", MAX_TENTATIVES)]

        # Mode « tout ce qui lui est assigné » : au lieu de cocher tâche par
        # tâche, l'agent prend tout ce qui porte « qui = Claude ».
        #
        # Le risque est réel et assumé : une tâche mal écrite part en exécution
        # sans relecture. C'est pour ça que le mode est explicite, séparé de
        # l'interrupteur général, et coupé par défaut.
        # LE PERIMETRE, ETROIT EXPRES.
        #
        # Patrick : << faut pas qu on se disperse >>. On ne ramasse donc QUE ce
        # qui porte l etiquette Claude, dans le projet de la tour, et que
        # Patrick a lui-meme passe en << En cours >>. Trois conditions : c est a
        # moi, c est le bon projet, et il l a decide.
        #
        # Le << En cours >> est le declencheur, et c est le bon : c est un geste
        # qu il fait deja naturellement, pas une case de plus a cocher.
        etiquette = self.env["project.tags"].sudo().search(
            [("name", "=", "Claude")], limit=1)
        encours = self.env["project.task.type"].sudo().search(
            [("name", "in", ["En cours", "In Progress"])], limit=1)
        if not etiquette or not encours:
            return
        domaine += [("tag_ids", "in", etiquette.id),
                    ("stage_id", "=", encours.id),
                    ("agent_mission_id", "=", False)]
        projet = self.env["project.project"].sudo().search(
            [("name", "ilike", "Tour de")], limit=1)
        if projet:
            domaine.append(("project_id", "=", projet.id))
        if fait:
            domaine.append(("stage_id", "!=", fait.id))

        # On releve d abord ce qui est revenu, ensuite on depose du neuf.
        self._agent_relever()

        limite = int(icp.get_param(PARAM_MAX) or MAX_DEFAUT)
        for tache in self.sudo().search(domaine, limit=limite, order="priority desc, id"):
            tache._agent_traiter()

    def _agent_traiter(self):
        """Depose la tache a l atelier. AUCUNE cle d API n est utilisee.

        L ancienne version appelait le cerveau du copilote, donc la cle d API :
        de l argent a chaque tache. Patrick a ete clair — << eteins-le s il
        consomme des API et pas mon compte >>. L atelier tourne sur le jeton
        d ABONNEMENT du serveur, le meme que Clark et Lois.

        Consequence assumee : la reponse n est plus immediate. Elle revient au
        passage suivant. C est le prix a payer pour ne rien depenser, et c est
        le bon prix.
        """
        self.ensure_one()
        # ATTENTION SI TU EPROUVES CETTE METHODE : un point de reprise annule
        # les ecritures en BASE, pas celles sur le DISQUE. Deposer une mission
        # ecrit un fichier dans ~/atelier/missions/ ; annuler la transaction
        # laisse le fichier, et l atelier l executera alors qu aucune fiche ne
        # le reclame. Paye le 28/07 : trois missions fantomes deposees par un
        # essai cense ne rien laisser.
        Mission = self.env["atelier.mission"].sudo()
        consigne = CONSIGNE % {
            "titre": self.name,
            "description": (self.description or "")[:4000],
            "notes": self._agent_notes(),
        }
        vals = self._agent_vals_mission(consigne)
        if "claude" in [m[0] for m in Mission._moteurs_disponibles()]:
            vals["moteur"] = "claude"
        mission = Mission.create(vals)
        self.sudo().write({"agent_tentatives": self.agent_tentatives + 1,
                           "agent_mission_id": mission.id})
        try:
            mission.action_envoyer()
        except Exception as exc:  # noqa: BLE001
            _logger.warning("Agent : depot impossible (tache %s) : %s", self.id, exc)
            self.sudo().agent_mission_id = False
            # Le brouillon orphelin part avec l'echec : le laisser, c'etait
            # une fiche de decision « Envoyer la mission » par tentative —
            # trois doublons pour la tache 346, payes le 29/07.
            try:
                mission.sudo().unlink()
            except Exception:  # noqa: BLE001 — deja envoyee ou verrouillee
                _logger.warning("Agent : brouillon %s non supprime", mission.id)
            self.message_post(body=_(
                "Depot impossible : %s", str(exc)[:200]))
            return False
        self.message_post(body=_(
            "<b>Confie a l atelier</b> (mission %(m)s, tentative %(n)s/%(x)s). "
            "Aucune cle d API : ca tourne sur l abonnement.",
            m=mission.id, n=self.agent_tentatives, x=MAX_TENTATIVES))
        return True

    def _agent_vals_mission(self, consigne):
        """La fiche de mission telle qu'elle partira à l'atelier.

        Extraite pour être testable sans rien déposer : créer une mission
        écrit un fichier dans ~/atelier/missions/ ; cette méthode, elle, ne
        fait que construire le dictionnaire. La tâche liée à une app
        (app_id, posé par suivi_apps) laisse son app à la mission — c'est
        elle qui déclenche la remontée dans le « Fait » de l'app à la fin.
        """
        self.ensure_one()
        vals = {"name": _("Tache %s", self.id), "consigne": consigne}
        if getattr(self, "app_id", False):
            vals["app_id"] = self.app_id.id
        # LA RELANCE REPREND LE TRAVAIL (08/08, Merline). Une tache qui a
        # deja echoue portait une mission precedente : sans lien, la relance
        # ouvrait un dossier VIDE et le modele reecrivait tout a neuf, jusqu'a
        # retomber sur la limite de 40 tours sans conclure (Tache 349,
        # 3 echecs le 08/08). En posant precedente_id, atelier.sh ajoute
        # #!chantier:<jeton> en tete de consigne et l'agent reprend son
        # dossier : ce qui est deja ecrit reste, il ne lui reste qu'a finir.
        if self.agent_derniere_mission:
            vals["precedente_id"] = self.agent_derniere_mission.id
        return vals

    def _agent_notes(self, limite=12):
        """Les notes du fil de la tache, mises a plat pour l agent.

        Patrick : << les dev savent qu ils doivent lire les notes ? >>. Non, ils
        ne le savaient pas — on ne leur envoyait que le titre et la description.
        Or la precision qui compte arrive souvent APRES, dans le fil : une
        correction, un refus, un detail. Une tache se lit avec son historique.

        On ecarte les messages purement techniques (changements d etape, envois
        automatiques) : un agent noye sous le bruit ne lit plus rien.
        """
        self.ensure_one()
        messages = self.message_ids.filtered(
            lambda m: m.body and m.message_type in ("comment", "notification"))
        lignes = []
        for msg in messages.sorted("id")[-limite:]:
            texte = re.sub(r"<[^>]+>", " ", str(msg.body or ""))
            texte = re.sub(r"\s+", " ", texte).strip()
            if not texte or len(texte) < 12:
                continue
            if texte.startswith(("Confie a l atelier", "Retour de l atelier",
                                 "Depot impossible")):
                continue
            qui = msg.author_id.name or "quelqu un"
            lignes.append("- [%s] %s" % (qui, texte[:600]))
        if not lignes:
            return "NOTES DU FIL : aucune."
        return ("NOTES DU FIL (lis-les, elles priment sur la description si "
                "elles la contredisent) :" + chr(10) + chr(10).join(lignes))

    @api.model
    def _agent_relever(self):
        """Ramene dans la tache ce que l atelier a rendu."""
        for tache in self.sudo().search([("agent_mission_id", "!=", False)]):
            mission = tache.agent_mission_id
            if mission.etat not in ("terminee", "echec"):
                continue
            retour = (mission.reponse or "").strip() or _("(aucune reponse)")
            # On garde la mission precedente pour la relance (voir
            # _agent_vals_mission) AVANT de detacher la tache : sans cette
            # trace, l'en-tete #!chantier: ne partait jamais et la relance
            # repartait d'un dossier vide (Tache 349, 3 echecs le 08/08).
            vals = {"agent_dernier_retour": retour,
                    "agent_mission_id": False}
            if mission.etat == "echec":
                vals["agent_derniere_mission"] = mission.id
            tache.write(vals)
            tache.message_post(body=_(
                "<b>Retour de l atelier</b> (mission %(m)s, %(e)s)<br/>%(r)s",
                m=mission.id, e=mission.etat,
                r=retour.replace(chr(10), "<br/>")[:6000]))
        return True

    def action_agent_maintenant(self):
        """Bouton : tenter tout de suite, sans attendre le passage planifié."""
        for tache in self:
            tache._agent_traiter()
        return True
