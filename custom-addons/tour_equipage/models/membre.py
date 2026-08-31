# -*- coding: utf-8 -*-
"""L'équipe — des personnages dont l'expérience se gagne, jamais ne se saisit.

La demande était : « leur expérience doit être visible et leur évolution comme
des skills de personnages RPG ». Le piège d'une telle demande est de fabriquer
une décoration : des barres jolies qu'un administrateur remplit à la main. Une
jauge qu'on peut écrire ne renseigne sur rien — elle raconte l'humeur de celui
qui l'a écrite.

Ici, **l'expérience n'est pas un champ, c'est une somme**. Chaque compétence
compte des enregistrements qui existent déjà dans la tour : une mission rendue,
un constat de sécurité accepté, une régression trouvée, un guide écrit. Le
niveau se déduit du total. Aucun champ n'est modifiable — ni par l'utilisateur,
ni par l'administrateur, ni par un agent.

Conséquence assumée, et c'est la bonne : **un agent qu'on n'utilise pas reste
au niveau 1**, et ça se voit. Tess vient d'être recrutée et n'a rien fait — sa
fiche le dit. C'est plus utile qu'un niveau de complaisance.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Les paliers d'expérience. Volontairement écartés : passer un niveau doit
# demander plusieurs jours de travail réel, sinon tout le monde est maître en
# une semaine et l'échelle ne distingue plus personne.
SEUILS = [0, 20, 60, 140, 300, 600, 1000, 1600, 2500, 4000]

TITRES = [
    ("Novice", "見習い", "Vient d'arriver. Son périmètre est écrit, rien n'est encore prouvé."),
    ("Apprenti", "弟子", "A fait le travail au moins quelques fois, sans surprise."),
    ("Confirmé", "職人", "Tourne seul. On lui confie sans relire par-dessus l'épaule."),
    ("Vétéran", "達人", "A rencontré les cas tordus et les a réglés."),
    ("Maître", "名人", "Sa spécialité n'est plus discutée dans la tour."),
    ("Sage", "賢者", "Ses arbitrages font jurisprudence. On vient le consulter."),
    ("Légende", "伝説", "Son nom seul ouvre les portes. Le travail le cherche."),
    ("Titan", "巨神", "Il soulève ce que les autres appellent des problèmes."),
    ("Immortel", "不滅", "Il a vu la tour changer d'ère et il l'a portée."),
    ("Mythe", "神話", "Ce qu'il a bâti tient debout sans lui — c'est la réussite finale."),
]

# Le catalogue des compteurs. Chacun dit : quoi compter, où, et ce que ça vaut.
#
# Règle de composition : on ne compte QUE ce qui a déjà une existence propre
# dans la base. Si un chiffre demande d'inventer un enregistrement pour être
# mesuré, c'est qu'on est en train de fabriquer la mesure plutôt que de la
# lire — et une mesure fabriquée finit toujours par être flatteuse.
COMPTEURS = {
    # Clark — le développeur
    "clark_missions": ("Missions menées à terme", "atelier.mission",
                       [("etat", "=", "terminee")], 6),
    "clark_fils": ("Conversations suivies", "discussion.fil", [], 4),
    # Lois — la relecture
    "lois_relectures": ("Relectures rendues", "atelier.mission",
                        [("etat", "=", "terminee"), ("moteur", "=", "lois")], 10),
    # Victor — la sécurité
    "victor_constats": ("Constats retenus", "securite.constat",
                        [("etat", "in", ["accepte", "resolu"])], 8),
    "victor_passages": ("Contrôles passés", "securite.constat", [], 2),
    # Jimmy / Vibe — la recette
    "jimmy_passages": ("Passages de recette", "recette.passage", [], 4),
    "jimmy_regressions": ("Régressions attrapées", "recette.resultat",
                          [("etat", "=", "ko"), ("critique", "=", True)], 8),
    # Braignak — l'observateur
    "braignak_etudes": ("Études menées", "braignak.etude",
                        [("etat", "in", ["analysee", "prototype", "close"])], 12),
    "braignak_capacites": ("Capacités identifiées", "braignak.capacite", [], 3),
    # Predateur (22/08) : ce que Braignak a rapporte du DEHORS et qui manquait
    # Piege paye le 22/08 : Odoo ne distingue PAS une case jamais remplie d une
    # case decochee. Les 171 non jugees apparaissent donc deja comme « pas deja
    # presentes » dans la tour. Le nom du compteur dit donc exactement ce qu il
    # compte, sans gonfler en douce. Juger ces 171 est un chantier a part.
    "predateur": ("Predateur - rapportees, non reconnues comme deja presentes",
                  "braignak.capacite", [("existe_deja", "=", False)], 10),
    # La détection de circuits (31/07) : chaque gabarit proposé par la
    # détection de compétence (circuit.modele.detecte) est une capacité vue
    # avant d'exister. Compteur partagé, branché sur TOUS les agents : quand
    # un brouillon est proposé, chaque agent « voit » une capacité de plus.
    "detection_circuits": ("Circuits proposés (détection)",
                           "circuit.modele", [("detecte", "=", True)], 5),
    # Perry — la documentation.
    #
    # Tentation écartée : lui compter les 44 guides déjà écrits. Ils existent,
    # mais ce n'est pas lui qui les a écrits — il n'est pas construit. Le faire
    # naître au niveau 3 aurait rendu toute l'échelle décorative dès le premier
    # jour. Son compteur mesure SON geste à lui : refuser une livraison qui
    # n'a pas de guide.
    "perry_refus": ("Livraisons refusées faute de guide", "perry.refus", [], 6),
    # Oliver — l'électronicien. Son premier travail réel est l'avis qu'il
    # rend en débat (le matériel se chiffre avant de se souder) : c'est donc
    # ça qu'on compte — comme Lois est filtrée par son moteur, lui l'est par
    # son nom de participant. Sans ce compteur, Emil le déclarait « muet »
    # alors que son avis était rendu (28/07).
    "oliver_avis": ("Avis rendus en débat", "debat.avis",
                    [("membre_id.name", "=", "Oliver"),
                     ("reponse", "!=", False)], 8),
    # Martha — le droit. Même logique qu'Oliver : son travail réel est
    # l'avis qu'elle rend, et il se compte par son nom de participante.
    "martha_avis": ("Avis juridiques rendus", "debat.avis",
                    [("membre_id.name", "=", "Martha"),
                     ("reponse", "!=", False)], 8),
    # Chloe — l'assistante
    "chloe_echanges": ("Échanges tenus", "copilote.usage", [], 1),
    # Ses apps construites (01/08) : les missions « App demandée par … » menées
    # à terme sont SES livraisons — le copilote est le seul chemin qui construit.
    "chloe_apps": ("Apps construites", "atelier.mission",
                   [("name", "ilike", "App demandée par%"),
                    ("etat", "=", "terminee")], 8),
    # Jonathan — le courrier. Détecter vaut peu, mener au bout vaut plus :
    # un besoin ne compte vraiment que quand le message est parti.
    "jonathan_besoins": ("Besoins d'échange détectés", "echange.besoin", [], 2),
    "jonathan_envois": ("Courriers menés au bout", "echange.besoin",
                        [("etat", "=", "envoye")], 6),
    # Le déploiement
    "sites_livres": ("Sites mis en ligne", "deploiement.site", [], 10),
    # opencode / Raphaël — l'inspecteur d'éléments (04/08) : chaque
    # vérification à l'écran (résultats de recette) est une inspection.
    # Compteur partagé, comme detection_circuits.
    "inspecteur_elements": ("Inspections navigateur (DOM/styles/JS)", "recette.resultat", [], 2),
    # Le commercial (01/08) — embauché pour qualifier, proposer, conclure.
    # Ses gestes se mesurent sur ce qui existe : les offres publiées et les
    # contrats actifs — rien de fabriqué pour lui faire du XP.
    "commercial_offres": ("Offres commerciales en place",
                          "abonnement.offre", [], 4),
    "commercial_contrats": ("Contrats actifs",
                            "abonnement.contrat",
                            [("etat", "=", "actif")], 6),
    # Patrick — le design et l'architecture. Son œuvre n'est ni une mission
    # ni une décision : c'est une LIVRAISON (un site, une maquette, un plan
    # d'architecture). Le compteur lit le carnet des livraisons, où chaque
    # ligne est un livrable vérifiable daté — pas une intention.
    "patrick_livraisons": ("Livraisons de design & architecture",
                           "equipe.livraison",
                           [("membre_id.name", "=", "Patrick")], 10),
    # Les enchaînements (04/08) — déclarés en graine le 04/08 sans entrée ici,
    # donc muets (même piège que Raphaël le 31/07). Compteurs partagés comme
    # inspecteur_elements : le geste est collectif, le chiffre est réel.
    "enchainement_demandes": ("Missions enchaînées", "atelier.mission",
                              [("precedente_id", "!=", False)], 2),
    "enchainement": ("Chaînes menées au bout", "atelier.mission",
                     [("precedente_id", "!=", False),
                      ("etat", "=", "terminee")], 3),
    # Le journal de travail (circuit 19) : chaque porte franchie laisse une
    # trace — c'est le passage qui compte, pas l'intention.
    "journal_travail": ("Portes franchies et consignées", "circuit.passage",
                        [], 1),
    # La réécriture de la virtualité (circuit 121, Patrick) : chaque
    # correction du clone est une réécriture du monde virtuel — mesurée sur
    # clone.feedback, jamais posée à la main.
    "virtualite": ("Réécritures du monde virtuel", "clone.feedback", [], 3),
    # Le signal commun — toute l'équipe
    "signaux": ("Comptes rendus émis", "tour.signal", [], 1),
    # Mirline — les tests du cahier (03/08) : chaque passage vert la fait monter.
    "mirline_tests": ("Tests du cahier passés", "recette.passage", [], 2),
    # Tess — les coûts. Rien à compter tant qu'elle n'est pas construite : la
    # ligne existe pour que son absence soit VISIBLE plutôt que silencieuse.
    "tess_releves": ("Relevés de coûts", "tess.releve", [], 5),
    # Patrick — le propriétaire. Mesure le cap qu'il tranche : une décision
    # approuvée ou rejetée, c'est un choix fait.
    "patrick_decisions": ("Décisions tranchées", "decision.fiche",
                          [("etat", "in", ["approuve", "rejete"]),
                           ("user_id", "=", 2)], 4),
    # Patrick — actions sur les tâches du journal ODOO
    "patrick_taches": ("Tâches closes", "project.task",
                       [("stage_id.name", "=", "Fait")], 3),
    # Patrick — le module Quêtes (01/08). Une quête accomplie est un fait
    # mesurable : search_count des quêtes terminées. L'XP n'est JAMAIS posée
    # à la main — c'est la relève qui compte et qui consigne le gain.
    "patrick_quetes": ("Quêtes de carrière accomplies", "quete.fiche",
                       [("etat", "=", "faite")], 10),
    # Raphaël — le bâtisseur. Il converse, construit, conçoit : chaque échange
    # dans le copilote est son travail.
    "raphael_echanges": ("Échanges tenus", "copilote.usage", [], 1),
    # Raphaël — les décisions techniques qu'il arbitre. Mesuré le 31/07 :
    # le compteur était déclaré en graine (seed membres.xml) sans entrée ici,
    # donc `_mesurer` le sautait (if not desc: continue) et sa valeur restait
    # à 0. Il compte les décisions approuvées — le choix d'architecture qu'il
    # a fait aboutir — comme Patrick compte les siennes.
    "raphael_decisions": ("Décisions techniques arbitrées", "decision.fiche",
                          [("etat", "=", "approuve")], 4),
    # Raphaël — les conversations d'architecture. Autre code que
    # `raphael_echanges` : avant le 31/07 les deux fiches (Échanges tenus et
    # Conversations d'architecture) portaient le même code, et `_mesurer`
    # écrivait les deux avec la même valeur en écrasant l'une par l'autre.
    "raphael_conversations": ("Conversations d'architecture",
                              "copilote.usage", [], 1),
    # Emil — la cohérence. Chaque écart qu'il détecte est un défaut évité.
    "emil_ecarts": ("Écarts détectés", "coherence.ecart", [], 6),
    # Pete — le greffier. Chaque exploit enregistré est son œuvre.
    "pete_exploits": ("Faits d'armes enregistrés", "equipe.exploit",
                      [("code", "!=", "pete_exploits")], 1),
    # Jor-El — le chef formation. Les guides qu'il crée forment l'équipe.
    "jorel_parcours": ("Guides créés", "tour.guide", [], 3),
    # Raph — l'opérateur (opencode). Son travail n'est pas une mission :
    # ce sont les circuits qu'il conçoit, les garde-fous qu'il pose, les
    # guides qu'il publie et les sites qu'il met en ligne. Ancré au 31/07 —
    # son jour de prise de service — pour ne pas digérer l'héritage des
    # prédécesseurs. atelier et moteurs, eux, n'ont pas encore de registre
    # mesurable : on ne compte que ce qui existe.
    "raph_circuits": ("Circuits conçus", "circuit.modele", [], 8),
    "raph_garde_fous": ("Garde-fous en place", "garde_fou.garde_fou", [], 4),
    "raph_vitrine": ("Guides publiés sur la vitrine", "tour.guide", [], 3),
    "raph_deploiement": ("Sites mis en ligne", "deploiement.site", [], 8),
    # Lex — le contrôle qualité (embauché 05/08). Son geste propre : rendre un
    # verdict de conformité VÉRIFIÉ sur le travail d'un autre agent. Mesuré sur
    # le carnet des livraisons marquées conformes — jamais posé à la main, et
    # pas de réutilisassions : Jimmy compte les recettes, Emil les écarts.
    "lex_verifications": ("Livraisons vérifiées et conformes", "equipe.livraison",
                          [("conformite_validee", "=", True)], 8),
}

# Paliers d'une compétence : combien d'unités pour chaque étoile.
PALIERS_COMPETENCE = [1, 3, 8, 20, 50]


class EquipeMembre(models.Model):
    _name = "equipe.membre"
    _description = "Membre de l'équipe"
    _order = "sequence, id"

    name = fields.Char("Nom", required=True)
    poste = fields.Char("Poste", required=True)
    embleme = fields.Char("Emblème", default="🛠️",
                          help="Un caractère, affiché sur sa fiche.")
    sequence = fields.Integer(default=10)
    actif_le = fields.Date("Rejoint le")
    active = fields.Boolean("Actif", default=True)

    perimetre = fields.Html("Son périmètre")
    refus = fields.Html("Ce qu'il ne fait pas",
                        help="Aussi important que le périmètre : c'est ce qui "
                             "empêche un agent de déborder sur le voisin.")
    origine = fields.Char("Pourquoi ce nom")

    # TRAVAILLER AVEC LUI, pas seulement lire ses rapports.
    #
    # Patrick, devant l'écran Sécurité : « je vois les constats de Victor mais
    # je ne peux ni lui parler, ni améliorer ses consignes, ni faire un truc
    # avec lui ». Un agent auquel on ne peut rien dire n'est pas un collègue,
    # c'est un rapport qu'on subit.
    moteur = fields.Char(
        "Moteur", help="Le script qui le fait parler (~/atelier/moteurs/<nom>.sh). "
                       "Vide = agent sans conversation, comme Victor.")
    consignes = fields.Text(
        "Mes consignes pour lui",
        help="Ce que tu veux qu'il garde en tête à CHAQUE fois. C'est envoyé en "
             "tête de chaque nouvelle conversation avec lui — donc ce que tu "
             "écris ici arrive vraiment jusqu'à lui, ce n'est pas une note.")
    exemples = fields.Text(
        "Exemples de ce qu'il sait faire",
        help="Trois ou quatre demandes types. Sert à savoir quoi lui confier "
             "sans deviner.")

    competence_ids = fields.One2many("equipe.competence", "membre_id", "Compétences")
    livraison_ids = fields.One2many("equipe.livraison", "membre_id", "Livraisons")

    xp = fields.Integer("Expérience", compute="_calculer", store=True)
    niveau = fields.Integer("Niveau", compute="_calculer", store=True)
    titre = fields.Char("Titre", compute="_calculer", store=True)
    titre_jp = fields.Char("Titre (japonais)", compute="_calculer", store=True)
    titre_sens = fields.Char("Ce que dit le titre", compute="_calculer", store=True)
    xp_palier = fields.Integer("Palier suivant", compute="_calculer", store=True)
    avancement = fields.Integer("Avancement dans le niveau (%)",
                                compute="_calculer", store=True)

    @api.depends("competence_ids.xp")
    def _calculer(self):
        for m in self:
            m.xp = sum(m.competence_ids.mapped("xp"))
            niveau = 1
            for i, seuil in enumerate(SEUILS):
                if m.xp >= seuil:
                    niveau = i + 1
            m.niveau = niveau
            libelle, jp, sens = TITRES[niveau - 1]
            m.titre, m.titre_jp, m.titre_sens = libelle, jp, sens
            bas = SEUILS[niveau - 1]
            haut = SEUILS[niveau] if niveau < len(SEUILS) else None
            m.xp_palier = haut or 0
            if haut is None:
                # Au dernier niveau la barre est pleine. Une barre qui continue
                # de monter sans palier suivant ment sur ce qui reste à faire.
                m.avancement = 100
            else:
                m.avancement = int(round(100.0 * (m.xp - bas) / max(1, haut - bas)))

    def action_parler(self):
        """Ouvrir une conversation avec CET agent, ses consignes déjà en tête."""
        self.ensure_one()
        if not self.active:
            from odoo.exceptions import UserError
            raise UserError(_("%s est éteint : rallume-le avant de lui parler.",
                              self.name))
        if not self.moteur:
            from odoo.exceptions import UserError
            raise UserError(_(
                "%s ne tient pas de conversation : il ne consomme aucune "
                "intelligence artificielle, par construction. Pour le faire "
                "évoluer, écris tes consignes sur sa fiche — elles seront "
                "reprises la prochaine fois qu'on touche à son code.") % self.name)
        Fil = self.env["discussion.fil"]
        fil = Fil.search([("agent_id", "=", self.id),
                          ("user_id", "=", self.env.user.id)],
                         order="write_date desc", limit=1)
        if not fil:
            fil = Fil.create({"name": "Avec %s" % self.name, "agent_id": self.id})
        return {
            "type": "ir.actions.act_window",
            "name": "Avec %s" % self.name,
            "res_model": "discussion.fil",
            "res_id": fil.id,
            "view_mode": "form",
        }

    def action_recalculer(self):
        self.mapped("competence_ids")._mesurer()
        return True

    def action_confier_mission(self):
        """Confier une mission à CET agent, depuis sa fiche.

        Patrick, 29/07 : « je ne peux rien envoyer à l'atelier » — depuis
        l'équipe et le registre, aucun chemin ne menait à une mission. Le
        bouton ouvre une mission en création, moteur prérempli. Motif
        « module absent = pas de bouton » : l'atelier peut ne pas être
        installé (instance cliente), on le dit au lieu de planter.
        """
        self.ensure_one()
        from odoo.exceptions import UserError
        if "atelier.mission" not in self.env:
            raise UserError(_(
                "L'atelier n'est pas installé sur cette base : il n'y a "
                "personne pour exécuter une mission ici."))
        if not self.moteur:
            raise UserError(_(
                "%s n'a pas de moteur : il ne peut pas recevoir de mission. "
                "Choisis un membre dont la fiche porte un moteur.") % self.name)
        if not self.active:
            raise UserError(_("%s est éteint : rallume-le avant de lui "
                              "confier une mission.", self.name))
        return {
            "type": "ir.actions.act_window",
            "name": _("Confier une mission à %s") % self.name,
            "res_model": "atelier.mission",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_moteur": self.moteur,
                "default_name": _("Pour %s : ") % self.name,
            },
        }

    def action_basculer_activite(self):
        """Éteindre ou rallumer UN agent (admin seulement).

        Patrick, 31/07 : « peut-on éteindre, allumer un agent et ses
        actions ? ». Éteint, un agent ne reçoit plus de nouvelle conversation
        ni de nouvelle mission « Confier » — ses consignes restent, son
        historique reste, on peut le rallumer à tout moment. Seul l'admin de
        la tour (group_system) peut le faire : éteindre un collègue n'est pas
        une décision qu'on délègue.
        """
        self.ensure_one()
        if not self.env.user.has_group("base.group_system"):
            from odoo.exceptions import UserError
            raise UserError(_(
                "Seul l'admin de la tour peut éteindre ou rallumer un agent."))
        self.active = not self.active
        return True

    # ------------------------------------------------------------------
    # Le tableau de bord d'un agent : ce qu'il a fait, ce qui l'attend.
    #
    # Patrick voulait « le même accueil que le mien, mais pour chaque dev ».
    # Le principe est le même que son accueil à lui : on ne montre PAS tout ce
    # qui existe, on montre ce qui a bougé et ce qui attend quelqu'un. Un
    # tableau de bord qui liste tout est une archive, pas un tableau de bord.
    #
    # Chaque agent lit ses PROPRES sources — Clark ses missions, Victor ses
    # constats, Lois ses relectures. Le lien se fait par le code de compétence
    # déjà déclaré sur la fiche : rien à configurer en double, et un agent
    # nouveau alimente son tableau dès qu'il a une compétence.
    # ------------------------------------------------------------------
    def _travaux(self, limite=8):
        """Les dernières traces réelles de cet agent. Jamais d'invention.

        Rend une liste de dicts : {quoi, quand, etat, ok}. Chaque source est
        isolée : un modèle absent (agent pas encore construit, module retiré
        chez un client) rend une liste vide, il n'emporte pas les autres.
        """
        self.ensure_one()
        codes = set(self.competence_ids.mapped("code"))
        lignes = []

        def ajouter(modele, domaine, libelle, etat_champ=None, ordre="create_date desc"):
            if modele not in self.env:
                return
            try:
                with self.env.cr.savepoint():
                    for r in self.env[modele].sudo().search(domaine, limit=limite, order=ordre):
                        etat = getattr(r, etat_champ, "") if etat_champ else ""
                        avancement = ""
                        if modele == "atelier.mission" and "avancement" in r._fields:
                            avancement = r.avancement or "non_consigne"
                        lignes.append({
                            "quoi": (getattr(r, "name", "") or libelle)[:70],
                            "quand": r.create_date,
                            "etat": etat or "",
                            "ok": etat in ("terminee", "resolu", "accepte", "close", "analysee"),
                            "avancement": avancement,
                        })
            except Exception:
                return

        if "clark_missions" in codes:
            ajouter("atelier.mission", [("moteur", "not in", ["lois"])], "Mission", "etat")
        if "clark_fils" in codes:
            ajouter("discussion.fil", [], "Conversation")
        if "lois_relectures" in codes:
            ajouter("atelier.mission", [("moteur", "=", "lois")], "Relecture", "etat")
        if "victor_constats" in codes or "victor_passages" in codes:
            ajouter("securite.constat", [], "Constat", "etat")
        if "jimmy_passages" in codes:
            ajouter("recette.passage", [], "Passage de recette")
        if "braignak_etudes" in codes:
            ajouter("braignak.etude", [], "Étude", "etat")

        lignes.sort(key=lambda x: x["quand"] or "", reverse=True)
        return lignes[:limite]

    def _evolution(self, limite=12):
        """Le tableau d'évolution de l'agent : ses missions avec l'avancement
        qu'il a consigné (fait / en cours / pas fait) et ses étapes.

        Règle du propriétaire (31/07) : chaque agent consigne où il en est
        dans sa tâche. Cette méthode lit ce que la relève a capté du compte
        rendu (champs atelier.mission.avancement / etape_ids) et le rend pour
        la fiche de l'agent. Rien n'est inventé : absent = liste vide.
        """
        self.ensure_one()
        if not (self.moteur or "").strip() or "atelier.mission" not in self.env:
            return []
        try:
            with self.env.cr.savepoint():
                missions = self.env["atelier.mission"].sudo().search(
                    [("moteur", "=", self.moteur)],
                    order="create_date desc", limit=limite)
                retour = []
                for m in missions:
                    etapes = []
                    if "etape_ids" in m._fields:
                        etapes = [{"nom": e.nom, "etat": e.etat}
                                  for e in m.etape_ids]
                    avancement = "non_consigne"
                    if "avancement" in m._fields:
                        avancement = m.avancement or "non_consigne"
                    retour.append({
                        "id": m.id,
                        "quoi": (m.name or "")[:70],
                        "quand": m.create_date,
                        "etat": m.etat,
                        "ok": m.etat == "terminee",
                        "avancement": avancement,
                        "detail": (m.avancement_detail or "")[:220],
                        "etapes": etapes,
                    })
                return retour
        except Exception:  # noqa: BLE001
            return []

    def _consommation(self, jours=30):
        """Ce que cet agent a coûté et produit sur la période.

        Patrick voulait suivre le travail de Chloe : ce qu'elle a fait, ce qui
        lui reste. La deuxième moitié se lit dans ses travaux ; la première
        manquait — et c'est celle qui coûte de l'argent.

        Rend None quand l'agent ne consomme rien : Victor, Jimmy et Tess sont
        du code déterministe. Afficher « 0,00 EUR » sur leur fiche laisserait
        croire qu'on les mesure alors qu'il n'y a rien à mesurer, et un zéro
        qu'on ne peut pas distinguer d'une absence de mesure ne renseigne pas.
        """
        self.ensure_one()
        if "chloe_echanges" not in set(self.competence_ids.mapped("code")):
            return None
        if "copilote.usage" not in self.env:
            return None
        try:
            with self.env.cr.savepoint():
                debut = fields.Date.subtract(fields.Date.context_today(self),
                                             days=jours)
                lignes = self.env["copilote.usage"].sudo().search(
                    [("jour", ">=", debut)])
                if not lignes:
                    return {"echanges": 0, "cout": 0.0, "entree": 0,
                            "sortie": 0, "jours": jours, "par_jour": 0.0}
                cout = sum(lignes.mapped("cout_estime") or [0.0])
                return {
                    "echanges": len(lignes),
                    "cout": cout,
                    "entree": sum(lignes.mapped("tokens_entree") or [0]),
                    "sortie": sum(lignes.mapped("tokens_sortie") or [0]),
                    "jours": jours,
                    # Le coût par jour dit ce que ça fera sur un mois : un
                    # total sur trente jours ne se projette pas tout seul.
                    "par_jour": cout / max(1, jours),
                }
        except Exception:
            return None

    def _attente(self):
        """Ce qui attend cet agent — la seule partie qui demande une action."""
        self.ensure_one()
        codes = set(self.competence_ids.mapped("code"))
        att = []
        if ("victor_constats" in codes) and "securite.constat" in self.env:
            try:
                with self.env.cr.savepoint():
                    n = self.env["securite.constat"].sudo().search_count(
                        [("etat", "in", ["propose", "attente"])])
                    if n:
                        att.append("%s constat(s) de sécurité à trancher" % n)
            except Exception:
                pass
        if "atelier.mission" in self.env:
            try:
                with self.env.cr.savepoint():
                    moteur = "lois" if "lois_relectures" in codes else None
                    dom = [("etat", "=", "envoyee")]
                    if moteur:
                        dom.append(("moteur", "=", moteur))
                    elif "clark_missions" in codes:
                        dom.append(("moteur", "not in", ["lois"]))
                    else:
                        dom = None
                    if dom:
                        n = self.env["atelier.mission"].sudo().search_count(dom)
                        if n:
                            att.append("%s mission(s) en cours" % n)
            except Exception:
                pass
        if not self.competence_ids.filtered(lambda c: c.valeur):
            att.append("Jamais utilisé — il n'a encore rien produit")
        return att

    @api.model
    def _cron_mesurer(self):
        """Une mesure par jour. L'expérience d'une équipe ne se regarde pas en
        temps réel : ce qui compte est la pente sur des semaines.

        ET UNE MONTÉE DE NIVEAU SE FÊTE. Patrick, le 28/07 : « notifie tous
        ceux qui montent en compétence, dans leur module — gamification ».
        Un niveau qui monte en silence ne motive personne ; un niveau annoncé
        donne envie de voir le suivant. On compare AVANT et APRÈS la mesure :
        la seule façon honnête de détecter la montée, puisque les niveaux
        sont calculés et jamais saisis.
        """
        membres = self.sudo().search([])
        avant = {m.id: m.niveau for m in membres}
        self.env["equipe.competence"].sudo().search([])._mesurer()
        for m in membres:
            if m.niveau <= avant.get(m.id, m.niveau):
                continue
            # PAS de message_post ici : equipe.membre n'herite pas de
            # mail.thread, et l'appel leve AttributeError — decouvert en
            # retestant a la main, AVANT que le cron ne plante en silence
            # cette nuit. Le trophee passe par le signal, qui arrive par
            # courriel et dans les notifications : plus visible qu'un
            # message de fiche, de toute facon.
            if "tour.signal" in self.env:
                try:
                    self.env["tour.signal"]._signaler(
                        agent="L'équipe",
                        titre=_("🏆 %(nom)s passe au niveau %(niv)s",
                                nom=m.name, niv=m.niveau),
                        corps_html=_(
                            "<p><b>%(nom)s</b> vient de passer "
                            "<b>niveau %(niv)s — %(titre)s</b>, avec %(xp)s "
                            "points d'expérience. Les niveaux se gagnent en "
                            "travaillant : celui-ci raconte du travail "
                            "réellement fait.</p>",
                            nom=m.name, niv=m.niveau,
                            titre=m.titre or "", xp=m.xp),
                        ton="fait")
                except Exception:  # noqa: BLE001 — la fete ne casse pas la mesure
                    _logger.exception("Équipe : signal de niveau raté")


class EquipeCompetence(models.Model):
    _name = "equipe.competence"
    _description = "Compétence d'un membre de l'équipe"
    _order = "membre_id, sequence, id"

    membre_id = fields.Many2one("equipe.membre", "Membre", required=True,
                                ondelete="cascade")
    name = fields.Char("Compétence", required=True)
    code = fields.Char("Compteur", required=True,
                       help="Clef du catalogue COMPTEURS : ce qui est réellement compté.")
    sequence = fields.Integer(default=10)
    confidentiel = fields.Boolean(
        "Confidentielle", default=False,
        help="Masquée du public : la compétence n'apparaît que connecté (pilote). "
             "Pour les compétences sensibles (sécurité, bas niveau, exploitation).")

    valeur = fields.Integer("Compté", readonly=True)
    xp = fields.Integer("Expérience", readonly=True)
    etoiles = fields.Integer("Étoiles", readonly=True)
    mesure_le = fields.Datetime("Dernière mesure", readonly=True)
    depuis = fields.Date(
        "Compter à partir du",
        help="Vide : on compte tout l'historique (les agents établis). Renseigné "
             "à l'embauche : on ne compte que ce qui vient APRÈS cette date — "
             "pas de XP rétroactif pour un agent qui vient de naître.")
    quoi = fields.Char("Ce qui est compté", compute="_dire_quoi")
    barre = fields.Integer("Progression vers l'étoile suivante (%)",
                           compute="_dire_quoi")

    @api.depends("code", "valeur", "etoiles")
    def _dire_quoi(self):
        for c in self:
            desc = COMPTEURS.get(c.code)
            c.quoi = desc[0] if desc else "compteur inconnu"
            if c.etoiles >= len(PALIERS_COMPETENCE):
                c.barre = 100
            else:
                bas = PALIERS_COMPETENCE[c.etoiles - 1] if c.etoiles else 0
                haut = PALIERS_COMPETENCE[c.etoiles]
                c.barre = int(round(100.0 * (c.valeur - bas) / max(1, haut - bas)))

    # ------------------------------------------------------------------
    # LE VERROU. Le docstring du module promet : « Aucun champ n'est
    # modifiable — ni par l'utilisateur, ni par l'administrateur, ni par un
    # agent. » La promesse ne tenait que par le `readonly` des vues, qui se
    # laisse contourner par n'importe quel `write()` en code. Seule la mesure
    # (`_mesurer`, sous le contexte `mesure_xp`) a le droit d'écrire ces
    # champs : valeur, xp, etoiles, mesure_le. Tout le reste est refusé.
    # ------------------------------------------------------------------
    CHAMPS_MESURES = {"valeur", "xp", "etoiles", "mesure_le"}

    @api.model_create_multi
    def create(self, vals_list):
        if not self._context.get("mesure_xp"):
            for vals in vals_list:
                if self.CHAMPS_MESURES & set(vals):
                    raise UserError(_(
                        "Les compteurs d'expérience ne se saisissent pas : ils "
                        "se mesurent. Seule la relève peut les écrire."))
        return super().create(vals_list)

    def write(self, vals):
        if not self._context.get("mesure_xp"):
            if self.CHAMPS_MESURES & set(vals):
                raise UserError(_(
                    "Les compteurs d'expérience ne se saisissent pas : ils "
                    "se mesurent. Seule la relève peut les écrire."))
        return super().write(vals)

    def _mesurer(self):
        """Relit les compteurs et consigne ce qui a bougé.

        Chaque compteur est isolé dans son propre point de reprise. Sans ça, un
        modèle absent (Tess n'est pas construite, un module désinstallé chez un
        client) laisse la transaction PostgreSQL en état abandonné et TOUS les
        compteurs suivants échouent — y compris ceux qui allaient très bien.
        Une mesure qui s'effondre en entier parce qu'une seule ligne manque
        n'est pas une mesure, c'est un pari.
        """
        self = self.with_context(mesure_xp=True)
        Exploit = self.env["equipe.exploit"].sudo()
        maintenant = fields.Datetime.now()
        for c in self:
            desc = COMPTEURS.get(c.code)
            if not desc:
                continue
            libelle, modele, domaine, poids = desc
            if c.depuis:
                # LE GARDE ANTI-RÉTROACTIF. Une compétence née aujourd'hui ne
                # doit pas digérer des années d'historique d'un coup — sinon le
                # compteur est une truite qu'on engraisse. On borne le domaine
                # à ce qui est créé APRÈS la date d'ancrage de la compétence.
                domaine = list(domaine) + [(
                    "create_date", ">=",
                    fields.Datetime.to_string(
                        fields.Datetime.from_string(str(c.depuis))))]
            valeur = 0
            if modele in self.env:
                try:
                    with self.env.cr.savepoint():
                        valeur = self.env[modele].sudo().search_count(domaine)
                except Exception:
                    valeur = c.valeur or 0
            gain = valeur - (c.valeur or 0)
            etoiles = 0
            for i, palier in enumerate(PALIERS_COMPETENCE):
                if valeur >= palier:
                    etoiles = i + 1
            c.write({"valeur": valeur, "xp": valeur * poids,
                     "etoiles": etoiles, "mesure_le": maintenant})
            if gain > 0 and c.code != "pete_exploits":
                Exploit.create({
                    "membre_id": c.membre_id.id,
                    "name": "%s : +%s" % (libelle, gain),
                    "resume": "%s nouvelle(s) entrée(s) dans « %s » (%s)." % (
                        gain, libelle, c.code or "compteur"),
                    "gain": gain * poids,
                    "date": maintenant,
                    # Le code du compteur : c'est lui qui permet « Voir le
                    # détail » — ouvrir les enregistrements comptés au lieu
                    # d'une ligne sèche (Patrick, 29/07 : « je ne peux rien
                    # voir des détails »).
                    "code": c.code,
                })


class EquipeExploit(models.Model):
    """Le registre. C'est lui qui rend l'expérience honnête : chaque point a une
    date et une raison. Un total sans registre n'est qu'une affirmation."""

    _name = "equipe.exploit"
    _description = "Fait d'armes d'un membre"
    _order = "date desc, id desc"

    membre_id = fields.Many2one("equipe.membre", "Membre", required=True,
                                ondelete="cascade", index=True)
    name = fields.Char("Ce qui a été fait", required=True)
    gain = fields.Integer("Expérience gagnée")
    date = fields.Datetime("Quand", default=fields.Datetime.now)
    code = fields.Char("Compteur", index=True,
                       help="Le compteur qui a produit cette ligne — c'est "
                            "lui qui sait où sont les enregistrements comptés.")
    resume = fields.Text(
        "Résumé de ce qui a été fait",
        help="Une phrase lisible de ce que cette ligne enregistre "
             "réellement — lisible sans ouvrir le détail.")

    def action_voir_detail(self):
        """Ouvrir les enregistrements derrière la ligne du registre.

        Un exploit est un delta de compteur (« Relectures : +3 ») : le
        détail, ce sont les enregistrements du modèle compté, filtrés par
        le domaine du compteur. Les lignes d'avant ce champ n'ont pas de
        code — on le dit, on ne plante pas.
        """
        self.ensure_one()
        from odoo.exceptions import UserError
        desc = COMPTEURS.get(self.code or "")
        if not desc:
            raise UserError(_(
                "Cette ligne date d'avant le détail (ou son compteur a "
                "disparu) : rien à ouvrir. Les nouvelles lignes du registre "
                "sauront le faire."))
        libelle, modele, domaine, _poids = desc
        if modele not in self.env:
            raise UserError(_(
                "Le modèle « %s » n'est pas installé sur cette base.") % modele)
        return {
            "type": "ir.actions.act_window",
            "name": libelle,
            "res_model": modele,
            "view_mode": "list,form",
            "domain": domaine,
            "target": "current",
        }


class EquipeLivraison(models.Model):
    """Le carnet des livraisons de design & d'architecture.

    C'est le pendant exact du registre des exploits, mais côté œuvre : le
    registre compte des POINTS, ce carnet compte des LIVRABLES. Une ligne =
    un site mis en ligne, une maquette livrée, un plan d'architecture posé —
    toujours daté, toujours vérifiable (une adresse, un lien, une description).

    Pourquoi ce modèle existe et pas seulement un compteur : la règle de la
    tour est qu'on ne compte QUE ce qui a une existence propre en base. Un
    compteur sans carnet fabriquerait la mesure ; le carnet, lui, est d'abord
    utile à Patrick — son portfolio, ce qu'il a réellement construit — et
    l'expérience s'y lit en bonus.
    """

    _name = "equipe.livraison"
    _description = "Livraison de design & d'architecture"
    _order = "date desc, id desc"

    name = fields.Char("Ce qui a été livré", required=True)
    membre_id = fields.Many2one(
        "equipe.membre", "Par qui", required=True, index=True,
        default=lambda self: self.env["equipe.membre"].sudo().search(
            [("name", "=", "Patrick")], limit=1) or False)
    type = fields.Selection(
        [("site", "Un site mis en ligne"),
         ("design", "Une maquette / un design system"),
         ("architecture", "Une architecture / un plan système"),
         ("autre", "Autre livrable")],
        string="Nature", required=True, default="site")
    url = fields.Char("Où on le voit",
                      help="Adresse publique, dépôt, ou chemin. Une livraison "
                           "sans endroit où la voir n'est pas une livraison.")
    date = fields.Date("Livré le", default=fields.Date.context_today)
    description = fields.Text("Ce que c'est")

    # Verdict de conformité de Lex (05/08). Une livraison marquée conforme a
    # été VÉRIFIÉE par le contrôle qualité : cahier de tests joué, circuit
    # passé, preuve datée. C'est le geste mesuré par le compteur
    # `lex_verifications`. Le champ est posé par Lex lui-même, jamais à la main.
    lex_verifie = fields.Many2one(
        "equipe.membre", "Vérifié par Lex", readonly=False, ondelete="set null")
    conformite_validee = fields.Boolean(
        "Conforme", default=False,
        help="Posé par Lex quand la livraison a passé les contrôles de conformité "
             "(cahier de tests + circuit + preuve datée).")


class EquipeConsignePerso(models.Model):
    """Les consignes d'UN utilisateur pour UN agent.

    Patrick, le 28/07 : « donner la possibilité à l'utilisateur de donner ses
    spécifications et de dire à l'agent concerné de les suivre — tant que ça
    reste dans le périmètre et ne déclenche aucun garde-fou ».

    La hiérarchie est stricte et c'est elle qui rend la chose sûre :
    le socle et les refus de l'agent d'abord (ils tiennent même si la
    consigne demande le contraire — c'est déjà écrit dans le socle), les
    consignes de la maison ensuite, celles de l'utilisateur en dernier.
    Personnaliser la voix, jamais desserrer les verrous.
    """
    _name = "equipe.consigne.perso"
    _description = "Mes consignes pour cet agent"

    membre_id = fields.Many2one("equipe.membre", required=True,
                                ondelete="cascade", index=True)
    user_id = fields.Many2one("res.users", required=True, index=True,
                              default=lambda self: self.env.user)
    texte = fields.Text(
        "Ce que je lui demande de garder en tête", required=True,
        help="Envoyé à cet agent chaque fois que VOUS lui confiez quelque "
             "chose. Ses refus et ses garde-fous passent toujours avant.")

    _sql_constraints = [
        ("un_par_agent", "unique(membre_id, user_id)",
         "Vous avez déjà des consignes pour cet agent : modifiez-les plutôt "
         "que d'en créer d'autres — deux textes finiraient par se contredire."),
    ]


class EquipeMembreConsigne(models.Model):
    _inherit = "equipe.membre"

    consigne_perso_ids = fields.One2many(
        "equipe.consigne.perso", "membre_id", "Consignes personnelles")

    def consigne_de(self, user):
        """Le texte de CET utilisateur pour CET agent — vide sinon."""
        self.ensure_one()
        if not user:
            return ""
        p = self.env["equipe.consigne.perso"].sudo().search(
            [("membre_id", "=", self.id), ("user_id", "=", user.id)], limit=1)
        return (p.texte or "").strip()
