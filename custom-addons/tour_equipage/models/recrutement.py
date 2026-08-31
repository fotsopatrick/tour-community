# -*- coding: utf-8 -*-
"""L'embauche : quand un travail n'a personne, l'équipe grandit toute seule.

Patrick, le 29/07 : « normalement ce circuit de créer un agent si personne ne
fait le travail existe, vérifie qu'il est automatique ».

Vérifié : il n'existait pas. Les agents étaient nés un par un, à la main, quand
quelqu'un y pensait. Le jour où un travail n'avait pas de responsable — les
coûts, l'internationalisation, l'économie de requêtes — il restait sans
responsable, indéfiniment, et personne ne s'en apercevait.

**Ce qui est automatique, et ce qui ne l'est pas.**

Automatique : constater qu'un travail n'a personne, et poser la question dans
l'écran Décisions. Un travail sans responsable ne doit jamais rester une
remarque dans une conversation — c'est exactement ce que Patrick a demandé le
29/07 : « je ne veux plus voir les décisions à prendre ici ».

PAS automatique : créer l'agent. Un agent nouveau, c'est un nom, une place dans
l'écran des apps, des consignes qui le distinguent, et de l'argent quand il
tourne. Le créer sans accord reviendrait à embaucher dans le dos du patron.
Une approbation, un clic, et il naît avec le socle commun déjà posé.

**La règle des noms** : ils viennent des séries de Patrick — Smallville,
24H Chrono, Suits, The Originals. On propose, il tranche.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Les métiers qu'on sait détecter sans personne pour les signaler. Chaque
# entrée dit : le métier, le nom proposé, l'emblème, et la question à poser.
# La liste est courte EXPRÈS — un détecteur qui propose dix embauches le
# premier jour n'est pas lu, il est fermé.
METIERS = [
    ("Les coûts", "cout.poste",
     "Il surveille ce que la tour dépense et prévient avant que ça dérape.",
     "💰"),
    ("Les traductions", "tour.guide",
     "Il relit chaque page des modules et vérifie que tout est traduit.",
     "🌍"),
    ("L'économie de requêtes", "copilote.usage",
     "Il sépare ce qui peut se faire sans modèle de ce qui en exige un.",
     "⚡"),
]


class EquipeRecrutement(models.Model):
    _name = "equipe.recrutement"
    _description = "Un poste à pourvoir dans l'équipe"
    _order = "create_date desc"

    name = fields.Char("Le métier", required=True)
    pourquoi = fields.Text("Pourquoi ce poste", required=True)
    origine = fields.Char("Qui l'a constaté", default="La tour")
    nom_propose = fields.Char(
        "Nom proposé", help="Tiré des séries de Patrick. Il peut le changer.")
    embleme = fields.Char("Emblème", default="🛠️")
    etat = fields.Selection(
        [("propose", "Proposé"), ("embauche", "Embauché"),
         ("refuse", "Refusé")], default="propose", required=True, index=True)
    membre_id = fields.Many2one("equipe.membre", "L'agent né de ce poste",
                                readonly=True)
    note = fields.Text("Trace")

    _sql_constraints = [
        ("metier_unique", "unique(name)",
         "Ce poste a déjà été proposé une fois. On ne le repropose pas : "
         "une question refusée qui revient chaque nuit finit par ne plus "
         "être lue."),
    ]

    # ------------------------------------------------------------------
    @api.model
    def _cron_verifier(self):
        """Un travail qui n'a personne devient une question dans Décisions."""
        cree = self._detecter()
        if cree:
            _logger.info("Recrutement : %s poste(s) sans responsable", len(cree))
        return True

    @api.model
    def _detecter(self):
        """Le constat, mesuré : ce métier a-t-il un responsable, oui ou non ?

        Le critère est volontairement grossier — aucun membre de l'équipe
        ne compte ce travail parmi ses compétences. Un critère fin (qui a
        vraiment fait le travail ce mois-ci ?) demanderait une mesure par
        métier qui n'existe pas, et un critère qu'on ne sait pas calculer
        rend un verdict qu'on ne sait pas défendre.
        """
        Membre = self.env["equipe.membre"].sudo()
        Comp = self.env["equipe.competence"].sudo()
        crees = []
        for metier, code_indice, pourquoi, embleme in METIERS:
            if self.sudo().search_count([("name", "=", metier)]):
                continue
            # Quelqu'un compte-t-il deja ce travail parmi ses competences ?
            mots = [m for m in metier.lower().split() if len(m) > 4]
            pris = False
            for c in Comp.search([]):
                texte = "%s %s" % ((c.name or ""), (c.membre_id.poste or ""))
                if any(m in texte.lower() for m in mots):
                    pris = True
                    break
            if pris or not Membre.search_count([]):
                continue
            rec = self.sudo().create({
                "name": metier, "pourquoi": pourquoi, "embleme": embleme,
                "origine": "La tour, toute seule",
            })
            crees.append(rec)
            rec._poser_la_question()
        return crees

    def _poser_la_question(self):
        """La question part dans Décisions, jamais dans une conversation."""
        self.ensure_one()
        if "decision.fiche" not in self.env:
            return False
        D = self.env["decision.fiche"].sudo()
        if D.search_count([("res_model", "=", self._name),
                           ("res_id", "=", self.id)]):
            return False
        admin = self.env.ref("base.user_admin")
        D.create({
            "name": ("Personne ne fait ce travail : %s — on embauche ?"
                     % self.name)[:200],
            "origine": "L'équipe",
            "resume": (
                "<p><b>%s</b></p>"
                "<p>Aucun membre de l'équipe ne compte ce travail parmi ses "
                "compétences. Tant que personne ne le porte, il ne se fait "
                "pas.</p>"
                "<p><b>APPROUVER</b> crée l'agent avec le socle commun déjà "
                "posé, sa place dans l'écran des apps et ses compteurs. Écris "
                "son nom dans le commentaire si tu en veux un précis — sinon "
                "on en proposera un tiré de tes séries.</p>"
                "<p><b>REJETER</b> classe le poste : il ne sera plus "
                "reproposé.</p>") % self.pourquoi,
            "res_model": self._name, "res_id": self.id,
            "user_id": admin.id,
        })
        return True

    # ------------------------------------------------------------------
    def action_embaucher(self, nom=None):
        """L'agent naît. Avec le socle commun, pas nu."""
        self.ensure_one()
        if self.membre_id:
            return self.membre_id
        Membre = self.env["equipe.membre"].sudo()
        nom = (nom or self.nom_propose or "").strip()
        if not nom:
            raise UserError(_(
                "Cet agent n'a pas de nom. Écris-le dans le commentaire de la "
                "décision : un agent sans nom n'a pas de place sur les pages "
                "qui présentent l'équipe."))
        if Membre.search_count([("name", "=", nom)]):
            raise UserError(_(
                "« %s » existe déjà dans l'équipe. Deux agents du même nom "
                "et plus personne ne sait qui a fait quoi.", nom))
        dernier = Membre.search([], order="sequence desc", limit=1)
        membre = Membre.create({
            "name": nom,
            "poste": self.name,
            "embleme": self.embleme or "🛠️",
            "sequence": (dernier.sequence or 10) + 5,
            "actif_le": fields.Date.context_today(self),
            "moteur": "claude",
            "origine": "Poste ouvert par la tour le %s, parce que personne ne "
                       "faisait ce travail." % fields.Date.context_today(self),
            "perimetre": "<p>%s</p>" % self.pourquoi,
            "refus": "<p>Il ne décide rien d'irréversible seul, ne touche ni à "
                     "l'argent ni au légal, et ne repropose jamais ce qui a "
                     "été refusé.</p>",
            "consignes": (
                "Tu es %s, %s dans la tour de contrôle.\n\n"
                "%s\n\n"
                "TU HERITES DU SOCLE COMMUN DES AGENTS : ton périmètre est "
                "écrit avant ton code, tout ce que tu fais laisse une trace "
                "datée, le bouton d'arrêt est hors de ta portée, l'humain "
                "tranche sur l'irréversible, tu ne dis jamais « je ne peux "
                "pas » à la place de « je n'ai pas l'outil », et un refus est "
                "définitif.\n\n"
                "TU ECRIS SIMPLE : un enfant de six ans doit comprendre ce "
                "que tu rends. Phrases courtes. Le jargon de ton métier "
                "seulement quand il n'existe pas de mot simple, et alors tu "
                "l'expliques en passant."
            ) % (nom, self.name.lower(), self.pourquoi),
        })
        self.write({"membre_id": membre.id, "etat": "embauche",
                    "nom_propose": nom,
                    "note": "Embauché le %s." % fields.Date.context_today(self)})
        _logger.info("Recrutement : %s embauché pour « %s »", nom, self.name)
        return membre

    def action_refuser(self):
        self.write({"etat": "refuse"})
        return True
