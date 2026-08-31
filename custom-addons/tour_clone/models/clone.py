# -*- coding: utf-8 -*-
"""Le clone de Patrick : un agent qui apprend SON style et LUI propose.

Ce que le clone EST (d'après le prototype Braignak #40, validé) :
- il APPREND le style de Patrick (longueur des phrases, ton direct, phrases
  courtes) depuis ce que Patrick écrit (courriels, décisions, consignes) ;
- il VERSIONNE sa fiche persona avec retour arrière ;
- il est DANS UNE CAGE : il ne produit que du TEXTE, il n'a aucune action
  possible — garanti par le moteur (lecture-seule à l'origine) ET par les
  consignes.

Ce que Patrick a décidé (31/07) : le brancher EN ÉCRITURE (moteur
deepseek-agent, comme les constructeurs) mais avec des garde-fous stricts :
- il ne PEUT PAS envoyer de message, publier, modifier la production ;
- tout ce qu'il PROPOSE (réponse, texte, fiche) passe par une validation.

Deux crons l'animent :
- _cron_apprendre : relit ce que Patrick a écrit récemment et met à jour sa
  fiche persona (versionnée).
- _cron_veiller : chaque jour, il lit les décisions récentes et propose un
  « si j'étais Patrick » — une fiche Réponses qui suit SON style.
"""
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class EquipeMembreClone(models.Model):
    _inherit = "equipe.membre"

    # Les permissions du clone, lues par les crons et la fiche Décisions.
    # Défaut prudent : le clone NE PEUT PAS envoyer/publier/modifier/décider.
    clone_peut_apprendre = fields.Boolean(
        "Apprendre ton style", default=False)
    clone_peut_veiller = fields.Boolean(
        "Veille quotidienne", default=False)
    clone_peut_proposer = fields.Boolean(
        "Rédiger des propositions", default=False)
    clone_peut_envoyer = fields.Boolean(
        "Envoyer des messages", default=False)
    clone_peut_publier = fields.Boolean(
        "Publier", default=False)
    clone_peut_modifier = fields.Boolean(
        "Modifier la tour", default=False)
    clone_peut_decider = fields.Boolean(
        "Décider seul", default=False)

    clone_style_actif = fields.Boolean(
        "Le clone apprend ton style", default=False,
        help="Coché : le cron d'apprentissage lit tes écrits récents et "
             "versionne sa fiche persona.")
    clone_veille_actif = fields.Boolean(
        "Le clone propose chaque jour", default=False,
        help="Coché : chaque jour, le clone rend une fiche Réponses « si "
             "j'étais Patrick » sur les décisions récentes.")

    # ------------------------------------------------------------------
    def action_appliquer_permissions(self, **perms):
        """Applique les cases cochées par Patrick à la fiche du clone."""
        self.ensure_one()
        valeurs = {}
        correspondance = {
            "clone_peut_apprendre": "clone_peut_apprendre",
            "clone_peut_veiller": "clone_peut_veiller",
            "clone_peut_proposer": "clone_peut_proposer",
            "clone_peut_envoyer": "clone_peut_envoyer",
            "clone_peut_publier": "clone_peut_publier",
            "clone_peut_modifier": "clone_peut_modifier",
            "clone_peut_decider": "clone_peut_decider",
        }
        for cle, champ in correspondance.items():
            if cle in perms:
                valeurs[champ] = bool(perms[cle])
        # Les crons héritent de l'apprentissage et de la veille.
        if "clone_peut_apprendre" in perms:
            valeurs["clone_style_actif"] = bool(perms["clone_peut_apprendre"])
        if "clone_peut_veiller" in perms:
            valeurs["clone_veille_actif"] = bool(perms["clone_peut_veiller"])
        if valeurs:
            self.write(valeurs)
        return True

    # ------------------------------------------------------------------
    @api.model
    def _clone(self):
        return self.search([("name", "=", "Clone de Patrick")], limit=1) or None

    @api.model
    def _patrick_user(self):
        """Le compte res.users de Patrick — trouvé par l'activité, pas par un
        nom exact en dur.

        Piège payé le 31/07 : le cron d'apprentissage filtrait sur
        `user_id.name = "Patrick"`, qui ne matche AUCUN compte (le compte de
        Patrick s'appelle « Le cerveau », puis « KAMDEM Patrick »). Résultat :
        le clone n'a jamais rien appris. On résout autrement : parmi les
        comptes internes dont le nom contient « Patrick » (ou le nom
        historique « Le cerveau »), on prend celui qui a tranché le PLUS de
        décisions — c'est le vrai décideur.
        """
        Users = self.env["res.users"].sudo()
        actifs = Users.search([("share", "=", False), ("active", "=", True)])
        if not actifs:
            return Users.browse()
        candidats = actifs.filtered(
            lambda u: "patrick" in (u.partner_id.name or "").lower()
            or (u.partner_id.name or "").strip().lower() == "le cerveau")
        if not candidats:
            return actifs[:1]
        if "decision.fiche" in self.env:
            D = self.env["decision.fiche"].sudo()

            def tranchees(u):
                try:
                    return D.search_count(
                        [("user_id", "=", u.id),
                         ("etat", "in", ("approuve", "rejete"))])
                except Exception:  # noqa: BLE001
                    return 0
            return max(candidats, key=tranchees) or candidats[0]
        return candidats[0]

    @api.model
    def _cron_apprendre(self):
        """Relit ce que Patrick a tranché et corrigé, et met à jour la persona.

        Corrigé le 31/07 : avant, il filtrait sur user_id.name='Patrick' (qui
        ne matche aucun compte) et ne lisait que le nom/commentaire des
        décisions. Maintenant il apprend de DEUX matières :
        1. les CORRECTIONS par proposition (clone.feedback : « le clone a
           proposé X, Patrick a dit pas d'accord parce que Y ») — c'est LE
           signal qui rapproche le clone de la façon de penser de Patrick ;
        2. ses décisions récentes tranchées avec ses mots (commentaire).
        """
        clone = self._clone()
        if not clone or not clone.clone_peut_apprendre:
            return False
        Patrick = self._patrick_user()
        if not Patrick:
            return False
        morceaux = []

        # 1) SES CORRECTIONS DES PRÉ-DÉCISIONS DU CLONE, une par une.
        if "clone.feedback" in self.env:
            retours = self.env["clone.feedback"].sudo().search(
                [("repondu_le", "!=", False)],
                order="repondu_le desc", limit=40)
            for f in retours:
                verdict = "d'accord" if f.verdict == "ok" else "PAS d'accord"
                morceaux.append(
                    "LE CLONE A PROPOSE : %s\nSA JUSTIFICATION : %s\n"
                    "PATRICK : %s — %s"
                    % (f.proposition or "", f.justif or "", verdict,
                       f.pourquoi or ""))

        # 2) SES DÉCISIONS TRANCHÉES RÉCEMMENT, avec ses mots.
        dep = fields.Datetime.subtract(fields.Datetime.now(), days=7)
        marqueurs = ("APPROUVE", "REJETE", "Doublon fermé")
        decisions = self.env["decision.fiche"].sudo().search(
            [("user_id", "=", Patrick.id),
             ("etat", "in", ("approuve", "rejete")),
             ("create_date", ">=", dep)], limit=50)
        decisions = decisions.filtered(
            lambda d: (d.commentaire or "").strip()
            and not any(m in (d.commentaire or "") for m in marqueurs))
        for d in decisions:
            morceaux.append(
                "DECISION : %s\nVERDICT : %s\nPOURQUOI : %s"
                % (d.name or "", d.etat, (d.commentaire or "").strip()))

        matiere = "\n\n".join(morceaux)
        if not matiere:
            return False
        # On dépose une mission d'apprentissage à l'atelier (moteur du clone).
        Mission = self.env["atelier.mission"].sudo()
        consigne = (
            "Tu es le Clone de Patrick. Relis la matière suivante — les "
            "corrections de Patrick sur TES propositions et sur des décisions "
            "qu'il a tranchées — et extrais SA façon de penser : ce qu'il "
            "accepte, ce qu'il refuse, POURQUOI, son ton, sa longueur de "
            "phrase, ce qu'il ne dit jamais.\n"
            "Écris la fiche persona en français, simple. N'INVENTE PAS ce "
            "que la matière ne montre pas.\n\n=== LA MATIÈRE ===\n%s"
            % matiere[:7000])
        m = Mission.create({
            "name": "Clone — apprendre le style de Patrick",
            "consigne": consigne,
            "moteur": clone.moteur or "deepseek-agent",
        })
        m.action_envoyer()
        _logger.info("Clone : mission d'apprentissage déposée (%s)", m.id)
        return True

    @api.model
    def _cron_veiller(self):
        """Chaque jour : le clone rend un « si j'étais Patrick » sur les
        décisions EN ATTENTE. Toujours une proposition, jamais une action.

        Corrigé le 31/07 : avant, il ne prenait que les décisions des 24
        dernières heures (limit 20) — 36 décisions attendaient et le clone
        n'en voyait que 17. Patrick a demandé pourquoi. Maintenant : tout ce
        qui est en attente, sans limite de date, et on exclut sa propre
        décision (il ne se prononce pas sur lui-même)."""
        clone = self._clone()
        if not clone or not clone.clone_peut_veiller:
            return False
        Decisions = self.env["decision.fiche"].sudo()
        decisions = Decisions.search(
            [("etat", "=", "attente"),
             "|", ("origine", "!=", "Clone de Patrick"),
             ("res_model", "!=", "atelier.mission")],
            order="priorite, id", limit=40)
        matiere = "\n".join(
            "%s (priorité %s) : %s" % (d.name or "", d.priorite or "2",
                                        str(d.resume or "")[:200])
            for d in decisions)
        if not matiere:
            return False
        Mission = self.env["atelier.mission"].sudo()
        consigne = (
            "Tu es le Clone de Patrick. Voici les décisions récentes de la "
            "tour. Pour CHACUNE, décide comme le ferait Patrick (ton direct, "
            "court, sans blabla).\n\n"
            "RÉPONDS UNIQUEMENT PAR DES LIGNES, RIEN D'AUTRE — aucune "
            "intro, aucune réflexion, aucun « je vais », aucun commentaire. "
            "Juste une ligne PAR décision, au format exact :\n"
            "#<numéro> : <TA DECISION, en une phrase simple> — JUSTIF : <ta "
            "justification, en une phrase, niveau 6 ans>\n\n"
            "Règle : tu DECIDES (c'est un test d'autonomie) mais ta décision "
            "atterrit dans la file de Patrick qui la valide. Ta justification "
            "DOIT être lisible par lui sans ouvrir le détail : dis le POURQUOI "
            "en clair, pas du jargon. Ne décide pas d'une décision déjà "
            "tranchée (approuvée ou rejetée).\n"
            "Tu ne lances rien, tu ne modifies rien : tu rends des lignes.\n\n"
            "=== LES DÉCISIONS ===\n%s"
            % matiere[:5000])
        m = Mission.create({
            "name": "Clone — si j'étais Patrick (veille quotidienne)",
            "consigne": consigne,
            "moteur": clone.moteur or "deepseek-agent",
        })
        m.action_envoyer()
        _logger.info("Clone : veille déposée (%s)", m.id)
        return True
