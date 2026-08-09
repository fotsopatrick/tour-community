# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ApprentissageSource(models.Model):
    _name = "apprentissage.source"
    _description = "Source d'apprentissage (livre, dépôt, article)"
    _order = "name"

    name = fields.Char("Titre", required=True)
    auteur = fields.Char("Auteur")
    annee = fields.Char("Année")
    lien = fields.Char("Lien")
    type_source = fields.Selection(
        [
            ("livre", "Livre"),
            ("depot", "Dépôt public"),
            ("article", "Article"),
            ("autre", "Autre"),
        ],
        string="Type",
        default="livre",
        required=True,
    )
    etat_lecture = fields.Selection(
        [
            ("a_lire", "À lire"),
            ("en_cours", "Lecture en cours"),
            ("lue", "Lue en entier"),
            ("bloquee", "Bloquée (accès manquant)"),
        ],
        string="État de lecture",
        default="a_lire",
        required=True,
    )
    progression = fields.Char(
        "Où en est la lecture",
        help="Ex. : « chapitre 1 lu en entier, chapitre 2 verrouillé »",
    )
    lecon_ids = fields.One2many("apprentissage.lecon", "source_id", string="Leçons")
    nb_lecons = fields.Integer("Leçons tirées", compute="_compute_nb_lecons")

    @api.depends("lecon_ids")
    def _compute_nb_lecons(self):
        for rec in self:
            rec.nb_lecons = len(rec.lecon_ids)


class ApprentissageLecon(models.Model):
    _name = "apprentissage.lecon"
    _description = "Leçon apprise (une trouvaille rapportée à la tour)"
    _order = "create_date desc"

    name = fields.Char("La leçon en une ligne", required=True)
    source_id = fields.Many2one(
        "apprentissage.source", string="Source", required=True, ondelete="restrict"
    )
    chapitre = fields.Char("Chapitre / section", help="Ex. : « ch. 1, §1.3 »")
    constat = fields.Text(
        "Le constat, reformulé",
        required=True,
        help="Reformulé avec nos mots — pas de copier-coller long (droit d'auteur).",
    )
    impact_tour = fields.Text(
        "Ce que ça change pour la tour",
        required=True,
        help="Une leçon sans impact tour est du bruit : elle est refusée.",
    )
    action = fields.Text("Action proposée")
    etat = fields.Selection(
        [
            ("nouvelle", "Nouvelle"),
            ("a_creuser", "À creuser"),
            ("tache", "Transformée en tâche"),
            ("appliquee", "Appliquée"),
            ("rejetee", "Rejetée"),
        ],
        string="État",
        default="nouvelle",
        required=True,
    )
    lien_suite = fields.Char(
        "Suite donnée",
        help="Référence de la tâche, décision ou étude née de cette leçon.",
    )
