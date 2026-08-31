# -*- coding: utf-8 -*-
"""La boîte à outils de la tour.

Un outil = une fiche : ce qu'il fait, le fichier à télécharger, et le mode
d'emploi pour l'installer et s'en servir. La liste existe pour une raison
simple : un script qui dort dans un dépôt Git n'existe pas pour quelqu'un
qui n'ouvre pas le dépôt. Ici, on ouvre la tour, on clique, on a l'outil.

Le fichier porté par la fiche est une COPIE embarquée dans le module
(static/outils/). La source de vérité reste le dépôt (outils/poste/…) :
après toute modification d'un script, recopier dans static/outils/ puis
mettre à jour le module — même règle que les moteurs de l'atelier.
"""
from odoo import fields, models

CATEGORIES = [
    ("poste", "Script de poste (PC)"),
    ("serveur", "Script serveur"),
    ("mobile", "Application mobile"),
    ("autre", "Autre"),
]


class TourOutil(models.Model):
    _name = "tour.outil"
    _description = "Outil de la tour"
    _order = "categorie, sequence, name"

    name = fields.Char("Nom", required=True)
    resume = fields.Char("En une phrase",
                         help="Ce que fait l'outil, lisible dans la liste.")
    categorie = fields.Selection(CATEGORIES, string="Catégorie",
                                 required=True, default="poste", index=True)
    plateforme = fields.Char("Tourne sur", help="Ex. : Windows 10/11, Android…")
    commande = fields.Char(
        "Commande de lancement",
        help="La ligne à taper pour lancer l'outil, prête à copier.")
    emplacement_repo = fields.Char(
        "Source dans le dépôt",
        help="Où vit le fichier d'origine (la copie téléchargeable peut "
             "retarder d'une mise à jour de module).")
    description = fields.Html("Mode d'emploi", sanitize=False)
    fichier = fields.Binary("Fichier à télécharger", attachment=True)
    fichier_nom = fields.Char("Nom du fichier")
    sequence = fields.Integer("Ordre", default=10)
    interne = fields.Boolean(
        "Réservé à l'admin", default=False,
        help="Coché : invisible pour les utilisateurs non administrateurs.")
