# -*- coding: utf-8 -*-
"""Le CV : une page web qui se met à jour toute seule.

Un CV est un fichier qui vieillit. On l'écrit une fois, on l'envoie, et six
mois plus tard il ne dit plus ce qu'on sait faire — mais on l'envoie quand
même, parce que le rouvrir coûte une soirée.

Ici il vit dans la tour, à côté du reste. On ajoute une réalisation le jour
où elle est finie, et la page publique est à jour dans la seconde. C'est la
seule différence qui compte, et elle change tout : **le CV cesse d'être un
travail pour devenir un affichage.**

Deux décisions de conception :

**Une page, pas un PDF.** Le web permet de replier le détail : le lecteur
choisit d'en lire plus. Un PDF impose une longueur, donc il oblige à couper
ce qui explique le raisonnement — et c'est précisément ce qui distingue
quelqu'un qui a construit de quelqu'un qui a suivi un tutoriel.

**Publié par lien, jamais indexé.** Un CV en ligne trouvable par recherche
reste consultable des années après, y compris par un employeur qu'on n'a pas
choisi. On donne le lien à qui on veut.
"""
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class CvProfil(models.Model):
    _name = "cv.profil"
    _description = "Profil de CV"
    _inherit = ["mail.thread"]

    name = fields.Char("Nom affiché", required=True, tracking=True)
    slug = fields.Char(
        "Adresse", required=True, copy=False,
        help="La page sera servie sur /cv/<adresse>. Lettres minuscules, "
             "chiffres et tirets.")
    metier = fields.Char("Métier, en une ligne")
    accroche = fields.Html(
        "L'accroche", sanitize=False,
        help="Deux ou trois phrases. C'est ce qu'on lit avant de décider de "
             "lire la suite.")
    phrase_forte = fields.Char(
        "La phrase à retenir",
        help="Une seule. Elle s'affiche sous le titre, en gras.")

    ville = fields.Char("Ville")
    telephone = fields.Char("Téléphone")
    email = fields.Char("Courriel")
    linkedin = fields.Char("LinkedIn")

    publie = fields.Boolean(
        "Publié", default=False, tracking=True,
        help="Tant que ce n'est pas coché, la page rend 404 — même avec la "
             "bonne adresse.")
    indexable = fields.Boolean(
        "Autoriser les moteurs de recherche", default=False,
        help="Décoché par défaut. Un CV trouvable par recherche reste "
             "consultable des années, y compris par un employeur qu'on n'a "
             "pas choisi.")

    experience_ids = fields.One2many("cv.experience", "profil_id", "Expériences")
    realisation_ids = fields.One2many("cv.realisation", "profil_id", "Réalisations")
    competence_ids = fields.One2many("cv.competence", "profil_id", "Compétences")
    formation_ids = fields.One2many("cv.formation", "profil_id", "Formations")
    langues = fields.Char("Langues")

    url = fields.Char("Adresse publique", compute="_compute_url")

    _sql_constraints = [("slug_unique", "unique(slug)", "Cette adresse est déjà prise.")]

    @api.depends("slug")
    def _compute_url(self):
        base = (self.env["ir.config_parameter"].sudo()
                .get_param("web.base.url") or "").rstrip("/")
        for rec in self:
            rec.url = "%s/cv/%s" % (base, rec.slug or "")

    @api.constrains("slug")
    def _verifier_slug(self):
        for rec in self:
            if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,48}", rec.slug or ""):
                raise UserError(_(
                    "L'adresse doit être en minuscules, sans espace ni "
                    "accent : « %s » ne convient pas.") % rec.slug)

    def action_voir(self):
        self.ensure_one()
        return {"type": "ir.actions.act_url", "url": "/cv/%s" % self.slug,
                "target": "new"}


class CvExperience(models.Model):
    _name = "cv.experience"
    _description = "Expérience professionnelle"
    _order = "sequence, id desc"

    profil_id = fields.Many2one("cv.profil", required=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    name = fields.Char("Poste", required=True)
    organisation = fields.Char("Organisation")
    precision = fields.Char("Ce que fait l'organisation")
    periode = fields.Char("Période", help="Ex. « Juin 2020 → aujourd'hui »")
    points = fields.Html(
        "Ce que j'y ai fait", sanitize=False,
        help="Une liste. Chaque point dit un RÉSULTAT, pas une mission.")
    detail_titre = fields.Char(
        "Titre du bloc replié", help="Vide = pas de bloc replié.")
    detail = fields.Html("Le détail replié", sanitize=False)


class CvRealisation(models.Model):
    _name = "cv.realisation"
    _description = "Réalisation majeure"
    _order = "sequence, id"

    profil_id = fields.Many2one("cv.profil", required=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    name = fields.Char("Titre", required=True)
    periode = fields.Char("Période")
    contexte = fields.Char("Une ligne de contexte")
    chiffres = fields.Char(
        "Chiffres", help="Format : 20+|modules ; 17|utilisateurs — séparés "
                         "par des points-virgules. Quatre au maximum : au-delà "
                         "on ne les lit plus.")
    outils = fields.Char("Outils", help="Séparés par des virgules.")
    points = fields.Html("Ce qui a été fait", sanitize=False)
    bloc_ids = fields.One2many("cv.bloc", "realisation_id", "Blocs repliés")

    def _chiffres_lus(self):
        self.ensure_one()
        sortie = []
        for morceau in (self.chiffres or "").split(";"):
            if "|" in morceau:
                valeur, libelle = morceau.split("|", 1)
                sortie.append((valeur.strip(), libelle.strip()))
        return sortie[:4]

    def _outils_lus(self):
        self.ensure_one()
        return [o.strip() for o in (self.outils or "").split(",") if o.strip()]


class CvBloc(models.Model):
    _name = "cv.bloc"
    _description = "Bloc de détail replié"
    _order = "sequence, id"

    realisation_id = fields.Many2one("cv.realisation", required=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    name = fields.Char("Titre du bloc", required=True)
    contenu = fields.Html("Contenu", sanitize=False)


class CvCompetence(models.Model):
    _name = "cv.competence"
    _description = "Groupe de compétences"
    _order = "sequence, id"

    profil_id = fields.Many2one("cv.profil", required=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    name = fields.Char("Domaine", required=True)
    contenu = fields.Text("Détail", required=True)


class CvFormation(models.Model):
    _name = "cv.formation"
    _description = "Formation"
    _order = "sequence, id"

    profil_id = fields.Many2one("cv.profil", required=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    name = fields.Char("Intitulé", required=True)
    ecole = fields.Char("Établissement")
    periode = fields.Char("Période")
