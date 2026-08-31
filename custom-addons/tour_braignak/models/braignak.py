# -*- coding: utf-8 -*-
"""Braignak — l'observateur.

Ce qu'il fait : il regarde une application, comprend avec quoi elle est faite,
en tire la liste de ce qu'elle sait faire, et dit lesquelles de ces capacités
mériteraient d'entrer dans la tour. Quand ça vaut le coup, il fait construire
un prototype ; quand ça n'en vaut pas la peine, il le dit et on n'y revient pas.

Ce qu'il n'est pas : un programme qui se lance tout seul. La v1 ne tourne
qu'à la demande, ne publie rien, et n'envoie aucune mission sans qu'un humain
appuie sur le bouton.

**La règle d'ouverture.** Ce fichier est la description complète de Braignak.
Il n'y a pas de deuxième endroit où il ferait autre chose. Si un jour son
comportement ne correspond plus à ce qui est écrit ici, c'est un défaut — ou
une attaque —, pas une évolution.

**Les trois verrous, et pourquoi il en faut trois.** La règle posée par le
propriétaire est que tout ordre venu de la tour fait loi. C'est exactement ce
qui rend la question « et si la tour se fait attaquer ? » si sérieuse : qui
tient la tour tient Braignak. Un interrupteur rangé dans la base de données ne
protège donc de rien contre celui qui a la base. D'où :

1. `tour_braignak.actif` — l'interrupteur ordinaire, dans la tour. Faux par
   défaut. Pratique : il s'éteint depuis un téléphone, en une seconde.
2. Le fichier d'autorisation **hors du dossier partagé**, sur la machine hôte.
   Le conteneur ne le voit pas, ne peut pas le créer, ne peut pas le lire.
   Seul quelqu'un qui entre en SSH peut le poser. Une tour entièrement
   compromise ne peut pas le contourner : elle peut mentir sur l'interrupteur,
   pas fabriquer ce fichier.
3. L'absence du moteur. Aucun moteur `braignak` installé sur l'hôte = aucune
   exécution possible, quoi que dise la tour.

Le verrou n° 2 est le seul qui compte le jour d'une attaque. Les deux autres
sont du confort.
"""
import json
import logging
import re
from html import unescape

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Le moteur côté hôte vérifie ce chemin AVANT de travailler. Il est écrit ici
# pour que la fiche puisse l'afficher à l'utilisateur — la tour, elle, ne peut
# ni le lire ni l'écrire : il est en dehors du dossier partagé, exprès.
CHEMIN_AUTORISATION = "~/braignak.autorise (sur la machine hôte, hors du dossier partagé)"

NATURES = [
    ("mienne", "Une de mes applications"),
    ("libre", "Logiciel libre / code ouvert"),
    ("publique", "Application publique, observée de l'extérieur"),
]

VERDICTS = [
    ("a_reprendre", "À reprendre : la tour doit savoir faire ça"),
    ("a_prototyper", "À prototyper avant de décider"),
    ("a_ignorer", "Sans intérêt pour la tour — on n'y revient pas"),
]

# La hiérarchie d'une pile, c'est son ordre. Vingt-cinq verdicts « à
# reprendre » sans ordre sont une pile qui ne se vide jamais : rien ne dit
# lequel passe d'abord, donc chacun attend que quelqu'un en décide, et la
# décision finit par tomber sur le dernier qui a parlé — pas sur le plus
# utile. La priorité est posée par le décideur, à la main ; le fichier
# « À traiter » s'en sert pour ordonner la file.
PRIORITES = [
    ("haute", "Haute — la file passe par là d'abord"),
    ("moyenne", "Moyenne"),
    ("basse", "Basse — quand le reste est traité"),
]
# L'ordre de tri : une chaîne alphabétique dirait « basse < haute < moyenne ».
# L'ordre humain, lui, est haute > moyenne > basse. On range donc sur un
# nombre, jamais sur le libellé.
ORDRE_PRIORITE = {"haute": 0, "moyenne": 1, "basse": 2}


class BraignakEtude(models.Model):
    _name = "braignak.etude"
    _description = "Braignak — étude d'une application"
    _inherit = ["mail.thread"]
    _order = "create_date desc"

    name = fields.Char("Application étudiée", required=True, tracking=True)
    source = fields.Char(
        "Où on la regarde", required=True,
        help="Une adresse publique, un dépôt de code, ou le chemin d'une de "
             "vos applications.")
    nature = fields.Selection(
        NATURES, string="Nature", required=True, default="mienne", tracking=True,
        help="Détermine ce que Braignak a le droit de faire. Une application "
             "publique qui n'est pas à vous s'observe de l'extérieur : on note "
             "ce qu'elle SAIT FAIRE, on ne récupère pas comment elle est "
             "écrite.")
    etat = fields.Selection(
        [("brouillon", "Brouillon"),
         ("observation", "Observation en cours"),
         ("analysee", "Analysée"),
         ("prototype", "Prototype demandé"),
         ("close", "Close")],
        string="État", default="brouillon", readonly=True, tracking=True)
    observations = fields.Text(
        "Ce qu'on a observé",
        help="Le comportement constaté, les outils devinés, les limites.")
    # EN BREF : le coeur des observations, sans IA (recette de reponse.fiche).
    # On lit le resume en tete de fiche ; le detail reste dans l'onglet.
    resume = fields.Text(
        "En bref", compute="_compute_resume", store=True,
        help="Le coeur de ce qui a été observé, en court. Le détail complet "
             "est dans l'onglet Observations.")
    verdict = fields.Selection(VERDICTS, string="Verdict", tracking=True)
    justification = fields.Text("Pourquoi ce verdict")
    priorite = fields.Selection(
        PRIORITES, string="Priorité", default="moyenne", tracking=True,
        help="Qui choisit ? Vous, en posant la priorité ici. La file « À "
             "traiter » s'y range toute seule : haute d'abord, puis l'ancienneté. "
             "Une étude sans verdict ni priorité reste dans la file, mais elle "
             "attend derrière celles qu'on a voulu traiter.")
    priorite_ordre = fields.Integer(
        "Ordre de priorité", compute="_compute_priorite_ordre", store=True)
    nb_fort = fields.Integer(
        "Capacités à fort intérêt", compute="_compute_nb_fort", store=True,
        help="Combien de capacités repérées valent le coup d'être reprises. "
             "Un bon signal pour choisir la priorité.")
    capacite_ids = fields.One2many("braignak.capacite", "etude_id", "Capacités repérées")
    nb_capacites = fields.Integer("Capacités", compute="_compute_nb", store=False)
    mission_ids = fields.Many2many("atelier.mission", string="Missions engendrees",
                                   readonly=True)
    demandeur_id = fields.Many2one(
        "res.users", "Demandeur",
        help="Qui a pose la question depuis la webapp Braignak : chacun ne voit que ses etudes.")
    journal_ids = fields.One2many(
        "braignak.journal", "etude_id", string="Journal",
        help="Les traces de ce que Braignak a fait pour cette étude. Ce "
             "journal ne se modifie pas et ne s'efface pas.")

    # ------------------------------------------------------------------
    @api.depends("priorite")
    def _compute_priorite_ordre(self):
        for rec in self:
            rec.priorite_ordre = ORDRE_PRIORITE.get(rec.priorite, 1)

    @api.depends("capacite_ids.interet")
    def _compute_nb_fort(self):
        for rec in self:
            rec.nb_fort = len(rec.capacite_ids.filtered(
                lambda c: c.interet == "fort"))

    # ------------------------------------------------------------------
    @api.depends("observations", "mission_ids", "mission_ids.reponse")
    def _compute_resume(self):
        # LE RESUME COURT, BRANCHE SUR LE MOTEUR DE CONDENSATION (31/07).
        # La recette locale gardait le markdown brut (** , ##, *) et les
        # en-tetes de mission — le « En bref » affiche n'importe quoi.
        # Le moteur condense (condense.engine._resumer_bref) nettoie et rend
        # un resume court, niveau 6 ans (IA en secours). Repli local sinon.
        #
        # 31/07 (2e passe) : la source est la REPONSE de la mission, pas le
        # champ observations — qui commence par la SPEC de l'etude. Résumer
        # la spec, c'est afficher la question, pas la réponse de Braignak.
        # On prend la dernière réponse de mission (la plus récente), et on
        # retombe sur observations seulement si aucune mission n'a répondu.
        for rec in self:
            source = ""
            if rec.mission_ids:
                reponses = rec.mission_ids.sudo().filtered(
                    lambda m: (m.reponse or "").strip())
                if reponses:
                    source = reponses.sorted(
                        key=lambda m: m.livree_le or m.create_date,
                        reverse=True)[0].reponse
            if not source:
                source = rec.observations or ""
            if not source:
                rec.resume = ""
                continue
            if "condense.engine" in self.env:
                resume = self.env["condense.engine"].sudo()._resumer_bref(source)
                if resume:
                    rec.resume = resume
                    continue
            rec.resume = self._resumer(source)

    @staticmethod
    def _resumer(html):
        """Un resume court, sans IA. On jette le decor, on garde la prose.

        Recopie de reponse.fiche : ligne par ligne, on ecarte le decor
        technique et on garde les premieres vraies phrases. Deterministe.
        """
        if not html:
            return ""
        texte = unescape(re.sub(r"<[^>]+>", "\n", html))
        rejets = ("===", "---", "***", "tours", "jetons", "fichiers",
                  "appels", "attention", "moteur", "ce qu on", "ce qu'on",
                  "ce qui", "ce que", "voici ce qu", "trois lignes",
                  "trois phrases", "aucun fichier", "construit par")
        bonnes = []
        for ligne in texte.splitlines():
            l = ligne.strip().lstrip("-*#>• ").strip()
            if not l or re.fullmatch(r"[=\-_*·•\s]+", l):
                continue
            low = l.lower()
            if any(low.startswith(p) for p in rejets):
                continue
            if len(l) < 12 or not re.search(r"[A-Za-zÀ-ÿ]", l):
                continue
            bonnes.append(l)
            if sum(len(x) for x in bonnes) > 320:
                break
        resume = re.sub(r"\s+", " ", " ".join(bonnes)).strip()
        if len(resume) <= 300:
            return resume
        coupe = resume[:300]
        p = max(coupe.rfind(". "), coupe.rfind("! "), coupe.rfind("? "))
        return coupe[:p + 1] if p > 120 else coupe.rsplit(" ", 1)[0] + " …"

    # ------------------------------------------------------------------
    @api.depends("capacite_ids")
    def _compute_nb(self):
        for rec in self:
            rec.nb_capacites = len(rec.capacite_ids)

    # ------------------------------------------------------------------
    # Les garde-fous
    # ------------------------------------------------------------------
    @api.model
    def _actif(self):
        return self.env["ir.config_parameter"].sudo().get_param(
            "tour_braignak.actif", "False") == "True"

    @api.model
    def _exiger_actif(self):
        """Refuse tout net si l'interrupteur est éteint.

        Volontairement bavard : quelqu'un qui découvre Braignak doit
        comprendre du premier coup ce qui le retient, et où est l'autre verrou.
        """
        if not self._actif():
            raise UserError(_(
                "Braignak est à l'arrêt.\n\n"
                "Pour le mettre en marche il faut DEUX gestes, et le second "
                "ne peut pas être fait depuis la tour :\n"
                "1. Cocher « Braignak en marche » dans Réglages.\n"
                "2. Créer le fichier d'autorisation sur le serveur : %s\n\n"
                "Le second verrou existe pour une raison précise : si la tour "
                "était prise par quelqu'un d'autre, il pourrait tout changer "
                "ici — mais pas fabriquer ce fichier.", CHEMIN_AUTORISATION))

    def _journaliser(self, action, detail=""):
        """Écrit une ligne dans le journal. Ce journal ne se modifie pas.

        Les droits n'accordent que la création : ni écriture, ni suppression,
        pour personne. Un observateur dont on peut effacer les traces
        n'est pas observable.
        """
        self.env["braignak.journal"].sudo().create({
            "etude_id": self.id,
            "action": action,
            "detail": detail[:4000],
            "utilisateur_id": self.env.user.id,
        })

    # ------------------------------------------------------------------
    # Les actions
    # ------------------------------------------------------------------
    def action_observer(self):
        """Prépare la mission d'observation — en BROUILLON, jamais envoyée.

        C'est le cœur de la garantie : Braignak n'a pas de bouton qui part
        tout seul. Il rédige, un humain relit et envoie.
        """
        self.ensure_one()
        self._exiger_actif()
        Mission = self.env["atelier.mission"]

        if self.nature == "publique":
            cadre = _(
                "Cette application ne vous appartient pas. Tu observes ce "
                "qu'elle SAIT FAIRE, depuis l'extérieur et depuis sa "
                "documentation publique.\n\n"
                "INTERDICTIONS ABSOLUES, NON NÉGOCIABLES :\n"
                "• Tu ne recopies AUCUNE ligne de code source, même partielle.\n"
                "• Tu ne recopies AUCUNE image, icône, capture d'écran.\n"
                "• Tu ne recopies AUCUN texte original (articles, descriptions, "
                "CGV, mentions légales).\n"
                "• Tu ne reproduis AUCUNE maquette, mise en page protégée.\n"
                "• Tu ne sauvegardes AUCUN fichier du site observé.\n"
                "• Tu ne décris que la FONCTION et le COMPORTEMENT, pas "
                "l'expression originale.\n\n"
                "Ce qui est permis : décrire ce que ça fait, avec quel type "
                "d'outils c'est construit, quelles API sont utilisées, et "
                "évaluer la difficulté de refaire la même fonction. "
                "Reproduire une fonction est licite ; recopier une œuvre ne "
                "l'est pas. Cette limite est technique : tu n'as pas d'outil "
                "d'écriture.")
        elif self.nature == "libre":
            cadre = _(
                "Code ouvert : tu peux le lire. Relève la licence AVANT toute "
                "chose et écris-la dans ton compte rendu — une licence "
                "contaminante (GPL, AGPL) changerait la licence de la tour.\n\n"
                "INTERDICTIONS :\n"
                "• Tu ne recopies PAS de blocs entiers de code.\n"
                "• Tu ne recopies PAS les commentaires originaux.\n"
                "• Tu cites la fonction, pas son implémentation littérale.\n"
                "• Tu écris le nom de la licence dans ton compte rendu.")
        else:
            cadre = _("C'est une application du propriétaire : accès complet.")

        consigne = _(
            "%(cadre)s\n\n"
            "Application : %(nom)s\nOù la regarder : %(origine)s\n\n"
            "Travail demandé, et RIEN d'autre :\n"
            "1. Décris ce que cette application sait faire, capacité par "
            "capacité. Une ligne par capacité, en français, sans jargon.\n"
            "2. Pour chacune, dis avec quoi elle est probablement construite "
            "et à quel point ce serait dur à refaire — JAMAIS de copie de "
            "code ou de texte original.\n"
            "3. Dis lesquelles la tour de contrôle NE SAIT PAS déjà faire — "
            "lis le guide « Cahier de reproduction » de la tour pour le "
            "savoir, ne devine pas.\n"
            "4. Termine par un verdict en une phrase : à reprendre, à "
            "prototyper, ou sans intérêt.\n\n"
            "Tu ne modifies aucun fichier de la tour. Tu ne publies rien. "
            "Tu n'écris AUCUN fichier — tu n'as d'ailleurs pas l'outil "
            "pour le faire. Tu rends un texte.",
            cadre=cadre, nom=self.name, origine=self.source)

        # LA SPEC DE L'ETUDE, JOINTE A LA MISSION (31/07).
        #
        # Defaut paye le 31/07 : la spec etait deposee dans `observations` de
        # l'etude, mais la consigne de mission n'en parlait pas — Braignak
        # recevait le cadre generique d'observation SANS le sujet precis a
        # analyser (marche, outils, consignes permanentes). Capte != livre :
        # une spec qui ne voyage pas jusqu'a la mission n'existe pas pour
        # l'agent. On la joint donc au texte, comme le Cahier de reproduction.
        spec = (self.observations or "").strip()
        if spec:
            import re as _re
            spec_propre = _re.sub(r"\s+", " ", spec).strip()
            consigne += _(
                "\n\n=== LA SPEC DE CETTE ETUDE (a analyser) ===\n%s"
                "\n\nLe travail demande ci-dessus s'applique A CETTE SPEC : "
                "c'est elle le sujet precis, pas le nom de l'application "
                "seule.") % spec_propre[:20000]

        # LA METHODE (regle de Patrick, 31/07). Chaque etude porte une
        # question differente, et la question DECIDE de la methode. Braignak
        # doit donc, en tete de compte rendu, annoncer la methode qu'il a
        # choisie et POURQUOI — puis suivre ses etapes dans l'ordre. Ce n'est
        # pas un menu a piocher au gout : c'est une discipline qui depend de
        # ce qu'on lui demande de prouver.
        consigne += _(
            "\n\n=== TA METHODE (a annoncer en tete de compte rendu) ===\n"
            "Chaque etude pose une question. La question DECIDE de la methode. "
            "Avant de travailler, choisis LA methode qui convient a CETTE "
            "etude, ecris en tete de ton compte rendu : « METHODE : <nom> — "
            "pourquoi celle-la », puis suis SES etapes, dans l'ordre.\n\n"
            "Les methodes, et quand les choisir :\n"
            "1. THEORIQUE — on veut REFLECHIR, comprendre une idee, modeliser. "
            "Etapes : definir le probleme ; lire ce qui existe deja ; "
            "identifier les idees cles ; comparer les concepts ; construire un "
            "modele ou une explication ; verifier la coherence du "
            "raisonnement ; conclure (ou formuler une hypothese a tester "
            "ensuite).\n"
            "2. EMPIRIQUE — on veut VERIFIER DANS LE REEL, pas raisonner. "
            "Etapes : choisir une question concrete ; observer le terrain ou "
            "la realite ; recueillir des donnees ; mesurer ou noter ce qui se "
            "passe ; analyser les donnees ; comparer avec l'hypothese de "
            "depart ; conclure a partir du reel.\n"
            "3. QUALITATIVE — on veut COMPRENDRE LE SENS, le pourquoi, le "
            "comment. Etapes : definir ce qu'on veut comprendre ; choisir les "
            "personnes ou situations a etudier ; mener entretiens, "
            "observations, lecture de documents ; recueillir verbatims, "
            "comportements, recits ; classer les idees qui reviennent ; "
            "interpreter le sens ; conclure sur le pourquoi ou le comment.\n"
            "4. OBSERVATIONNELLE — on veut REGARDER SANS INTERVENIR. Etapes : "
            "definir ce qu'on veut observer ; choisir le lieu ou le groupe ; "
            "observer sans intervenir ; noter les faits de maniere "
            "systematique ; comparer les observations ; chercher des "
            "tendances ; conclure sans pretendre avoir cause le phenomene.\n"
            "5. ETUDE DE CAS — on veut ANALYSER UN CAS PRECIS, en profondeur. "
            "Etapes : definir le sujet precis ; delimiter le cas, le groupe "
            "ou la population ; choisir la methode de collecte ; reunir les "
            "informations utiles ; analyser les donnees ; mettre en relation "
            "les elements ; tirer une conclusion sur CE cas.\n"
            "6. META-ANALYSE — on veut COMPARER PLUSIEURS TRAVAUX. Etapes : "
            "formuler une question de recherche ; chercher plusieurs etudes "
            "sur le sujet ; choisir les etudes pertinentes ; extraire leurs "
            "resultats ; comparer les resultats entre eux ; regrouper les "
            "donnees ; conclure sur la tendance generale.\n"
            "7. RECHERCHE-ACTION — on veut AGIR ET APPRENDRE EN MEME TEMPS, "
            "ameliorer quelque chose. Etapes : reperer un probleme reel ; "
            "definir une action pour l'ameliorer ; mettre en place cette "
            "action ; observer ce qui change ; analyser les effets ; ajuster "
            "l'action si besoin ; conclure sur ce qui a marche ou non.\n"
            "8. PARTICIPATIVE — on veut CONSTRUIRE LA RECHERCHE AVEC LES "
            "PERSONNES CONCERNEES. Etapes : definir le probleme avec elles ; "
            "decider ensemble des objectifs ; choisir les methodes avec "
            "elles ; recueillir les donnees ensemble ; interpreter les "
            "resultats ensemble ; decider des actions ensemble ; partager les "
            "conclusions avec tous.\n\n"
            "En un mot : theorique = reflechir ; empirique = observer le "
            "reel ; qualitative = comprendre le sens ; observationnelle = "
            "regarder sans agir ; etude de cas = analyser un cas ; "
            "meta-analyse = comparer des etudes ; recherche-action = "
            "comprendre et ameliorer ; participative = chercher avec les "
            "personnes concernees.\n"
            "Choisis-en UNE, annonce-la avec ta raison, suis ses etapes.\n\n"
            "=== LA DEMARCHE SCIENTIFIQUE (regle du proprietaire, 31/07) ===\n"
            "Toute etude qui cherche a RESOUDRE UN PROBLEME suit la sequence :\n"
            "question → hypothese → protocole/experience → resultats → "
            "analyse → conclusion.\n"
            "Simplement : on part d'une question, on propose une hypothese "
            "(une idee a tester), on teste, on observe les resultats, on "
            "analyse, puis on conclut SANS DEPASSER les donnees. Si tu n'as "
            "pas de donnees, dis-le et propose le protocole pour en avoir.\n\n"
            "=== L'EXPERIENCE DE PENSEE AVANT CONSTRUCTION (31/07) ===\n"
            "Avant de recommander de construire quoi que ce soit, pousse "
            "l'idee dans ta tete jusqu'a ses cas extremes, et reponds dans "
            "ton compte rendu a ces trois questions :\n"
            "- Que se passe-t-il si ca tourne A FOND ?\n"
            "- Que se passe-t-il si TOUT ECHOUE ?\n"
            "- Que se passe-t-il si l'INVERSE de mon raisonnement est vrai ?\n"
            "Si une reponse montre que l'idee ne tient pas, dis-le.\n\n"
            "=== LE CIRCUIT DE TES ETUDES (regle du proprietaire, 31/07) ===\n"
            "Ton travail ne s'arrete pas a rendre un texte. Quand tu termines "
            "une etude :\n"
            "1. Tu relis TON PROPRE retour d'etude et tu dis ce qu'elle a "
            "apporte ou echoue a apporter.\n"
            "2. Tu observes si cette etude permet d'emettre DE NOUVELLES "
            "HYPOTHESES pour resoudre le probleme de depart.\n"
            "3. TU NE DECLENCHES UNE DECISION QUE DANS CE SEUL CAS : une "
            "hypothese nouvelle est sortie de TON etude (pas de celle d'un "
            "autre, pas d'une intuition sans etude). Sans hypothese nouvelle "
            "issue de ton propre travail, tu ne proposes AUCUNE decision.\n"
            "Une decision n'est jamais une fin : c'est une hypothese que "
            "Patrick pourra valider, tester, et corriger.")


        # Le << Cahier de reproduction >> est un GUIDE dans Odoo, pas un
        # fichier : Braignak n'y a aucun acces et il l'a dit lui-meme plutot
        # que de deviner — exactement ce qu'on lui demande. On le lui joint
        # donc au texte de la mission. Demander a quelqu'un de lire un
        # document qu'on ne lui donne pas, c'est l'obliger a inventer ou a
        # s'arreter.
        cahier = self.env["tour.guide"].sudo().search(
            [("name", "ilike", "reproduction")], limit=1)
        if cahier:
            import re
            texte = re.sub(r"<[^>]+>", " ", str(cahier.contenu or ""))
            texte = re.sub(r"\s+", " ", texte).strip()
            # On coupe à une PHRASE, jamais au caractère. Braignak a refusé de
            # travailler sur un cahier tranché au milieu d'un mot, en disant
            # pourquoi : la consigne lui interdit de deviner. Il avait raison.
            # Un document tronqué sans le dire oblige à inventer ou à s'arrêter.
            LIMITE = 20000
            if len(texte) > LIMITE:
                coupe = texte.rfind(". ", 0, LIMITE)
                texte = texte[:coupe + 1] if coupe > 0 else texte[:LIMITE]
                texte += _(
                    "\n\n[Le cahier continue au-delà de ce point. Ce qui "
                    "précède est complet et se termine sur une phrase "
                    "entière : tu peux t'y fier. Si tu as besoin de la suite, "
                    "demande-la plutôt que de supposer.]")
            consigne += _(
                "\n\n--- CE QUE LA TOUR SAIT DEJA FAIRE (cahier de "
                "reproduction, joint pour que tu n'aies pas a le chercher) "
                "---\n%s") % texte

        # LE MOTEUR. Sans cette ligne, la mission part sur le moteur PAR
        # DÉFAUT (« claude ») — celui-là n'a aucune restriction d'outils, donc
        # WebFetch lui demande une autorisation par domaine et il s'arrête.
        #
        # C'est ce qui s'est passé trois fois le 27/07, et j'ai « corrigé »
        # trois fois `braignak.sh` — un fichier que la mission n'exécutait
        # jamais. Le journal de l'atelier le disait pourtant en clair :
        # « moteur claude ». Je ne l'avais pas lu.
        #
        # Leçon : avant de corriger, vérifier QUEL code s'exécute réellement.
        # UNE SEULE mission en brouillon a la fois.
        #
        # Patrick a appuye trois fois sur << Preparer l'observation >> en disant
        # << ca revient toujours >>. Le bouton marchait tres bien : il creait
        # une NOUVELLE mission en brouillon a chaque appui — l'etude 2 en avait
        # sept. Rien a l'ecran ne disait que c'etait deja fait, donc le geste
        # naturel etait de reappuyer.
        #
        # Un bouton qui semble ne rien faire est un bouton sur lequel on
        # reappuie. On rouvre le brouillon existant au lieu d'en empiler un de
        # plus, et on le dit.
        existante = self.mission_ids.filtered(lambda m: m.etat == "brouillon")[:1]
        if existante:
            self.message_post(body=_(
                "Une mission d'observation est deja prete (n° %s) et attend "
                "d'etre envoyee. Je te la rouvre plutot que d'en creer une "
                "seconde.", existante.id))
            return {
                "type": "ir.actions.act_window",
                "res_model": "atelier.mission",
                "res_id": existante.id,
                "view_mode": "form",
            }

        consigne += _(
            "\n\n=== CAPACITES A DEPOSER (obligatoire, a la fin de ton compte "
            "rendu) ===\n"
            "Termine TOUJOURS ton compte rendu par ce bloc, UNE ligne par "
            "capacite reperee, au format exact :\n"
            "=== CAPACITES ===\n"
            "- Nom de la capacite | ce que ca permet en une phrase | fort, "
            "moyen ou nul\n"
            "Le « fort » = la tour devrait savoir le faire (prototype a "
            "envisager). Ce bloc est lu par la tour : les capacites entrent "
            "dans la fiche toutes seules.")
        vals = {
            "name": _("Braignak — observer %s", self.name),
            "consigne": consigne,
        }
        if "braignak" in [m[0] for m in Mission._moteurs_disponibles()]:
            vals["moteur"] = "braignak"
        mission = Mission.create(vals)
        self.write({"etat": "observation", "mission_ids": [(4, mission.id)]})
        self._journaliser("observation_preparee",
                          "mission %s (brouillon)" % mission.id)
        self.message_post(body=_(
            "Mission d'observation rédigée en <b>brouillon</b> (n° %s). "
            "Elle ne partira que si vous l'envoyez.", mission.id))
        return {
            "type": "ir.actions.act_window",
            "res_model": "atelier.mission",
            "res_id": mission.id,
            "view_mode": "form",
        }

    def _demander_depuis_chat(self, question, qui=None):
        """Etude lancee depuis la webapp Braignak (fenetre dediee).

        Patrick (06/08) : depuis la fenetre dediee a Braignak, on lance
        l'etude DIRECTEMENT ??? pas de brouillon a envoyer a la main.
        """
        self.ensure_one()
        self._exiger_actif()
        Mission = self.env["atelier.mission"]
        consigne = _(
            "Question posee par %(qui)s depuis la webapp Braignak :\n\n"
            "%(q)s\n\n"
            "Travail demande, et RIEN d'autre :\n"
            "1. Fais une etude serieuse de cette question : cherche, "
            "verifie, recoupe les sources accessibles.\n"
            "2. Rends un texte clair, en francais simple, avec les faits "
            "et les chiffres.\n"
            "3. Termine par ?? EN BREF : ?? en 5 lignes qui resument le "
            "coeur.\n"
            "4. Termine par un VERDICT en une phrase : a reprendre, a "
            "prototyper, ou sans interet.\n\n"
            "Tu ne modifies aucun fichier de la tour. Tu rends un texte.",
            qui=qui or self.env.user.name, q=question)
        vals = {
            "name": _("Braignak ??? ??tude : %s", self.name),
            "consigne": consigne,
        }
        if "braignak" in [m[0] for m in Mission._moteurs_disponibles()]:
            vals["moteur"] = "braignak"
        mission = Mission.create(vals)
        self.write({"etat": "observation", "mission_ids": [(4, mission.id)]})
        mission.action_envoyer()
        self._journaliser("demande_chat", "mission %s envoyee" % mission.id)
        return mission

    def action_prototyper(self):
        """Demande un prototype. Toujours en brouillon, et jamais publié."""
        self.ensure_one()
        self._exiger_actif()
        if self.verdict != "a_prototyper":
            raise UserError(_(
                "Le verdict doit être « À prototyper » pour demander un "
                "prototype. Sans verdict écrit, on construit sans savoir "
                "pourquoi."))
        retenues = self.capacite_ids.filtered(lambda c: c.interet == "fort")
        if not retenues:
            raise UserError(_(
                "Aucune capacité marquée « fort intérêt ». Un prototype qui "
                "ne vise rien de précis ne s'évalue pas."))
        liste = "\n".join("- %s : %s" % (c.name, c.description or "")
                          for c in retenues)
        mission = self.env["atelier.mission"].create({
            "name": _("Braignak — prototype d'après %s", self.name),
            "consigne": _(
                "Construis un prototype JETABLE qui démontre les capacités "
                "ci-dessous. Il ne s'agit pas de livrer dans la tour : il "
                "s'agit de savoir si ça vaut le coup.\n\n%(liste)s\n\n"
                "Contraintes : tu travailles dans le dossier jetable de la "
                "mission, tu ne touches à AUCUN module de la tour, tu ne "
                "publies rien. Termine par ce qui a été facile, ce qui a été "
                "dur, et ce que ça coûterait de le faire proprement.",
                liste=liste),
        })
        self.write({"etat": "prototype", "mission_ids": [(4, mission.id)]})
        self._journaliser("prototype_prepare", "mission %s" % mission.id)
        return {
            "type": "ir.actions.act_window",
            "res_model": "atelier.mission",
            "res_id": mission.id,
            "view_mode": "form",
        }

    def action_publier_prototype(self):
        """La v1 ne publie pas. C'est écrit dans le code, pas dans un réglage."""
        raise UserError(_(
            "La version 1 de Braignak ne met rien en ligne, et ce n'est pas "
            "un réglage qu'on peut changer : c'est refusé dans le code.\n\n"
            "La raison : publier, c'est écrire des fichiers servis sur "
            "Internet à partir d'un contenu que personne n'a relu. Tant que "
            "la question « que fait-on si la tour est attaquée ? » n'a pas de "
            "réponse écrite, cette porte reste fermée.\n\n"
            "En attendant : la mission de prototype produit un dossier, et "
            "c'est vous qui décidez d'en publier le contenu depuis la fiche "
            "de mission."))

    def action_tuer(self):
        """Clôt l'étude et interdit d'y revenir sans le dire."""
        self.ensure_one()
        if not self.justification:
            raise UserError(_(
                "Écrivez pourquoi avant de clore. Une étude tuée sans motif "
                "sera refaite dans six mois par quelqu'un qui ne saura pas "
                "qu'elle a déjà été faite."))
        self.write({"etat": "close", "verdict": self.verdict or "a_ignorer"})
        self._journaliser("etude_close", self.justification or "")
        return True

    def _deposer_ordre_stop(self):
        """Dépose l'ordre de suppression de l'autorisation côté hôte.

        La tour ne peut pas supprimer le fichier d'autorisation elle-même
        (il est hors du dossier partagé, exprès). Elle dépose un ordre dans
        le dossier des ordres ; atelier.sh le ramasse et supprime le fichier.
        """
        try:
            import os, tempfile
            ordres = "/mnt/atelier/ordres"
            if os.path.isdir(ordres) and os.access(ordres, os.W_OK):
                fd, path = tempfile.mkstemp(dir=ordres, prefix="braignak-stop-", suffix=".ordre")
                os.close(fd)
                dest = os.path.join(ordres, "braignak-stop.ordre")
                os.rename(path, dest)
                _logger.warning("Braignak : ordre stop depose par %s", self.env.user.login)
        except Exception:
            _logger.exception("Braignak : impossible de deposer l'ordre stop")

    def action_arret_urgence(self):
        """Éteint Braignak et suspend tout ce qui est en cours.

        Accessible depuis n'importe quelle fiche, exprès : le jour où on veut
        l'arrêter, on ne doit pas avoir à chercher où est le réglage.
        Dépose aussi un ordre côté hôte pour supprimer le fichier
        d'autorisation — le seul verrou que la tour ne peut pas toucher elle-même.
        """
        self.env["ir.config_parameter"].sudo().set_param(
            "tour_braignak.actif", "False")
        encours = self.sudo().search([("etat", "in", ("observation", "prototype"))])
        for e in encours:
            e._journaliser("arret_urgence", "arrêt demandé par %s" % self.env.user.name)
        brouillons = encours.mapped("mission_ids").filtered(
            lambda m: m.etat == "brouillon")
        brouillons.unlink()
        self._deposer_ordre_stop()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Braignak est arrêté"),
                "message": _(
                    "L'interrupteur est coupé et %s mission(s) en brouillon "
                    "ont été supprimées. L'ordre de suppression du fichier "
                    "d'autorisation a été déposé (exécution sous 1 min).",
                    len(brouillons)),
                "sticky": True,
                "type": "warning",
            },
        }


    def unlink(self):
        """Une étude qui a des traces ne s'efface pas : on clôt.

        Le journal refuse déjà la suppression de ses lignes. Mais ce verrou
        seul laisserait un trou : sans cette garde, la suppression d'une étude
        entraînerait celle de SON journal (cascade), et des traces disparues
        font mentir le journal — pire que pas de journal du tout. Une étude
        sans journal, créée par erreur, reste supprimable.
        """
        for rec in self:
            if rec.journal_ids:
                raise UserError(_(
                    "Cette étude a un journal : la supprimer effacerait ses "
                    "traces. Clore-la à la place (bouton « Clore l'étude »), "
                    "en écrivant pourquoi."))
        return super().unlink()

    # ------------------------------------------------------------------
    # COMPETENCE : demander des ressources, puis clore apres 48 h sans
    # reponse — avec reprise possible si des donnees arrivent (Patrick,
    # 31/07 : « quand il n'arrive a rien, demander plus de ressources ;
    # si aucune reponse n'arrive dans les 48 h, il classe l'affaire comme
    # echec mais possibilite de reprendre si plus de donnees »).
    #
    # Le blocage vit dans atelier.mission.besoins (« === IL ME MANQUE === »)
    # qui remonte en decision. Cette competence : (1) rappelle la demande si
    # elle attend encore (relance), (2) au-dela de 48 h, clôt l'etude en
    # echec trace, sans la detruire — et une mission relancee avec des
    # donnees rouvre le chantier.
    # ------------------------------------------------------------------
    DELAI_CLOTURE_HEURES = 48

    @api.model
    def _cron_gestion_blocages(self):
        """Clôt les études bloquées depuis plus de 48 h ; note la reprise."""
        Mission = self.env["atelier.mission"].sudo()
        Decision = self.env["decision.fiche"].sudo() \
            if "decision.fiche" in self.env else None
        limite = fields.Datetime.subtract(fields.Datetime.now(),
                                          hours=self.DELAI_CLOTURE_HEURES)
        # Les missions bloquées : elles demandent quelque chose (besoins)
        # et ne sont ni terminées ni en cours de rejeu.
        bloquees = Mission.search([
            ("besoins", "!=", False),
            ("etat", "in", ["envoyee", "echec"]),
            ("write_date", "<", limite),
        ], order="id desc", limit=50)
        pour_etude = {}
        for m in bloquees:
            # L'étude liée : par la mission ou ses précédentes.
            etudes = self.search([("mission_ids", "in", m.id)], limit=1)
            if not etudes and m.precedente_id:
                etudes = self.search(
                    [("mission_ids", "in", m.precedente_id.id)], limit=1)
            if not etudes:
                continue
            pour_etude.setdefault(etudes.id, []).append(m)
        clos = 0
        for eid, missions in pour_etude.items():
            e = self.browse(eid)
            if e.etat in ("close",):
                continue
            # Trace : on n'efface rien, on consigne l'echec et la reprise.
            noms = ", ".join("mission %s" % m.id for m in missions[:5])
            e.write({
                "etat": "close",
                "verdict": e.verdict or "a_ignorer",
                "justification": (
                    e.justification or "") + (
                    "\n\n[Clôture automatique, 48 h sans réponse] "
                    "Braignak avait demandé des ressources (%s) et rien "
                    "n'est arrivé dans les 48 h. Affaire classée en échec, "
                    "MAIS reprise possible : si les données demandées "
                    "arrivent, relancer la mission et le chantier repart "
                    "là où il s'était arrêté." % noms),
            })
            e._journaliser(
                "cloture_48h",
                "échec faute de ressources (%s) — reprise possible" % noms)
            # Si une decision attend encore, on la note pour ne pas qu'elle
            # traîne sans objet.
            if Decision is not None:
                for m in missions:
                    dec = Decision.search([
                        ("res_model", "=", "atelier.mission"),
                        ("res_id", "=", m.id),
                        ("etat", "=", "attente")], limit=1)
                    if dec:
                        dec.write({"etat": "archive"})
            clos += 1
        return clos

    def write(self, vals):
        """Previens quand une etude aboutit.

        Sans ca, Braignak travaille, rend son texte, et personne ne le sait :
        l'etude change d'etat dans une fiche que personne ne regarde. Un agent
        dont on n'apprend pas qu'il a fini est un agent qu'on finit par ne
        plus lancer — non parce qu'il est mauvais, mais parce qu'on a pris
        l'habitude de ne rien attendre de lui.

        On previent au CHANGEMENT d'etat seulement, comme la veille : un
        message a chaque ecriture serait du bruit.
        """
        avant = {r.id: r.etat for r in self}
        res = super().write(vals)
        if "etat" not in vals:
            return res
        for rec in self:
            # « analysee » : Braignak a rendu son texte et ses capacites sont
            # extraites. C'est le seul moment ou il y a quelque chose a lire.
            if avant.get(rec.id) == rec.etat or rec.etat != "analysee":
                continue
            rec._prevenir_fin()
        return res

    def _prevenir_fin(self):
        """Passe par le signal COMMUN. Sa propre mecanique a vecu.

        Chaque agent avait sa facon de prevenir, ou ne prevenait pas du tout —
        et c'est ainsi qu'on cesse de lancer un agent : non parce qu'il est
        mauvais, mais parce qu'on a pris l'habitude de ne rien attendre de lui.
        """
        self.ensure_one()
        if "tour.signal" not in self.env:
            return
        capacites = "".join(
            "<li><b>%s</b>%s</li>" % (
                c.name, (" — " + (c.description or "")[:160]) if c.description else "")
            for c in self.capacite_ids[:12])
        corps = _(
            "<p>Source : %(origine)s<br/>Capacités repérées : <b>%(nb)s</b></p>"
            "%(liste)s<p><b>Verdict :</b> %(verdict)s</p>",
            origine=self.source or "—", nb=len(self.capacite_ids),
            liste=("<ul>%s</ul>" % capacites) if capacites else "",
            verdict=dict(self._fields["verdict"].selection or {}).get(
                self.verdict, _("pas encore rendu")))
        self.env["tour.signal"]._signaler(
            agent="Braignak",
            titre=_("Étude terminée : %s") % self.name,
            corps_html=corps,
            # Le nom exact de l action, verifie dans braignak_views.xml.
            # Il disait « action_etude » alors qu elle s appelle
            # « braignak_etude_action » : le bouton du courriel menait a
            # « cette action n existe pas ». Un lien faux dans un
            # courriel est pire qu absent — on clique, et on doute de
            # tout le reste.
            lien="/odoo/action-tour_braignak.braignak_etude_action/%s" % self.id,
            ton="fait",
            enregistrement=self)
        # Le bus : l'étude finie devient un message que les autres agents (et
        # Patrick) peuvent lire sans ouvrir la fiche. C'est le premier circuit
        # réel du bus inter-agents : un agent OBSERVE, un autre pourra s'en
        # servir.
        if "tour.bus.message" in self.env:
            try:
                self.env["tour.bus.message"].sudo()._envoyer(
                    "Braignak", "Patrick",
                    _("Étude terminée : %s") % self.name,
                    _("Verdict : %(verdict)s\nSource : %(origine)s",
                      verdict=dict(self._fields["verdict"].selection or {}).get(
                          self.verdict, _("pas encore rendu")),
                      origine=self.source or "—"))
            except Exception:  # noqa: BLE001 — le bus ne tue pas l'étude
                _logger.warning("Braignak : message au bus raté pour l'étude %s",
                                self.id)

    def _creer_capacites_depuis(self, texte):
        """Crée les capacités de l'étude à partir du bloc CAPACITES du compte
        rendu de Braignak (outil posé le 10/08). Format attendu, en fin de
        compte rendu :

        === CAPACITES ===
        - Nom de la capacité | description en une phrase | fort/moyen/nul
        """
        self.ensure_one()
        import re
        m = re.search(r"===+\s*CAPACITES\s*===+\s*\n(.*?)(\n===+|\Z)",
                      texte or "", re.S | re.I)
        if not m:
            return 0
        nb = 0
        for ligne in m.group(1).splitlines():
            ligne = ligne.strip().lstrip("-*").strip()
            if not ligne or "|" not in ligne:
                continue
            parties = [p.strip() for p in ligne.split("|")]
            nom = parties[0]
            desc = parties[1] if len(parties) > 1 else ""
            interet = "moyen"
            if len(parties) > 2:
                val = parties[2].strip().lower()
                if val in ("fort", "moyen", "nul"):
                    interet = val
            if not nom or len(nom) < 3:
                continue
            self.env["braignak.capacite"].sudo().create({
                "etude_id": self.id,
                "name": nom[:120],
                "description": desc[:500],
                "interet": interet,
            })
            nb += 1
        return nb

    def action_relancer(self):
        """Ouvre le formulaire de relance : pourquoi on relance + nouvelles
        consignes. La validation crée une nouvelle mission pour Braignak qui
        reprend le contexte existant et l'actualise (Patrick, 10/08)."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Relancer l'étude",
            "res_model": "braignak.relance.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_etude_id": self.id},
        }


class BraignakCapacite(models.Model):
    _name = "braignak.capacite"
    _description = "Braignak — capacité repérée dans une application"
    _order = "interet desc, name"

    name = fields.Char("Capacité", required=True)
    etude_id = fields.Many2one("braignak.etude", string="Étude", required=True,
                               ondelete="cascade")
    description = fields.Text("Ce que ça permet")
    interet = fields.Selection(
        [("fort", "Fort — la tour devrait savoir le faire"),
         ("moyen", "Moyen — à noter, pas urgent"),
         ("nul", "Nul — ne correspond pas à la tour")],
        string="Intérêt", default="moyen", required=True)
    existe_deja = fields.Boolean(
        "La tour sait déjà faire",
        help="Coché après vérification dans le Cahier de reproduction, pas de "
             "mémoire.")
    tache_id = fields.Many2one("project.task", string="Tâche créée", readonly=True)

    def action_creer_tache(self):
        """Fait entrer la capacité dans le journal de la tour."""
        Task = self.env["project.task"]
        projet = self.env["project.project"].search(
            [("name", "ilike", "ODOO")], limit=1)
        for rec in self:
            if rec.tache_id or rec.existe_deja:
                continue
            rec.tache_id = Task.create({
                "name": _("Braignak : %s", rec.name),
                "project_id": projet.id or False,
                # `source` est le nom du premier parametre de la fonction de
                # traduction : le passer en mot-clef la percute. Trouve au
                # premier usage reel de ce bouton, le 26/07.
                "description": _(
                    "<p>Capacité repérée par Braignak dans <b>%(app)s</b> "
                    "(%(origine)s).</p><p>%(desc)s</p>"
                    "<p><i>Vérifier dans le Cahier de reproduction que la tour "
                    "ne sait pas déjà le faire avant d'ouvrir le chantier.</i></p>",
                    app=rec.etude_id.name, origine=rec.etude_id.source,
                    desc=rec.description or ""),
            }).id
            rec.etude_id._journaliser("tache_creee", "%s -> tâche %s" % (
                rec.name, rec.tache_id.id))
        return True


class BraignakJournal(models.Model):
    """Ce que Braignak a fait, dans l'ordre. Ne se modifie pas, ne s'efface pas.

    Les droits (ir.model.access) n'accordent que la lecture et la création.
    C'est volontaire et c'est le point : un observateur dont on peut réécrire
    l'historique ne s'observe plus.
    """

    _name = "braignak.journal"
    _description = "Braignak — journal des actions"
    _order = "create_date desc"

    etude_id = fields.Many2one("braignak.etude", string="Étude", ondelete="restrict")
    action = fields.Char("Action", required=True)
    detail = fields.Text("Détail")
    utilisateur_id = fields.Many2one("res.users", string="Demandé par")

    def write(self, vals):
        raise UserError(_("Le journal de Braignak ne se modifie pas."))

    def unlink(self):
        raise UserError(_("Le journal de Braignak ne s'efface pas."))


class BraignakRelanceWizard(models.TransientModel):
    """Pourquoi on relance une étude + les nouvelles consignes. Braignak
    reprend l'étude existante, intègre le changement et rend un verdict à
    jour (Patrick, 10/08)."""

    _name = "braignak.relance.wizard"
    _description = "Braignak — relance d'une étude"

    etude_id = fields.Many2one("braignak.etude", string="Étude", required=True)
    raison = fields.Text("Pourquoi on relance", required=True)
    consignes = fields.Text("Nouvelles consignes")
    donnees = fields.Text("Nouvelles données")

    def valider(self):
        self.ensure_one()
        etude = self.etude_id
        Mission = self.env["atelier.mission"].sudo()
        contexte = (etude.observations or "")[:6000]
        raison = (self.raison or "").strip()
        nouvelles = (self.consignes or "").strip()
        donnees = (self.donnees or "").strip()
        consigne = _(
            "RELANCE DE L'ÉTUDE : %(nom)s\n\n"
            "Cette étude existe déjà et a été analysée. Le contexte a changé "
            "(marché, tour, données) : on te demande une étude À JOUR, pas une "
            "copie.\n\n"
            "POURQUOI ON RELANCE :\n%(raison)s\n\n"
            "NOUVELLES CONSIGNES :\n%(nouvelles)s\n\n"
            "NOUVELLES DONNÉES :\n%(donnees)s\n\n"
            "Reprends ce qui reste vrai de l'étude précédente, corrige ce qui "
            "a changé, revérifie les sources, et rends un verdict à jour "
            "(à prototyper / à reprendre / à ignorer).\n\n"
            "=== CONTEXTE DE L'ÉTUDE PRÉCÉDENTE ===\n%(contexte)s",
            nom=etude.name,
            raison=raison or "(non précisée)",
            nouvelles=nouvelles or "(aucune — vérifie si l'ancienne étude tient "
            "encore)",
            donnees=donnees or "(aucune)",
            contexte=contexte or "(vide)")
        dispo = [m[0] for m in Mission._moteurs_disponibles()]
        moteur = "braignak" if "braignak" in dispo else (
            "deepseek-agent" if "deepseek-agent" in dispo else "claude")
        mission = Mission.create({
            "name": _("Braignak — relance : %s", etude.name),
            "consigne": consigne,
            "moteur": moteur,
        })
        mission.action_envoyer()
        etude._journaliser("relance",
                           "relance demandée (mission %s)" % mission.id)
        etude.write({"etat": "observation", "mission_ids": [(4, mission.id)]})
        return {"type": "ir.actions.act_window_close"}
