# -*- coding: utf-8 -*-
"""Le registre des garde-fous de la tour.

Un garde-fou est un contrôle qui continue de tenir quand personne ne le
regarde. Il a deux faces, et les deux comptent :
- la PROTECTION : ce qu'il refuse, borne, ou signale ;
- le CONTRÔLE : la manipulation qui prouve qu'il tient encore.

Le registre recense les deux. Une fiche sans « comment le vérifier » est une
intention, pas un garde-fou.
"""
from odoo import fields, models


class GardeFou(models.Model):
    _name = "garde_fou.garde_fou"
    _description = "Garde-fou de la tour"
    _order = "zone, name"

    name = fields.Char("Garde-fou", required=True)
    code = fields.Char(
        "Code", required=True,
        help="Identifiant court, sans espace, ex. atelier.quota-stockage.")
    zone = fields.Selection(
        [("hote", "Hôte (serveur)"),
         ("tour", "Tour (Odoo)"),
         ("agent", "Agent (mission)")],
        string="Zone", required=True)
    niveau = fields.Selection(
        [("deterministe", "Déterministe"),
         ("processus", "Processus"),
         ("modele", "Modèle (prompt)")],
        string="Comment ça s'applique", required=True,
        help="Déterministe : code qui rend le même verdict deux fois. "
             "Processus : une règle de circulation (cron, circuit, ordre). "
             "Modèle : une consigne donnée à l'IA — le plus fragile des trois.")
    module = fields.Char(
        "Où ça vit", help="Module, fichier : ligne, ou script de l'hôte.")
    crainte = fields.Text(
        "Ce que ça protège",
        help="La crainte qui a fait naître ce garde-fou. Sans elle, le "
             "garde-fou n'est qu'une contrainte.")
    fonctionnement = fields.Text(
        "Comment ça protège",
        help="Le mécanisme : ce qui est refusé, borné, ou signalé, et par quel "
             "moyen.")
    verification = fields.Text(
        "Comment le vérifier",
        help="La manipulation exacte qui prouve qu'il tient encore. Un "
             "garde-fou qu'on ne sait pas contrôler n'est pas un garde-fou.")
    etat = fields.Selection(
        [("en_place", "En place"),
         ("en_cours", "En cours"),
         ("a_verifier", "À vérifier")],
        string="État", default="en_place")
    actif = fields.Boolean("Actif", default=True)
