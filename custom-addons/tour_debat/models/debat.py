# -*- coding: utf-8 -*-
"""Le débat : poser une question à un agent, ou à toute l'équipe.

Demandé par Patrick le 28/07 : « on doit pouvoir lancer un débat ou un échange
sur une idée, sur la dimension de l'agent, ou lancer un débat avec tous les
agents ».

Ce que ça change par rapport à une conversation ordinaire : **chaque agent
répond depuis SON angle**, sans voir les autres. Lois cherche ce qui casse,
Braignak regarde ce qui se fait ailleurs, Tess demande ce que ça coûte. Une
même question posée à quatre métiers donne quatre réponses qui ne se ressemblent
pas — et c'est exactement ce qu'on cherche quand on hésite.

**Ils ne se lisent pas entre eux, et c'est délibéré.** Un agent qui lit la
réponse du précédent s'y aligne : on obtient quatre variations d'un même avis,
en croyant avoir consulté quatre métiers. L'indépendance des avis est ce qui
fait la valeur du débat.

**Ce que ça coûte est annoncé.** Chaque participant consomme une mission de
l'atelier. Un débat à six agents coûte six fois un échange — c'est écrit sur
l'écran avant de lancer, pas découvert après.

**Les agents sans moteur ne débattent pas.** Victor, Jimmy et Tess sont du code
déterministe : ils n'ont pas d'avis, ils ont des mesures. Les faire « participer »
reviendrait à fabriquer une opinion qu'ils n'ont pas.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class DebatSujet(models.Model):
    _name = "debat.sujet"
    _description = "Débat avec l'équipe"
    _inherit = ["mail.thread"]
    _order = "create_date desc"

    name = fields.Char("La question", required=True,
                       help="Ce sur quoi on veut leur avis, en une phrase.")
    contexte = fields.Text(
        "Ce qu'ils doivent savoir",
        help="Ce que vous savez déjà et qui leur éviterait de le redécouvrir. "
             "Sans ça, ils repartent tous de zéro.")
    membre_ids = fields.Many2many(
        "equipe.membre", string="Qui participe",
        help="Laisser vide pour demander à tous ceux qui savent parler.")
    etat = fields.Selection(
        [("brouillon", "Brouillon"),
         ("en_cours", "Ils réfléchissent"),
         ("rendu", "Avis rendus")],
        "État", default="brouillon", readonly=True, tracking=True)

    # PRIVE PAR DEFAUT (30/07). Trouve ce jour-la : le fichier d acces
    # donnait read+write+create sur les debats a base.group_user, sans
    # aucune regle d enregistrement. Les 23 comptes internes — famille,
    # amis, clients — pouvaient donc lire ET modifier les debats de
    # strategie : ce qu on vend, a quel prix, ce qu on pense d un
    # concurrent. Un debat interne qui fuite ne se rattrape pas.
    #
    # Le choix de Patrick : tout ferme, et il ouvre a la main, un par un.
    # Une case a cocher plutot qu un reglage global — on ne publie jamais
    # par defaut, on publie par decision.
    publie = fields.Boolean(
        "Visible par toute l equipe", default=False, tracking=True,
        help="Decoche : seul l administrateur voit ce debat. Coche : tous\n"
             "les utilisateurs internes peuvent le lire (jamais le modifier).")
    avis_ids = fields.One2many("debat.avis", "sujet_id", "Les avis")
    nb_avis = fields.Integer("Avis rendus", compute="_compter")
    nb_attendus = fields.Integer("Avis attendus", compute="_compter")

    synthese = fields.Text(
        "Ce qu'on en retient",
        help="Écrit par vous, après lecture. Un débat sans conclusion écrite "
             "se rejoue trois semaines plus tard à l'identique.")

    @api.depends("avis_ids.reponse")
    def _compter(self):
        for d in self:
            d.nb_attendus = len(d.avis_ids)
            d.nb_avis = len(d.avis_ids.filtered(lambda a: a.reponse))

    # ------------------------------------------------------------------
    def _participants(self):
        """Ceux qui peuvent réellement répondre.

        Un agent sans moteur ne converse pas : il ne consomme aucune IA, par
        construction. L'inclure fabriquerait une opinion qu'il n'a pas.
        """
        self.ensure_one()
        choisis = self.membre_ids or self.env["equipe.membre"].search([])
        return choisis.filtered(lambda m: (m.moteur or "").strip())

    def action_lancer(self):
        """Dépose une mission par participant. Chacun répond sans voir les autres."""
        self.ensure_one()
        if self.etat == "en_cours":
            raise UserError(_("Ce débat est déjà en cours. Attends les avis."))
        participants = self._participants()
        if not participants:
            raise UserError(_(
                "Aucun des agents choisis ne sait converser. Victor, Jimmy et "
                "Tess sont du code déterministe : ils mesurent, ils n'ont pas "
                "d'avis. Choisis Clark, Lois ou Braignak."))
        Mission = self.env["atelier.mission"].sudo()
        for membre in participants:
            avis = self.env["debat.avis"].create({
                "sujet_id": self.id, "membre_id": membre.id})
            mission = Mission.create({
                "name": _("Débat — %(q)s (%(qui)s)",
                          q=self.name[:40], qui=membre.name),
                "consigne": avis._consigne(),
                "moteur": membre.moteur,
            })
            avis.mission_id = mission.id
            mission.action_envoyer()
        self.etat = "en_cours"
        self.message_post(body=_(
            "Débat lancé auprès de %(n)s agent(s) : %(qui)s. Chacun répond "
            "sans voir les autres — un agent qui lit la réponse du précédent "
            "s'y aligne, et on obtient des variations au lieu d'avis.",
            n=len(participants), qui=", ".join(participants.mapped("name"))))
        return True

    def action_relever(self):
        """Ramène les avis rendus. Appelée aussi par le cron."""
        for d in self:
            for avis in d.avis_ids.filtered(lambda a: not a.reponse and a.mission_id):
                m = avis.mission_id
                if m.etat in ("terminee", "echec"):
                    avis.reponse = (m.reponse or "").strip() or _("(aucune réponse)")
            if d.avis_ids and all(a.reponse for a in d.avis_ids):
                if d.etat != "rendu":
                    d.etat = "rendu"
                    d._prevenir()
                    d._verser_reponses()
        return True

    def _verser_reponses(self):
        """Chaque avis rendu laisse sa fiche dans Réponses (28/07 : « que
        toutes les questions-réponses soient notées »). Une fiche PAR AGENT,
        pas une pour le débat : c'est l'avis de Lois qu'on recherchera dans
        six mois, pas le procès-verbal complet."""
        self.ensure_one()
        if "reponse.fiche" not in self.env:
            return
        for a in self.avis_ids.filtered("reponse"):
            try:
                self.env["reponse.fiche"].sudo().create({
                    "name": ("Débat — %s" % self.name)[:120],
                    "reponse": "<pre style='white-space:pre-wrap'>%s</pre>"
                               % a.reponse[:20000],
                    "auteur": a.membre_id.name,
                    "user_id": self.create_uid.id,
                })
            except Exception:  # noqa: BLE001
                _logger.exception("Debat : fiche Reponses non creee")

    def _prevenir(self):
        self.ensure_one()
        if "tour.signal" not in self.env:
            return
        # LA COUPE PORTE SON LIEN. Patrick, 28/07 : « tous les mails sont
        # coupes et pas de lien pour voir la suite ». Un extrait sans porte
        # vers le reste est une porte fermee — le courriel de mission a eu
        # son lien a 19 h, celui-ci l'avait oublie.
        base = self.env["ir.config_parameter"].sudo().get_param(
            "web.base.url", "").rstrip("/")
        lien = "%s/web#id=%s&model=debat.sujet&view_type=form" % (
            base, self.id)
        lignes = "".join(
            "<li><b>%s</b> — %s%s</li>" % (
                a.membre_id.name, (a.reponse or "")[:200],
                "…" if len(a.reponse or "") > 200 else "")
            for a in self.avis_ids)
        self.env["tour.signal"]._signaler(
            agent="Le débat", titre=_("Les avis sont rendus : %s") % self.name[:60],
            corps_html="<p>%s agent(s) ont répondu :</p><ul>%s</ul>"
                       "<p><a href='%s'>Ouvrir le débat</a> — chaque avis "
                       "en entier, et ta case « retenu ».</p>"
                       % (len(self.avis_ids), lignes, lien),
            ton="fait")

    @api.model
    def _cron_relever(self):
        self.search([("etat", "=", "en_cours")]).action_relever()
        return True


class DebatAvis(models.Model):
    _name = "debat.avis"
    _description = "L'avis d'un agent"
    _order = "sujet_id, id"

    sujet_id = fields.Many2one("debat.sujet", required=True, ondelete="cascade",
                               index=True)
    membre_id = fields.Many2one("equipe.membre", "Agent", required=True,
                                ondelete="cascade")
    mission_id = fields.Many2one("atelier.mission", "Mission", readonly=True)
    reponse = fields.Text("Son avis", readonly=True)
    retenu = fields.Boolean(
        "Retenu", help="Cochez les avis qui ont pesé dans votre décision. "
                       "Six mois plus tard, c'est ça qu'on relit.")

    def _consigne(self):
        """La question, posée à CET agent, avec son métier en tête.

        C'est ce qui distingue un débat d'un sondage : on ne demande pas un
        avis générique, on demande l'avis de quelqu'un qui a un périmètre et
        des refus écrits.
        """
        self.ensure_one()
        m, d = self.membre_id, self.sujet_id
        import re
        def texte(html):
            t = re.sub(r"<[^>]+>", " ", str(html or ""))
            return re.sub(r"\s+", " ", t).strip()

        morceaux = [
            "Tu es %s, %s de la tour de controle." % (m.name, m.poste or ""),
            "",
            "TON METIER : %s" % (texte(m.perimetre) or "non ecrit"),
            "",
            "CE QUE TU NE FAIS PAS : %s" % (texte(m.refus) or "non ecrit"),
        ]
        if (m.consignes or "").strip():
            morceaux += ["", "CONSIGNES PERMANENTES : %s" % m.consignes.strip()]
        # Les consignes personnelles de celui qui a lance le debat.
        perso = m.consigne_de(d.create_uid) if hasattr(m, "consigne_de") else ""
        if perso:
            morceaux += ["", "CONSIGNES DE TON INTERLOCUTEUR (sous tes refus,",
                         "jamais contre eux) : %s" % perso]
        morceaux += [
            "",
            "---",
            "",
            "ON TE DEMANDE TON AVIS. Pas de construire, pas de coder : un avis.",
            "",
            "LA QUESTION : %s" % d.name,
        ]
        if (d.contexte or "").strip():
            morceaux += ["", "CE QU IL FAUT SAVOIR : %s" % d.contexte.strip()]
        morceaux += [
            "",
            "COMMENT REPONDRE",
            "- Reponds DEPUIS TON METIER, pas en general. Ce qu on veut de toi,",
            "  c est l angle que les autres n auront pas.",
            "- Sois franc. Si l idee est mauvaise de ton point de vue, dis-le et",
            "  dis pourquoi. Un avis complaisant ne sert a rien : il coute le",
            "  meme prix qu un vrai et il ne fait pas avancer.",
            "- Si la question ne concerne pas ton metier, dis-le en une phrase",
            "  plutot que d inventer une opinion.",
            "- Vingt lignes maximum. Phrases courtes, mots simples.",
            "- COMMENCE par ta conclusion, en UNE phrase qu un enfant de six",
            "  ans comprend — sans jargon. Les arguments viennent apres. La",
            "  personne qui lit dix avis d affilee retient les premieres",
            "  phrases, pas les developpements.",
            "",
            "Termine par UNE phrase : ce que tu ferais, toi.",
            "",
            "FACULTATIF — si ce debat t a appris quelque chose que tu",
            "voudrais raconter (une surprise, une lecon), ajoute a la toute",
            "fin une section :",
            "=== TEMOIGNAGE ===",
            "<deux phrases, premiere personne, du VECU>",
            "N ecris cette section QUE si tu as vraiment quelque chose a",
            "dire — un temoignage de remplissage ne sera pas retenu.",
        ]
        return "\n".join(morceaux)
