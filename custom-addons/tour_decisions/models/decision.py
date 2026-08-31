# -*- coding: utf-8 -*-
"""Décisions — la deuxième des trois portes.

Patrick, le 28/07 : « l'utilisateur voit le tableau de bord, décide dans
Décisions, et parle à Chloe ». Et sa règle, née d'une journée à approuver en
console : « tout ça doit être dans le module Décisions, faire en console c'est
chiant » — pour lui comme pour les utilisateurs, avec la notification sur
l'accueil.

Le principe qui évite les deux vérités : **une fiche de décision ne porte que
la décision et un pointeur**. L'enregistrement d'origine (mission, constat,
tâche) reste seul maître de son contenu. Approuver ou rejeter agit sur
l'origine ; le commentaire de rejet part dans son fil, là où l'agent
concerné le lira.

Le rabatteur ramasse ce qui attend une décision partout dans la tour. Il est
IDEMPOTENT : une origine déjà représentée n'est jamais dupliquée — sans quoi
chaque passage recréerait la pile et l'écran mentirait sur le nombre.
"""

import logging
import os

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Le canal des ordres vers l'hôte : le MÊME que l'atelier — la tour dépose un
# fichier, un cron de l'hôte le ramasse. Jamais une commande, seulement un nom.
DOSSIER_ORDRES = "/mnt/atelier/ordres"

# Combien de fois une mission peut être renvoyée à l'agent après un rejet.
# La même valeur que celle du champ atelier.mission.repropositions (module
# tour_atelier) : là-bas elle documente, ici elle borne.
MAX_REPROPOSITIONS = 3


class DecisionFiche(models.Model):
    _name = "decision.fiche"
    _description = "Une décision qui t'attend"
    _inherit = ["mail.thread"]
    _order = "etat, priorite, create_date desc"

    name = fields.Char("Ce qu'on te demande", required=True)
    origine = fields.Char("Qui le demande",
                          help="L'agent ou le module d'où ça vient.")
    # Libellé lisible (09/08, Patrick) : « Circuit (… » ne disait rien à
    # personne. Un agent qui passe une porte, ça s'appelle une DEMANDE.
    origine_lisible = fields.Char("Qui le demande (lisible)",
                                  compute="_compute_lisible", store=False)
    titre_lisible = fields.Char("Ce qu'on te demande (sans le préfixe)",
                                compute="_compute_lisible", store=False)
    resume = fields.Html("Le contexte, en bref")

    # Le pointeur — jamais une copie du contenu.
    res_model = fields.Char("Modèle d'origine", index=True)
    res_id = fields.Integer("Enregistrement d'origine", index=True)

    etat = fields.Selection(
        [("attente", "À décider"),
         ("approuve", "Approuvé"),
         ("rejete", "Rejeté"),
         ("archive", "Archivée")],
        "État", default="attente", required=True, tracking=True, index=True)

    # LA PRIORITÉ DES DÉCISIONS (Patrick, 29/07 : « créer ce concept sur le
    # coup, c'est super important »). Une pile où tout se vaut oblige à
    # tout lire pour trouver ce qui presse — et ce qui presse finit sous ce
    # qui est arrivé après. Le tri se fait donc DANS la pile, jamais dans la
    # tête. Trois niveaux, pas cinq : au-delà, plus personne ne sait ce que
    # « moyen-haut » veut dire. « Ça bloque » est réservé à ce qui arrête un
    # travail ou expose quelqu'un — la sécurité y va d'office.
    priorite = fields.Selection(
        [("1", "Ça bloque"),
         ("2", "Important"),
         ("3", "Quand tu peux")],
         "Priorité", default="3", required=True, index=True, tracking=True)
    commentaire = fields.Text(
        "Ton commentaire (si rejet)",
        help="Écris ce qui ne va pas : il part dans le fil de l'origine, et "
             "si un agent est derrière, il s'en servira pour reproposer.")
    decide_le = fields.Datetime("Décidé le", readonly=True)

    # À qui la décision appartient. C'est ce champ qui rend le module
    # utilisable par les utilisateurs : chacun ne voit que les siennes.
    user_id = fields.Many2one(
        "res.users", "Décideur", required=True, index=True,
        default=lambda self: self.env.user)

    # L'écran doit DIRE quand le commentaire sert à répondre, pas à rejeter.
    # Bug du 28/07 (fiche 14, Nihongo) : le cadre s'appelait « Si tu
    # rejettes, dis pourquoi » — Patrick a donc écrit ses réponses dans le
    # fil de discussion, approuvé, et reçu « Opération invalide ». Le
    # libellé contredisait le mécanisme ; un utilisateur ne lit pas le
    # code, il lit les titres.
    attend_reponses = fields.Boolean(compute="_compute_attend_reponses")

    @api.depends("origine", "name")
    def _compute_lisible(self):
        for d in self:
            o = d.origine or "La tour"
            if "Circuit" in o:
                o = o.replace("Circuit", "Demande d'un agent")
            d.origine_lisible = o
            nom = d.name or ""
            nom = nom.replace("Circuit", "Demande d'un agent")
            if nom.startswith("Demande d'un agent"):
                idx = nom.find(" : ")
                if idx != -1:
                    nom = nom[idx + 3:]
            d.titre_lisible = nom

    def _compute_attend_reponses(self):
        for d in self:
            o = d._origine()
            d.attend_reponses = bool(
                o is not None and d.res_model == "atelier.mission"
                and getattr(o, "besoins", False))

    _sql_constraints = [
        ("origine_unique", "unique(res_model, res_id)",
         "Cette origine a déjà sa fiche de décision."),
    ]

    # ------------------------------------------------------------------
    def action_ouvrir_origine(self):
        """Voir la chose elle-même, pas sa fiche."""
        self.ensure_one()
        if not (self.res_model and self.res_id):
            raise UserError(_("Cette décision n'a pas d'origine liée."))
        return {"type": "ir.actions.act_window",
                "res_model": self.res_model,
                "res_id": self.res_id,
                "view_mode": "form"}

    def _origine(self):
        self.ensure_one()
        if self.res_model and self.res_model in self.env and self.res_id:
            rec = self.env[self.res_model].sudo().browse(self.res_id)
            return rec if rec.exists() else None
        return None

    def action_approuver(self):
        for d in self:
            origine = d._origine()
            # L'approbation AGIT, elle ne note pas : c'est toute la
            # différence avec un simple statut.
            if origine is not None:
                if d.res_model == "atelier.mission" and origine.etat == "brouillon":
                    origine.action_envoyer()
                elif (d.res_model == "atelier.mission"
                      and origine.besoins):
                    # L'agent etait bloque : approuver = lui repondre. Le
                    # commentaire porte les reponses, la suite rouvre SON
                    # chantier.
                    if not (d.commentaire or "").strip():
                        raise UserError(_(
                            "Cet agent attend des reponses : ecris-les dans "
                            "le commentaire, puis approuve."))
                    act = origine.action_continuer()
                    suite = self.env["atelier.mission"].sudo().browse(
                        act["res_id"])
                    suite.consigne = (
                        "TES QUESTIONS ONT RECU REPONSE. Tu avais dit qu'il "
                        "te manquait :\n\n%s\n\nVOICI LES REPONSES DU "
                        "DECIDEUR :\n\n%s\n\nReprends et termine le travail "
                        "d'origine avec ces reponses." % (
                            origine.besoins, d.commentaire))
                    suite.action_envoyer()
                elif d.res_model == "securite.constat":
                    origine.write({"etat": "accepte"})
                elif d.res_model == "project.task" and origine.name.startswith("[À CONFIRMER]"):
                    # Confirmée : elle perd son préfixe et devient une tâche
                    # ordinaire — plus rien ne la distingue d'un travail admis.
                    origine.write({"name": origine.name.replace("[À CONFIRMER]", "").strip()})
                elif d.res_model == "equipe.recrutement":
                    # APPROUVER EMBAUCHE. Le commentaire porte le nom : c'est
                    # Patrick qui nomme, et un agent qu'il a nomme lui-meme a
                    # droit a son histoire publiee (regle du 29/07).
                    #
                    # PIÈGE (08/08, payé sur Malo) : quand Patrick approuve en
                    # cliquant le bouton sans écrire de nom, le commentaire
                    # vaut « APPROUVER » (le libellé du bouton) et l'agent
                    # naissait nommé « APPROUVER ». On ne nomme pas un agent
                    # avec le nom du bouton : on retombe sur le nom proposé
                    # par le poste (nom_propose du recrutement), jamais sur
                    # un libellé d'interface.
                    nom_candidat = (d.commentaire or "").strip().splitlines()
                    nom = nom_candidat[0] if nom_candidat else None
                    if not nom or nom.upper() in (
                            "APPROUVER", "APPROUVE", "VALIDER", "OK"):
                        nom = (origine.nom_propose or "").strip() or None
                    origine.action_embaucher(nom=nom)
                elif d.res_model == "reponse.fiche":
                    # Une étude approuvée devient un travail : la tâche porte
                    # la direction du décideur (son commentaire) et le lien
                    # vers l'étude — jamais une copie de l'étude.
                    Tache = self.env["project.task"].sudo()
                    titre_t = ("Donner suite : %s" % (origine.name or ""))[:120]
                    if not Tache.search([("name", "=", titre_t)], limit=1):
                        base = self.env["ir.config_parameter"].sudo(
                            ).get_param("web.base.url", "").rstrip("/")
                        vals = {
                            "name": titre_t, "project_id": 1,
                            "description": (
                                # CHAÎNON AUTOMATIQUE (31/07) : approuver
                                # crée la tâche ET la passe d'office en
                                # « En cours » — le ramasseur de l'atelier
                                # la prend au passage suivant. Plus aucun
                                # geste manuel entre l'approbation et la
                                # forge.
                                "<p style='background:#dcfce7;border-left:4px "
                                "solid #22c55e;padding:.5rem .7rem;"
                                "border-radius:.3rem'>"
                                "<b>CONSTRUCTION AUTOMATIQUE :</b> cette tâche "
                                "a été envoyée d'office en « En cours ». "
                                "L'atelier va la forger au prochain passage, "
                                "sans autre geste de ta part. (Pour construire "
                                "sans Claude : bouton « Basculer sur "
                                "DeepSeek » sur l'accueil.)</p>"
                                "<p><b>Direction du décideur :</b> %s</p>"
                                "<p><a href='%s/web#id=%s&amp;model=reponse."
                                "fiche&amp;view_type=form'>Lire l'étude "
                                "complète</a></p>"
                                "<p>PROMPT AGENT : lire la fiche "
                                "Réponses n° %s de la tour (étude de "
                                "Braignak) et exécuter la direction du "
                                "décideur ci-dessus ; si elle est vide, "
                                "proposer la plus petite suite utile en "
                                "tâche [À CONFIRMER].</p>"
                                % (d.commentaire or "(aucune — proposer la "
                                   "plus petite suite utile)",
                                   base, origine.id, origine.id)),
                        }
                        tag = self.env["project.tags"].sudo().search(
                            [("name", "=", "Claude")], limit=1)
                        if tag:
                            vals["tag_ids"] = [(4, tag.id)]
                        tache = Tache.create(vals)
                        # LE CHAÎNON AUTOMATIQUE (31/07) : la tâche part
                        # d'office en « En cours », ce qui arme le ramasseur
                        # (tour_agent) qui dépose la mission à l'atelier.
                        # Avant, Patrick devait déplacer la tâche d'étape à la
                        # main — le maillon qui tombait à chaque fois.
                        encours = self.env["project.task.type"].sudo().search(
                            [("name", "in", ["En cours", "In Progress"])],
                            limit=1)
                        if encours and tache.stage_id != encours:
                            tache.stage_id = encours.id
                            tache.message_post(body=_(
                                "Chaînon automatique : décision approuvée → "
                                "tâche passée d'office en « En cours » — "
                                "l'atelier va forger au prochain passage."))
                if hasattr(origine, "message_post"):
                    origine.message_post(body=_(
                        "Approuvé par %s depuis l'écran Décisions.",
                        d.env.user.name))
            # LA MISE EN PROD DE LA VITRINE : approuver PUBLIE. Règle de
            # Patrick (28/07) : « pas de décision automatique pour ça » — la
            # copie essai -> production n'a lieu qu'ici. La fiche n'a pas
            # d'enregistrement d'origine : l'origine est un dossier de
            # fichiers sur l'hôte. On dépose donc un ORDRE — un fichier,
            # jamais une commande — que le cron de l'atelier ramasse dans la
            # minute ; c'est lui qui lance `vitrine.sh --prod`.
            if d.res_model == "vitrine.prod":
                try:
                    os.makedirs(DOSSIER_ORDRES, exist_ok=True)
                    chemin = os.path.join(DOSSIER_ORDRES, "vitrine-prod.ordre")
                    with open(chemin, "w", encoding="utf-8") as fh:
                        fh.write("approuve par uid %s le %s\n"
                                 % (d.env.user.id, fields.Datetime.now()))
                except OSError as exc:
                    raise UserError(_(
                        "Impossible de déposer l'ordre de publication : %s",
                        exc))
                d.message_post(body=_(
                    "Ordre de publication déposé — la production sera copiée "
                    "dans la minute, puis vérifiée page par page."))
            d.write({"etat": "approuve", "decide_le": fields.Datetime.now()})
        return True

    def action_rejeter(self):
        for d in self:
            if not (d.commentaire or "").strip():
                raise UserError(_(
                    "Écris d'abord un commentaire : un rejet muet n'apprend "
                    "rien à personne, et l'agent ne pourra pas reproposer."))
            origine = d._origine()
            if origine is not None:
                if hasattr(origine, "message_post"):
                    origine.message_post(body=_(
                        "Rejeté par %(qui)s : %(motif)s",
                        qui=d.env.user.name, motif=d.commentaire))
                if d.res_model == "project.task":
                    origine.write({"active": False})
                elif d.res_model == "equipe.recrutement":
                    # Un poste refuse ne revient pas. Le detecteur ne le
                    # reproposera plus : une question refusee qui repasse
                    # chaque nuit finit par ne plus etre lue du tout.
                    origine.action_refuser()
                elif d.res_model == "securite.constat":
                    origine.write({"etat": "refuse"})
                elif d.res_model == "atelier.mission":
                    # Le rejet commenté RELANCE l'agent : une nouvelle
                    # mission brouillon portant tes remarques, qu'il
                    # retravaillera — c'est la boucle demandée par Patrick.
                    #
                    # BORNÉE depuis le 31/07. Avant, chaque rejet relançait
                    # sans compteur : un rejet répété des mêmes remarques
                    # finissait par relancer l'agent pour la dixième fois,
                    # avec un coût de jetons que personne n'avait décidé.
                    # Au-delà de MAX_REPROPOSITIONS, le rejet ne relance
                    # plus : la décision le dit en clair, et la consigne
                    # d'origine est à corriger, pas à re-rejeter.
                    Mission = self.env["atelier.mission"].sudo()
                    if origine.repropositions >= MAX_REPROPOSITIONS:
                        origine.message_post(body=_(
                            "Rejeté par %(qui)s : %(motif)s. Aucune nouvelle "
                            "reproposition : cette mission a déjà été renvoyée "
                            "%(n)s fois. Corriger la consigne d'origine ou "
                            "repartir d'une mission neuve.",
                            qui=d.env.user.name, motif=d.commentaire,
                            n=origine.repropositions))
                    else:
                        Mission.create({
                            "name": _("Reproposition : %s",
                                      origine.name[:50]),
                            "moteur": origine.moteur,
                            "precedente_id": origine.id,
                            "repropositions": origine.repropositions + 1,
                            "consigne": (
                                "TA PROPOSITION PRECEDENTE A ETE REJETEE, "
                                "avec ce commentaire du decideur :\n\n%s\n\n"
                                "---\n\nLA PROPOSITION D'ORIGINE ETAIT :\n\n"
                                "%s\n\n"
                                "Repropose en tenant compte du commentaire. "
                                "Si le commentaire rend la chose impossible, "
                                "dis-le au lieu de forcer."
                                % (d.commentaire, origine.consigne or "")),
                        })
            d.write({"etat": "rejete", "decide_le": fields.Datetime.now()})
        return True

    def action_archiver(self):
        """Classe une décision sans l'approuver ni la rejeter.

        Patrick, 31/07 : certaines demandes tournent en rond parce que
        personne ne comprend de quoi elles parlent (ex. le cycle de la
        tâche 815). Approuver les relaierait, rejeter les relancerait
        (reproposition). Archiver les range : la fiche quitte la pile
        « À décider » sans déclencher aucun geste sur l'origine. Le
        commentaire explique pourquoi — c'est ce qui évite de ré-archiver
        la même chose sans réfléchir.
        """
        for d in self:
            if not (d.commentaire or "").strip():
                raise UserError(_(
                    "Dis pourquoi tu classes cette décision (incompréhensible, "
                    "hors sujet, doublon…) : une archive muette renaîtra au "
                    "prochain rabattage, et on boucle."))
            if d.etat != "attente":
                continue
            origine = d._origine()
            if origine is not None and hasattr(origine, "message_post"):
                origine.message_post(body=_(
                    "Décision classée sans suite par %(qui)s : %(motif)s.",
                    qui=d.env.user.name, motif=d.commentaire))
            d.write({"etat": "archive", "decide_le": fields.Datetime.now()})
        return True


    # ------------------------------------------------------------------
    @api.model
    def _rabattre(self):
        """Ramasse tout ce qui attend une décision, sans jamais dupliquer."""
        admin = self.env.ref("base.user_admin")

        def decideur_de(rec):
            """La décision appartient à celui qui a demandé le travail.

            Patrick, 29/07 : « toutes les réponses dans Décisions —
            vérifie que cela s'applique à tous les utilisateurs ». Avant,
            tout allait à l'admin : la question d'un invité sur SON app se
            décidait sans lui. Désormais le créateur de l'origine reçoit
            sa fiche (il ne voit que les siennes, l'admin voit tout) ; les
            comptes techniques et les admins retombent sur l'admin.
            """
            u = getattr(rec, "create_uid", None)
            if (u and u.active and not u.share
                    and (u.login or "") not in ("admin", "odoo", "default",
                                                "__system__")
                    and not u.has_group("base.group_system")):
                return u
            return None

        def poser(res_model, res_id, name, origine, resume, user=None,
                  priorite="2"):
            if self.sudo().search_count([("res_model", "=", res_model),
                                         ("res_id", "=", res_id)]):
                return
            self.sudo().create({
                "name": name[:200], "origine": origine, "resume": resume,
                "res_model": res_model, "res_id": res_id,
                "priorite": priorite,
                "user_id": (user or admin).id})

        # 1. Les missions en brouillon (celles des agents, pas les tiennes en
        #    cours d'écriture : on ne rabat que ce qui a plus de 10 minutes,
        #    sinon l'écran te réclame une décision sur ta propre saisie).
        def demande_seule(consigne):
            """La DEMANDE, pas le protocole.

            Le 28/07, une fiche montrait « CE QUE TU PEUX FAIRE... CE QUE TU
            NE PEUX PAS FAIRE... » — le règlement intérieur de l'agent, collé
            dans l'écran du décideur. Patrick : « je ne comprends pas ça ».
            Le décideur doit lire ce qu'on va demander, pas comment l'agent
            doit se tenir. On coupe donc au marqueur de la demande quand il
            existe, et on saute les lignes d'en-tête en capitales sinon.
            """
            c = str(consigne or "")
            for marque in ("=== LA DEMANDE ===", "LA DEMANDE :", "LA DEMANDE"):
                i = c.find(marque)
                if i >= 0:
                    c = c[i + len(marque):]
                    break
            lignes = [l for l in c.splitlines()
                      if l.strip() and not (l.strip() == l.strip().upper()
                                            and len(l.strip()) > 12)]
            return " ".join(lignes)[:400]

        if "atelier.mission" in self.env:
            il_y_a_10min = fields.Datetime.subtract(
                fields.Datetime.now(), minutes=10)
            for m in self.env["atelier.mission"].sudo().search(
                    [("etat", "=", "brouillon"),
                     ("create_date", "<", il_y_a_10min)]):
                poser("atelier.mission", m.id,
                      "Envoyer la mission : %s" % m.name,
                      "L'atelier",
                      "<p>%s</p><p style='color:#64748b'>« Voir l'origine » "
                      "montre la consigne complète.</p>"
                      % demande_seule(m.consigne),
                      user=decideur_de(m))

        # 1 bis. Les agents BLOQUES proprement : leur « il me manque »
        #    devient une decision — tes reponses les relancent sur le MEME
        #    chantier, fichiers retrouves (l'en-tete #!chantier fait le
        #    reste). C'est la reponse a « qui controle ce genre de blocage »
        #    (Patrick, 28/07, mission 54 du billet Nantes-Brest).
        def besoins_clairs(besoins):
            """Le bloc « il me manque » d'un agent, reformule lisible.
 
            L'agent ecrit « - Le fichier X : sans lui je ne peux pas
            verifier, seulement supposer, et blabla ». Le decideur veut
            le BESOIN, pas la justification. On garde le debut de chaque
            ligne, coupe a la premiere coupure (», sans », « — sans »,
            « : sans », « (», point-virgule), et on retire le remplissage.
            """
            def esc(t):
                return (t.replace("&", "&amp;").replace("<", "&lt;")
                         .replace(">", "&gt;"))
            lignes = []
            for l in str(besoins or "").splitlines():
                t = l.strip().lstrip("-*•").strip()
                if not t:
                    continue
                for coupure in (" — sans", " : sans", ", sans", " (",
                                " (sans", " pour réellement", " et "):
                    i = t.find(coupure)
                    if i > 10:
                        t = t[:i]
                        break
                t = t.strip(" .,;:-—").strip()
                if t and (not lignes or t != lignes[-1]):
                    lignes.append(esc(t))
            return lignes
 
        def titre_bloque(m):
            """Un titre court : l'agent et le sujet, sans les imbrications.
 
            « Circuit — Braignak relit : Suite — Débat : Un Claude-console »
            devient « Braignak bloqué — Un Claude-console dans la tour ».
            « Braignak — étudier Création app » devient « Braignak bloqué —
            étudier Création app ».
            """
            nom = (m.name or "")
            # l'agent : apres « relit : » ou le nom du moteur
            agent = (m.moteur or "").capitalize()
            if "relit :" in nom:
                agent = nom.split("relit :")[0].split("—")[-1].strip()
            elif "—" in nom:
                agent = nom.split("—")[0].strip()
            if (agent or "").lower() in ("lecture-seule", "lecture seule",
                                         "none", "aucun", ""):
                agent = "Agent"
            # le sujet : apres le dernier « : », sinon apres le tiret
            if ":" in nom:
                sujet = nom.split(":")[-1].strip()
            elif "—" in nom:
                sujet = "—".join(nom.split("—")[1:]).strip()
            else:
                sujet = nom
            for pref in ("[À CONFIRMER] ", "Suite — ", "Débat — ",
                         "Debat — ", "Ecrire ", "Faire "):
                if sujet.startswith(pref):
                    sujet = sujet[len(pref):]
            sujet = sujet.strip(" —:")[:60]
            return "%s bloqué — %s" % (agent, sujet)
 
        if "atelier.mission" in self.env:
            for m in self.env["atelier.mission"].sudo().search(
                     [("besoins", "!=", False),
                      ("etat", "=", "echec"),
                      ("suite_ids", "=", False)]):
                manques = besoins_clairs(m.besoins)
                items = "".join(
                    "<li>%s</li>" % b for b in manques[:6])
                # L'agent n'a R I E N qui lui manque : sa mission « besoin »
                # est en fait un avis rendu. Poser une decision « bloqué »
                # dessus demanderait a Patrick de repondre a un vide — il
                # n a rien a donner. On archive directement : la mission
                # est terminee, il n y a personne a relancer.
                # (Patrick, 06/08 : « on est oblige d entrer dans origine
                # pour comprendre certaines decisions » — le cas « rien »
                # en etait la cause n 1.)
                brut = (m.besoins or "").strip().lower()
                rien = ("rien" in brut[:60]
                        or brut.startswith("aucun")
                        or brut.startswith("- aucun"))
                if rien and not any(
                        c in brut for c in ("manque", "il me faut",
                                            "besoin", "accès",
                                            "acces", "le fichier",
                                            "le numero", "la page")):
                    poser("atelier.mission", m.id,
                          titre_bloque(m) + " — avis rendu",
                          "L'atelier",
                          "<p>Cet agent a <b>rendu son avis sans rien "
                          "demander</b> : la mission est terminee, il n'y a "
                          "personne a relancer. <b>Archiver</b> pour classer."
                          "</p>",
                          user=decideur_de(m),
                          priorite="3")
                    continue
                poser("atelier.mission", m.id,
                      titre_bloque(m),
                      "L'atelier",
                      "<p><b>Cet agent est bloqué</b> — il attend que tu "
                      "lui donnes ce qui manque :</p>"
                      "<ul style='padding-left:1.1rem;margin:.4rem 0'>"
                      "%s</ul>"
                      "<p style='color:#64748b'>Écris tes réponses dans le "
                      "commentaire puis <b>Approuver</b> : il repartira sur "
                      "le même chantier. « Voir l'origine » montre tout.</p>"
                      % items,
                      user=decideur_de(m))
 
        # 1 ter. Les études de Braignak deviennent des décisions d'office.
        #    Patrick, 28/07, devant le courriel d'une étude : « ce mail sera
        #    traité automatiquement ? » — consigné oui, mais personne ne
        #    décidait d'en faire quelque chose. Désormais chaque étude
        #    terminée pose sa fiche : APPROUVER crée la tâche « Donner
        #    suite » (le commentaire devient la direction), REJETER classe.
        #    On pointe la fiche RÉPONSES de l'étude (pas la mission) : le
        #    texte complet est à un clic, et ça évite de percuter la fiche
        #    de décision que la mission a pu avoir en brouillon.
        #    Seules les études POSTÉRIEURES à la mise en place comptent :
        #    rabattre les treize études passées d'un coup ferait un mur.
        if "reponse.fiche" in self.env:
            ICP = self.env["ir.config_parameter"].sudo()
            depuis = ICP.get_param("tour_decisions.braignak_depuis")
            if not depuis:
                depuis = fields.Datetime.to_string(fields.Datetime.now())
                ICP.set_param("tour_decisions.braignak_depuis", depuis)
            import re as _re
            # PAS les avis de debats : un avis n'est pas une etude, et le
            # moissonneur en fabriquait des doublons (4 fiches de bruit le
            # 29/07, nettoyees a la main pendant que Patrick allait decider).
            for r in self.env["reponse.fiche"].sudo().search(
                    [("auteur", "=", "Braignak"),
                     ("name", "not like", "Débat —%"),
                     ("create_date", ">=", depuis)]):
                titre = _re.sub(r"^Braignak\s*[—-]*\s*observer\s*", "",
                                r.name or "").strip() or (r.name or "")
                texte = _re.sub(r"<[^>]+>", " ", str(r.reponse or ""))
                texte = _re.sub(r"\s+", " ", texte).strip()[:350]
                poser("reponse.fiche", r.id,
                      "Étude de Braignak : %s — on s'en sert ?" % titre[:120],
                      "Braignak",
                      "<p>%s…</p><p>« Voir l'origine » ouvre l'étude "
                      "complète. <b>APPROUVER</b> crée la tâche « Donner "
                      "suite » — écris ta direction dans le commentaire, "
                      "elle y sera collée. <b>REJETER</b> classe sans "
                      "suite.</p>" % texte)

        # 2. Les constats de sécurité non tranchés. La sécurité passe devant :
        #    un constat critique ou grave est « ça bloque », le reste est
        #    important — jamais « quand tu peux ». Patrick, 29/07 : « la
        #    sécurité c'est l'affaire de tout le monde ».
        #    BUG PAYÉ LE 29/07 : ce rabat cherchait l'état « nouveau », qui
        #    n'existe pas chez Victor (propose/accepte/attente/refuse/
        #    resolu). Résultat : AUCUN constat de sécurité n'est jamais
        #    arrivé dans Décisions depuis la création du module. Un filtre
        #    sur une valeur inexistante ne lève rien — il rend une liste
        #    vide, et le silence ressemble à « tout va bien ».
        if "securite.constat" in self.env:
            for c in self.env["securite.constat"].sudo().search(
                    [("etat", "in", ["propose", "attente"])]):
                poser("securite.constat", c.id,
                      "Constat de Victor : %s" % c.name,
                      "Victor", "",
                      priorite="1" if c.gravite in ("critique", "grave") else "2")

        # 3. Les tâches [À CONFIRMER].
        for t in self.env["project.task"].sudo().search(
                [("name", "like", "[À CONFIRMER]%")]):
            if not t.stage_id.fold:
                poser("project.task", t.id,
                      t.name.replace("[À CONFIRMER]", "").strip(),
                      "L'équipe",
                      t.description or "",
                      user=decideur_de(t))

        # 4. Le balai des doublons. Trois tentatives d'atelier pour la même
        #    tâche = trois missions différentes = trois fiches au même nom à
        #    l'écran (payé le 29/07, tâche 346 : « doublon à l'infini »).
        #    Même décideur, même modèle d'origine, même nom, tous en attente :
        #    un seul survivant, le plus récent. Les autres se ferment SANS
        #    passer par le rejet — un rejet commenté d'une mission relance
        #    l'agent, et le doublon renaîtrait en reproposition.
        groupes = {}
        for d in self.sudo().search([("etat", "=", "attente")],
                                    order="create_date"):
            groupes.setdefault((d.user_id.id, d.res_model, d.name),
                               []).append(d)
        for fiches in groupes.values():
            for doublon in fiches[:-1]:
                doublon.write({
                    "etat": "rejete",
                    "commentaire": "Doublon fermé par le rabatteur — la "
                                   "fiche la plus récente reste seule.",
                    "decide_le": fields.Datetime.now()})
        return True

    @api.model
    def _cron_rabattre(self):
        self._rabattre()
        return True

    @api.model
    def nb_en_attente(self, user_id=None):
        """Le compteur de l'accueil : combien m'attendent, moi."""
        return self.search_count([
            ("etat", "=", "attente"),
            ("user_id", "=", user_id or self.env.user.id)])

    # ------------------------------------------------------------------
    @api.model
    def _controle_banc(self):
        """Le banc des Décisions : dix cas joués, puis TOUT est annulé.

        Né le 28/07 (« des bugs, flemme d'expliquer, demande au testeur ») :
        le banc de cette session-là rendait 10/10 côté serveur, puis a
        disparu avec la session. Ici il devient une épreuve permanente
        (tâche 463) : approbation et rejet sur chaque type d'origine,
        origine supprimée comprise.

        Ses engagements, resserrés après la relecture de Lois du 29/07 :
        - AUCUN effet hors base, vraiment : pendant les cas mission,
          action_envoyer est remplacé pour les seules fiches [BANC] (les
          vraies missions passent par l'original) — plus de fichier déposé
          sur l'hôte, plus de course contre le ramasseur de l'atelier ;
        - tout se joue sous un savepoint TOUJOURS annulé, un savepoint par
          cas (un cas qui plante n'empoisonne pas les suivants) ;
        - les assertions comptent en DELTA (avant/après) : un reliquat
          d'une exécution passée rend le banc ROUGE, jamais faussement
          vert ;
        - le verdict dit ce qui n'a pas été joué (« 10/10 dont 4 non
          joués » sur une base sans atelier) au lieu de le taire.

        Rend « n/n » si tout ce qui s'est joué passe ; LÈVE sinon, pour que
        l'épreuve passe rouge avec le détail (le genre « controle » des
        épreuves ne regarde que la stabilité du verdict, pas son contenu).
        """
        resultats = []
        env = self.env
        Decision = env["decision.fiche"].sudo()
        Tache = env["project.task"].sudo()

        class _Fini(Exception):
            """Sortie volontaire : force l'annulation du savepoint global."""

        def fiche(res_model, res_id, nom):
            return Decision.create({
                "name": "[BANC] %s" % nom, "origine": "banc",
                "res_model": res_model, "res_id": res_id,
                "user_id": env.ref("base.user_admin").id,
            })

        def cas(nom, fn):
            try:
                with env.cr.savepoint():
                    fn()
                resultats.append((nom, True, ""))
            except Exception as exc:  # noqa: BLE001
                resultats.append((nom, False, str(exc)[:100]))

        def passe_sans_jouer(nom, pourquoi):
            resultats.append((nom, None, pourquoi))

        try:
            with env.cr.savepoint():
                # Le projet du banc : créé ici, annulé avec le reste. Jamais
                # d'id en dur — le projet 1 n'existe pas sur toute base
                # (Lois, cas 4).
                projet = env["project.project"].sudo().create(
                    {"name": "[BANC] projet du banc"})

                # 1-2 — la mission d'atelier : approuver envoie, rejeter
                # relance. action_envoyer est remplacé pour les fiches
                # [BANC] : on prouve que le circuit APPELLE l'envoi, sans
                # rien écrire sur l'hôte — la plomberie de l'atelier a ses
                # propres contrôles.
                if "atelier.mission" not in env:
                    passe_sans_jouer("approuver une mission", "module atelier absent")
                    passe_sans_jouer("rejeter une mission", "module atelier absent")
                else:
                    Mission = env["atelier.mission"].sudo()
                    moteurs = dict(Mission.fields_get(
                        ["moteur"])["moteur"]["selection"] or [])
                    if "essai" not in moteurs:
                        passe_sans_jouer("approuver une mission",
                                         "moteur essai indisponible (atelier non monté)")
                        passe_sans_jouer("rejeter une mission",
                                         "moteur essai indisponible (atelier non monté)")
                    else:
                        import uuid as _uuid
                        Registre = env.registry["atelier.mission"]
                        _envoyer_original = Registre.action_envoyer

                        def _envoyer_banc(mission):
                            if (mission.name or "").startswith("[BANC]"):
                                mission.jeton = _uuid.uuid4().hex[:16]
                                mission.etat = "envoyee"
                                return True
                            return _envoyer_original(mission)

                        def c1():
                            m = Mission.create({
                                "name": "[BANC] approuver une mission",
                                "moteur": "essai",
                                "consigne": "Banc des Décisions : ne rien faire."})
                            d = fiche("atelier.mission", m.id, "mission approuvée")
                            d.action_approuver()
                            assert d.etat == "approuve", "fiche pas approuvée"
                            assert m.etat == "envoyee", "l'envoi n'a pas été déclenché"

                        def c2():
                            m = Mission.create({
                                "name": "[BANC] rejeter une mission",
                                "moteur": "essai",
                                "consigne": "Banc des Décisions."})
                            d = fiche("atelier.mission", m.id, "mission rejetée")
                            avant = Mission.search_count(
                                [("name", "like", "Reproposition : [BANC] rejeter%")])
                            d.commentaire = "Banc : rejet volontaire."
                            d.action_rejeter()
                            assert d.etat == "rejete", "fiche pas rejetée"
                            apres = Mission.search_count(
                                [("name", "like", "Reproposition : [BANC] rejeter%")])
                            assert apres == avant + 1, (
                                "pas de reproposition créée PAR CE CAS "
                                "(avant %s, après %s)" % (avant, apres))

                        Registre.action_envoyer = _envoyer_banc
                        try:
                            cas("approuver une mission (l'envoi est déclenché)", c1)
                            cas("rejeter une mission (reproposition créée)", c2)
                        finally:
                            Registre.action_envoyer = _envoyer_original

                # 3-4 — la tâche [À CONFIRMER] : approuver retire le
                # préfixe, rejeter archive.
                def c3():
                    t = Tache.create({"name": "[À CONFIRMER] [BANC] cas approuvé",
                                      "project_id": projet.id})
                    d = fiche("project.task", t.id, "tâche à confirmer approuvée")
                    d.action_approuver()
                    assert d.etat == "approuve", "fiche pas approuvée"
                    assert not t.name.startswith("[À CONFIRMER]"), "préfixe pas retiré"

                def c4():
                    t = Tache.create({"name": "[À CONFIRMER] [BANC] cas rejeté",
                                      "project_id": projet.id})
                    d = fiche("project.task", t.id, "tâche rejetée")
                    d.commentaire = "Banc : rejet volontaire."
                    d.action_rejeter()
                    assert d.etat == "rejete", "fiche pas rejetée"
                    assert not t.active, "tâche pas archivée"

                cas("approuver une tâche [À CONFIRMER] (préfixe retiré)", c3)
                cas("rejeter une tâche (archivée)", c4)

                # 5-6 — le constat de Victor : accepté / refusé. Un code
                # UNIQUE par cas : la contrainte unique(code) a mordu le
                # banc à son premier passage réel.
                if "securite.constat" not in env:
                    passe_sans_jouer("approuver un constat", "module sécurité absent")
                    passe_sans_jouer("rejeter un constat", "module sécurité absent")
                else:
                    Constat = env["securite.constat"].sudo()

                    def c5():
                        c = Constat.create({"name": "[BANC] constat accepté",
                                            "code": "banc_decisions_a"})
                        d = fiche("securite.constat", c.id, "constat accepté")
                        d.action_approuver()
                        assert d.etat == "approuve", "fiche pas approuvée"
                        assert c.etat == "accepte", "constat pas accepté"

                    def c6():
                        c = Constat.create({"name": "[BANC] constat refusé",
                                            "code": "banc_decisions_b"})
                        d = fiche("securite.constat", c.id, "constat refusé")
                        d.commentaire = "Banc : rejet volontaire."
                        d.action_rejeter()
                        assert d.etat == "rejete", "fiche pas rejetée"
                        assert c.etat == "refuse", "constat pas refusé"

                    cas("approuver un constat de sécurité", c5)
                    cas("rejeter un constat de sécurité", c6)

                # 7-8 — l'étude (fiche Réponses) : approuver crée la tâche
                # « Donner suite ». Le code de production écrit dans le
                # projet 1 en dur : s'il n'existe pas ici, on le DIT au
                # lieu de passer rouge pour une raison d'environnement.
                if "reponse.fiche" not in env:
                    passe_sans_jouer("approuver une étude", "module réponses absent")
                    passe_sans_jouer("rejeter une étude", "module réponses absent")
                else:
                    Rep = env["reponse.fiche"].sudo()
                    projet_1 = env["project.project"].sudo().browse(1).exists()

                    def c7():
                        r = Rep.create({"name": "[BANC] étude approuvée",
                                        "reponse": "<p>Banc.</p>",
                                        "auteur": "banc"})
                        d = fiche("reponse.fiche", r.id, "étude approuvée")
                        titre = ("Donner suite : %s" % r.name)[:120]
                        avant = Tache.search_count([("name", "=", titre)])
                        d.action_approuver()
                        assert d.etat == "approuve", "fiche pas approuvée"
                        apres = Tache.search_count([("name", "=", titre)])
                        assert apres == avant + 1, (
                            "pas de tâche « Donner suite » créée PAR CE CAS "
                            "(avant %s, après %s — un reliquat bloque la "
                            "création en production)" % (avant, apres))

                    def c8():
                        r = Rep.create({"name": "[BANC] étude rejetée",
                                        "reponse": "<p>Banc.</p>",
                                        "auteur": "banc"})
                        d = fiche("reponse.fiche", r.id, "étude rejetée")
                        d.commentaire = "Banc : rejet volontaire."
                        d.action_rejeter()
                        assert d.etat == "rejete", "fiche pas rejetée"

                    if projet_1:
                        cas("approuver une étude (tâche Donner suite créée)", c7)
                    else:
                        passe_sans_jouer("approuver une étude",
                                         "le projet 1 (journal) n'existe pas ici")
                    cas("rejeter une étude", c8)

                # 9-10 — l'origine supprimée : décider ne doit JAMAIS
                # planter parce que la chose d'origine a disparu.
                def c9():
                    t = Tache.create({"name": "[BANC] origine disparue A",
                                      "project_id": projet.id})
                    tid = t.id
                    t.unlink()
                    d = fiche("project.task", tid, "origine supprimée, approuvée")
                    d.action_approuver()
                    assert d.etat == "approuve", "fiche pas approuvée"

                def c10():
                    t = Tache.create({"name": "[BANC] origine disparue B",
                                      "project_id": projet.id})
                    tid = t.id
                    t.unlink()
                    d = fiche("project.task", tid, "origine supprimée, rejetée")
                    d.commentaire = "Banc : rejet volontaire."
                    d.action_rejeter()
                    assert d.etat == "rejete", "fiche pas rejetée"

                cas("approuver malgré une origine supprimée", c9)
                cas("rejeter malgré une origine supprimée", c10)

                raise _Fini()
        except _Fini:
            pass

        rates = [(nom, detail) for nom, okv, detail in resultats if okv is False]
        non_joues = [(nom, detail) for nom, okv, detail in resultats if okv is None]
        total = len(resultats)
        if rates:
            raise ValueError("%s/%s — raté : %s" % (
                total - len(rates) - len(non_joues), total,
                "; ".join("%s (%s)" % r for r in rates)))
        verdict = "%s/%s" % (total, total)
        if non_joues:
            verdict += " dont %s non joué(s) : %s" % (
                len(non_joues), "; ".join(n for n, _d in non_joues))
        return verdict
