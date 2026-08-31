# -*- coding: utf-8 -*-
"""Discuter avec Clark depuis la tour, et depuis le téléphone.

Clark, c'est le nom donné à l'agent Claude Code du serveur. Un nom n'est pas
une coquetterie : on ne dit pas « je vais demander à l'agent Claude Code du
moteur discussion », on dit « je demande à Clark ». Et le jour où l'équipe
compte trois agents, on sait duquel on parle. Chloe — la bulle en bas à droite
— voit la tour ; Clark voit le code.

L'atelier confie des missions : une consigne part, un compte rendu revient, et
tout est oublié. Ici on veut l'inverse — une conversation qui se souvient, celle
qu'on a devant un terminal quand on cherche encore ce qu'on veut faire.

Le tuyau est celui de l'atelier, et pour la même raison : **la tour ne lance
aucune commande**. Elle dépose un fichier, un script de l'hôte le ramasse. Le
conteneur n'a jamais accès au terminal du serveur.

Ce qui change, c'est la mémoire. Chaque fil porte un identifiant ; le moteur
« discussion » retient la session correspondante côté serveur et la reprend à
l'échange suivant. La tour, elle, ne stocke aucun identifiant de session : elle
n'en a pas besoin, et ce qu'on ne stocke pas ne fuit pas.
"""
import logging
import os
import re
import uuid

from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

RACINE = "/mnt/atelier"
MOTEUR = "discussion"

# Ce que l'agent doit savoir avant le premier mot. Injecté une seule fois, au
# premier échange d'un fil : le répéter à chaque question gaspillerait le
# contexte que la conversation sert précisément à construire.
PREAMBULE = """Tu t'appelles Clark. C'est le nom sous lequel on te parle depuis
la tour de contrôle de Patrick : dans l'équipe, Chloe est la copilote (elle voit
les projets, les notes, le suivi) et toi tu es celui qui lit et écrit le code.
Si on te demande qui tu es, réponds Clark, sans en faire un numéro : le nom sert
à te désigner, pas à jouer un personnage. Chloe peut te confier du travail
elle-même — un message qui arrive « de la part de Chloe » vient d'elle, pas
d'un inconnu.

Tu réponds depuis la tour de contrôle de Patrick, qui te parle
depuis son navigateur ou son téléphone — il ne voit pas ton terminal.

Tu travailles dans un CLONE du dépôt de la tour, sur une branche de travail.
Ce n'est pas la production : le serveur qui fait tourner la tour est ailleurs.
Tu peux donc lire, écrire et te tromper ici. Tu ne déploies rien toi-même —
la migration vers la production est un geste humain, après relecture.

Le fichier CLAUDE.md à la racine est la mémoire du projet : lis-le avant de
répondre sur l'architecture, les pièges ou les décisions déjà prises.

Réponds en français, en texte simple : ta réponse s'affiche dans une fiche,
pas dans un terminal. Va droit au but. Si tu as besoin d'une information que
tu n'as pas, demande-la plutôt que de supposer.
"""


class DiscussionFil(models.Model):
    _name = "discussion.fil"
    _description = "Conversation avec Clark"
    _order = "write_date desc"

    name = fields.Char("Sujet", required=True, default="Nouvelle conversation",
                       help="De quoi on parle. Sert à retrouver le fil plus tard.")
    # L'identifiant qui relie ce fil à sa mémoire côté serveur. Restreint aux
    # mêmes caractères que le nom d'un moteur : pas de barre oblique, donc
    # aucun moyen d'écrire hors du dossier des sessions.
    slug = fields.Char("Identifiant", readonly=True, copy=False, index=True,
                       default=lambda self: uuid.uuid4().hex[:16])
    # À QUEL AGENT on parle.
    #
    # Le fil partait toujours vers Clark : c'était le seul agent conversationnel.
    # Patrick l'a dit en regardant l'écran Sécurité — « je vois les constats de
    # Victor mais je ne peux pas lui parler ni corriger ses consignes ». Un
    # agent auquel on ne peut rien dire n'est pas un collègue, c'est un rapport.
    #
    # On n'écrit toujours QUE des noms, jamais une commande : le nom du moteur
    # est validé côté hôte, comme avant.
    agent_id = fields.Many2one(
        "equipe.membre", "Avec qui", ondelete="set null",
        help="L'agent à qui ce fil s'adresse. Vide = Clark, par défaut.")
    moteur = fields.Char(
        "Moteur", readonly=True,
        help="Le moteur qui répond. Déduit de l'agent, jamais saisi à la main.")
    user_id = fields.Many2one("res.users", "Propriétaire", required=True,
                              default=lambda self: self.env.user,
                              readonly=True, ondelete="cascade")
    echange_ids = fields.One2many("discussion.echange", "fil_id", "Échanges")
    question = fields.Text(
        "Votre message",
        help="Ce que vous voulez dire. Le fil se souvient de tout ce qui "
             "précède : inutile de répéter le contexte.")
    autonomie = fields.Boolean(
        "Autonomie totale",
        help="Décoché, l'agent écrit des fichiers mais demande la permission "
             "pour lancer des commandes — et comme personne n'est là pour la "
             "donner, il s'arrête. Coché, il ne demande plus rien. À réserver "
             "au dépôt de travail, jamais à la production.")
    en_attente = fields.Boolean("Réponse en cours", compute="_compute_en_attente")
    nb_echanges = fields.Integer("Échanges", compute="_compute_en_attente")
    conversation = fields.Html("Conversation", compute="_compute_conversation",
                               sanitize=False)
    # La mémoire compressée (05/08, livre AI Agents in Action ch. 1 : la
    # mémoire est un composant de l'agent). « Oublier » renouvelle la session
    # côté serveur — avant, l'agent repartait amnésique ET sans préambule :
    # le premier message d'une session neuve partait nu, puisque « premier »
    # se mesurait aux échanges du fil, pas à la session.
    memoire = fields.Text(
        "Mémoire du fil précédent", readonly=True,
        help="Le résumé de la conversation d'avant le dernier « Oublier ». "
             "Réinjecté une seule fois, au premier message de la session "
             "neuve, pour que l'agent reprenne le contexte.")
    session_vierge = fields.Boolean(
        "Session à réamorcer", default=False, readonly=True,
        help="Vrai entre « Oublier » et le message suivant : le préambule "
             "et la mémoire doivent repartir.")

    @api.depends("echange_ids.reponse", "echange_ids.etat", "echange_ids.question")
    def _compute_conversation(self):
        """Le fil, rendu comme une conversation et non comme un tableau.

        Une liste de lignes tronquées est illisible dès le deuxième échange —
        or c'est précisément la lecture qui fait la différence entre « discuter »
        et « consulter des fiches ».
        """
        for fil in self:
            morceaux = []
            for echange in fil.echange_ids:
                # Tout ce qui vient de l'agent est échappé : une réponse peut
                # contenir du code, des chevrons, du HTML entier. On l'affiche,
                # on ne l'exécute pas.
                question = escape(echange.question or "").replace("\n", Markup("<br/>"))
                morceaux.append(Markup(
                    '<div style="margin:0 0 4px 0;padding:8px 12px;'
                    'background:#1e293b;border-radius:.5rem;">'
                    '<b>Moi</b><br/>%s</div>') % question)
                if echange.etat == "envoye":
                    morceaux.append(Markup(
                        '<div style="margin:0 0 16px 0;padding:8px 12px;'
                        'opacity:.7;"><i>Réponse en cours…</i></div>'))
                    continue
                couleur = "#0f172a" if echange.etat == "termine" else "#450a0a"
                reponse = escape(echange.reponse or "").replace("\n", Markup("<br/>"))
                nom_agent = (fil.agent_id.name or "Clark") if fil.agent_id else "Clark"
                morceaux.append(Markup(
                    '<div style="margin:0 0 16px 0;padding:8px 12px;'
                    'background:%s;border-radius:.5rem;border-left:3px solid #3b82f6;">'
                    '<b>%s</b> <span style="opacity:.6">(%ss)</span>'
                    '<br/>%s</div>') % (couleur, nom_agent, echange.duree or 0, reponse))
            fil.conversation = (Markup("").join(morceaux) if morceaux else
                                Markup('<p style="opacity:.6">La conversation '
                                       'commence avec votre premier message.</p>'))

    @api.depends("echange_ids.etat")
    def _compute_en_attente(self):
        for fil in self:
            fil.en_attente = any(e.etat == "envoye" for e in fil.echange_ids)
            fil.nb_echanges = len(fil.echange_ids)

    # ------------------------------------------------------------------
    @api.model
    def _atelier_pret(self):
        return os.path.isdir(os.path.join(RACINE, "missions"))

    def _moteur_effectif(self):
        """Le moteur de l'agent du fil, ou celui par défaut.

        Validé sur le même alphabet que côté hôte : pas de barre oblique, donc
        aucun moyen de désigner un script hors du dossier des moteurs.
        """
        self.ensure_one()
        nom = (self.agent_id.moteur or "").strip() if self.agent_id else ""
        if nom and re.match(r"^[a-z0-9_-]+$", nom):
            return nom
        return MOTEUR

    @api.model
    def _moteur_installe(self, nom=None):
        return os.path.isfile(
            os.path.join(RACINE, "moteurs", "%s.sh" % (nom or MOTEUR)))

    def _preambule(self):
        """Le préambule du fil : celui de SON agent, pas toujours Clark.

        La fiche d'un membre promettait « ses consignes déjà en tête » —
        c'était faux : tout fil s'ouvrait sur le préambule de Clark, quel
        que soit l'agent choisi (constaté le 29/07 : « les agents parlent
        comme des machines »). Un agent sans identité ni consignes répond
        comme un moteur nu.
        """
        self.ensure_one()
        m = self.agent_id
        if not m or (m.name or "").strip().lower() == "clark":
            return PREAMBULE
        morceaux = [
            "Tu t'appelles %s. %s — c'est ton poste dans l'équipe de la "
            "tour de contrôle de Patrick. Si on te demande qui tu es, "
            "réponds %s, sans en faire un numéro : le nom sert à te "
            "désigner, pas à jouer un personnage."
            % (m.name, (m.poste or "").strip(), m.name)]
        if (m.consignes or "").strip():
            morceaux.append("TES CONSIGNES PERMANENTES :\n%s"
                            % m.consignes.strip())
        perso = m.consigne_de(self.env.user) if hasattr(m, "consigne_de") else ""
        if perso:
            morceaux.append(
                "CONSIGNES DE TON INTERLOCUTEUR — elles s'appliquent APRÈS "
                "tes refus, jamais contre eux :\n%s" % perso)
        if (m.exemples or "").strip():
            morceaux.append(
                "EXEMPLES DE DEMANDES QUI RELÈVENT DE TOI :\n%s"
                % m.exemples.strip())
        # L'ANNUAIRE DE L'EQUIPE (31/07). Le chat doit savoir A QUI
        # transmettre une demande qui ne releve pas de son metier, et nommer
        # l'agent responsable. Test de routage du 31/07 : Chloe gardait des
        # demandes (formation, courrier) et nommait des roles vagues.
        Annuaire = self.env["equipe.membre"].sudo().search(
            [("active", "=", True)], order="id")
        if Annuaire:
            morceaux.append(
                "L'ANNUAIRE DE L'EQUIPE — qui fait quoi. Pour une demande qui "
                "ne releve pas de ton metier, nomme l'agent responsable :\n%s"
                % "\n".join(
                    "- %s : %s" % (x.name, (x.poste or x.perimetre or "membre").strip())
                    for x in Annuaire))
        morceaux.append(
            "Réponds en français, en texte simple : ta réponse s'affiche "
            "dans une fiche, pas dans un terminal. Va droit au but. Si tu "
            "as besoin d'une information que tu n'as pas, demande-la "
            "plutôt que de supposer.")
        # TA MANIÈRE DE TRAVAILLER (AI Agents in Action, 2e éd., 05/08) — bloc
        # commun appliqué à TOUS les agents du chat, pas une consigne par fiche.
        # Il cible les deux modes de panne constatés le 05/08 : tourner en
        # boucle sur le même message (stagnation) et affirmer comme sûr ce qui
        # ne l'est pas (confiance non mesurée). Voir specs/EVOLUTION-AGENTS-
        # AIAGENTSINACTION.md.
        morceaux.append(
            "TA MANIÈRE DE TRAVAILLER — s'applique à chaque réponse :\n"
            "1. Confiance : dis quand tu es SÛR et quand tu n'es PAS sûr. "
            "Si tu hésites, demande plutôt que de deviner.\n"
            "2. Pas de boucle stérile : si tu ne sais pas avancer, le dis "
            "et change de méthode. Ne répète JAMAIS ta réponse ou le même "
            "message à l'identique.\n"
            "3. Va à l'essentiel : réponds à la question posée, pas à côté. "
            "Ce que tu affirmes se prouve par un fait ou un outil, pas par "
            "une simple affirmation.\n"
            "4. Finis par une PROPOSITION, jamais par un constat seul. Si ce "
            "que tu as trouve demande une decision, donne AU MOINS DEUX choix, "
            "ce que chacun apporte et ce qu il coute, et dis lequel tu "
            "recommandes et pourquoi. Un constat sans proposition, c est du "
            "travail que tu repasses a Patrick.")
        return "\n\n".join(morceaux)

    def action_envoyer(self):
        """Dépose le message. La réponse arrivera dans la minute."""
        self.ensure_one()
        texte = (self.question or "").strip()
        if not texte:
            raise UserError(_("Écrivez quelque chose avant d'envoyer."))
        if not self._atelier_pret():
            raise UserError(_(
                "L'atelier n'est pas accessible depuis l'application (%s). "
                "Vérifier que le dossier partagé est monté dans le conteneur.",
                RACINE))
        moteur = self._moteur_effectif()
        if not self._moteur_installe(moteur):
            raise UserError(_(
                "Le moteur « %s » n'est pas installé sur le serveur. Il se "
                "copie depuis deploy/moteurs/ vers ~/atelier/moteurs/.", moteur))
        if self.agent_id and not self.agent_id.active:
            raise UserError(_(
                "%s est éteint : rallume-le avant de lui écrire.",
                self.agent_id.name))
        if self.en_attente:
            raise UserError(_(
                "Une réponse est déjà en route. Attendez-la avant d'envoyer "
                "la suite — sinon les deux messages se croiseraient."))

        premier = self._premier_envoi()
        jeton = uuid.uuid4().hex[:16]
        corps = self._corps(texte, premier)

        chemin = os.path.join(RACINE, "missions", "%s.txt" % jeton)
        # On n'écrit que des NOMS : celui du moteur, celui du fil. Jamais une
        # commande — c'est le point de sécurité de tout le dispositif.
        # Le moteur utilisé est celui de l'agent (calculé par _moteur_effectif),
        # pas le MOTEUR par défaut : sinon un agent avec son propre moteur
        # (Raphaël, Jonathan…) validerait mais partirait sur le mauvais script.
        with open(chemin, "w", encoding="utf-8") as f:
            f.write("#!moteur: %s\n" % moteur)
            f.write("#!fil: %s\n" % self.slug)
            if self.autonomie:
                f.write("#!autonomie: totale\n")
            f.write(corps)

        self.moteur = moteur
        self.env["discussion.echange"].create({
            "fil_id": self.id,
            "question": texte,
            "jeton": jeton,
            "etat": "envoye",
        })
        # Le sujet par défaut ne dit rien : la première question, si.
        vals = {"question": False, "session_vierge": False}
        if premier and self.name in (False, "Nouvelle conversation"):
            vals["name"] = texte[:60] + ("…" if len(texte) > 60 else "")
        self.write(vals)
        return True

    def _premier_envoi(self):
        """Premier message de la SESSION, pas du fil.

        Après « Oublier », la session serveur est neuve : le préambule doit
        repartir même si le fil affiche déjà des échanges. Avant le 05/08,
        « premier » se mesurait aux échanges — l'agent repartait nu.
        """
        self.ensure_one()
        return not self.echange_ids or self.session_vierge

    def _corps(self, texte, premier):
        """Le message tel qu'il part : préambule et mémoire au premier envoi."""
        self.ensure_one()
        if not premier:
            return texte
        morceaux = [self._preambule()]
        if (self.memoire or "").strip():
            morceaux.append(
                "MÉMOIRE DU FIL PRÉCÉDENT — le résumé de ce qu'on s'est "
                "déjà dit, pour reprendre sans tout relire :\n%s"
                % self.memoire.strip())
        # COMPÉTENCE TRANSFERT (Jiritsu Denshō, 05/08) : en début de session,
        # l'agent recharge la mémoire de la tour avant de répondre. Sans ce
        # geste, il répond de sa mémoire de session (éventuellement périmée) —
        # c'était le trou « écrit ≠ posé » : les connaissances du chat ne lui
        # arrivaient qu'au bouton manuel. Ici le rechargement est automatique.
        morceaux.append(
            "TRANSFERT DE MÉMOIRE (début de session) : avant de répondre, "
            "si tu as accès au dépôt, ouvre /home/ubuntu/tour/SESSION.md — le "
            "VRAI fichier, pas ton clone — et lis-en les entrées récentes pour "
            "être à jour de ce que la tour a appris. Si tu n'as pas d'accès, "
            "dis-le plutôt que d'inventer. Puis réponds.")
        return "%s\n---\n%s" % ("\n\n".join(morceaux), texte)

    def _resumer_fil(self):
        """La conversation en court, pour la mémoire compressée.

        On réutilise le moteur de condensation (coupe d'abord, IA en
        recours) ; sans lui, la fin de la conversation fait l'affaire.
        """
        self.ensure_one()
        morceaux = []
        for e in self.echange_ids.filtered(lambda e: e.etat == "termine"):
            morceaux.append("Moi : %s" % (e.question or "")[:400])
            morceaux.append("Lui : %s" % (e.reponse or "")[:400])
        if not morceaux:
            return ""
        texte = "\n".join(morceaux)
        if "condense.engine" in self.env:
            resume = self.env["condense.engine"]._resumer(texte)[0]
            if resume:
                return resume
        return texte[-800:]

    def action_recharger_memoire(self):
        """Demande à l'agent de RELIRE la mémoire de la tour (SESSION.md).

        Patrick, 31/07 : un bouton pour « recharger la mémoire de Raphaël ».
        Le chat travaille dans son clone (~/agent/raphael) ; sa mémoire peut
        prendre du retard sur le vrai dépôt. Ce bouton envoie un message qui
        force la relecture du VRAI fichier (chemin absolu), plutôt que de
        laisser l'agent répondre de ce qu'il croit savoir.

        Fonctionne le mieux avec « Autonomie totale » cochée (l'agent doit
        pouvoir ouvrir le fichier). Ne coûte rien de plus qu'un message.
        """
        self.ensure_one()
        if self.en_attente:
            raise UserError(_(
                "Une réponse est déjà en route. Attendez-la avant de "
                "recharger la mémoire."))
        note = ("RECHARGE DE MEMOIRE (demandée par Patrick) : oublie ce que "
                "tu crois savoir de l'état de la tour. Ouvre le fichier "
                "/home/ubuntu/tour/SESSION.md — le VRAI dépôt, pas ton clone "
                "— et lis-le EN ENTIER. Confirme en une ligne ce qui a changé "
                "depuis ta dernière lecture, puis reste disponible. Ne fais "
                "rien d'autre.")
        premier = not self.echange_ids
        self.question = note
        try:
            if premier:
                self.name = "Rechargement de mémoire"
            self.action_envoyer()
        finally:
            self.question = False
        return True

    def action_relever(self):
        """Va chercher les réponses prêtes."""
        for fil in self:
            fil.echange_ids.filtered(lambda e: e.etat == "envoye")._relever()
        return True

    def action_oublier(self):
        """Repart d'une conversation neuve, en gardant l'historique affiché.

        On change d'identifiant plutôt que d'effacer la session sur le serveur :
        la tour n'a pas à aller fouiller dans les fichiers de l'hôte, et un fil
        dont on a perdu le fil vaut mieux qu'un fil supprimé par erreur.

        Depuis le 05/08, oublier n'est plus une amnésie : un résumé du fil
        est gardé et repartira avec le premier message de la session neuve.
        """
        self.ensure_one()
        resume = self._resumer_fil()
        self.write({
            "slug": uuid.uuid4().hex[:16],
            "session_vierge": True,
            **({"memoire": resume} if resume else {}),
        })
        return True

    @api.model
    def _cron_relever(self):
        en_cours = self.env["discussion.echange"].sudo().search(
            [("etat", "=", "envoye")])
        en_cours._relever()


class DiscussionEchange(models.Model):
    _name = "discussion.echange"
    _description = "Un aller-retour dans une conversation"
    _order = "id asc"

    fil_id = fields.Many2one("discussion.fil", "Fil", required=True,
                             ondelete="cascade", index=True)
    question = fields.Text("Message", readonly=True)
    reponse = fields.Text("Réponse", readonly=True)
    jeton = fields.Char("Identifiant", readonly=True, copy=False)
    etat = fields.Selection(
        [("envoye", "En cours"), ("termine", "Reçue"), ("echec", "Échec")],
        string="État", default="envoye", readonly=True)
    duree = fields.Integer("Durée (s)", readonly=True)

    def _relever(self):
        for echange in self:
            if echange.etat != "envoye" or not echange.jeton:
                continue
            base = os.path.join(RACINE, "resultats", echange.jeton)
            if not os.path.exists(base + ".txt"):
                continue
            try:
                with open(base + ".txt", encoding="utf-8", errors="replace") as f:
                    reponse = f.read()
                code, duree = 0, 0
                if os.path.exists(base + ".meta"):
                    with open(base + ".meta", encoding="utf-8") as f:
                        morceaux = (f.read() or "0 0").split()
                        code = int(morceaux[0]) if morceaux else 0
                        duree = int(morceaux[1]) if len(morceaux) > 1 else 0
            except OSError as exc:
                echange.write({"etat": "echec",
                               "reponse": _("Lecture impossible : %s", exc)})
                continue
            echange.write({
                "reponse": reponse[:60000],
                "duree": duree,
                "etat": "termine" if code == 0 else "echec",
            })
