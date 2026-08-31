# -*- coding: utf-8 -*-
"""Les versions d'un produit : À trier, V2, V3, abandonné.

Depuis le 28/07, la version n'est plus un objet à part : c'est une étiquette sur
la TÂCHE (voir project_task.py). On avait deux listes — 134 cartes, toutes
copies de tâches — et deux listes pour la même chose finissent par diverger.

Ce fichier ne garde donc que deux choses :
  1. la liste des versions possibles (VERSIONS), partagée par toute la feuille
     de route ;
  2. l'ancien modèle `roadmap.item`, vidé de sa logique, le temps de migrer ses
     données vers les tâches. Il n'a plus de menu et disparaîtra.
"""

from odoo import api, fields, models

VERSIONS = [
    ("a_trier", "À trier"),
    # La V1 manquait : on pouvait trier vers v2 ou v3, mais le socle lui-meme
    # n'etait pas representable — donc « la tour est a quelle version ? »
    # n'avait pas de reponse dans l'ecran qui est cense la donner.
    ("v1", "V1 — le socle"),
    ("v2", "V2 — la prochaine"),
    ("v3", "V3 — plus tard"),
    ("v4", "V4 — l'ère des agents"),
    ("jamais", "Abandonné"),
]


class RoadmapItem(models.Model):
    """Ancien modèle, conservé sans logique pour migrer ses données puis mourir.

    On ne le supprime pas d'un coup : ses champs portent encore le « pourquoi »,
    le « proposé par moi » et le « faisable sans Patrick » qu'il faut recopier
    sur les tâches. Une fois la copie faite et vérifiée, on efface les
    enregistrements.
    """

    _name = "roadmap.item"
    _description = "Fonctionnalité (ancien modèle, en migration)"
    _order = "sequence, id"

    name = fields.Char("Fonctionnalité", required=True)
    sequence = fields.Integer(default=10)
    resume = fields.Char("En une phrase")
    version = fields.Selection(
        VERSIONS + [("hors_sujet", "Hors tour")], "Version", default="a_trier")
    version_proposee = fields.Selection(
        VERSIONS + [("hors_sujet", "Hors tour")], "Ce que je proposais")
    propose_claude = fields.Boolean("Proposé par moi")
    sans_patrick = fields.Boolean("Faisable sans Patrick")
    pourquoi = fields.Text("Pourquoi cette version")
    avis = fields.Text("Mon avis")
    effort = fields.Selection(
        [("petit", "Petit"), ("moyen", "Moyen"), ("gros", "Gros")], "Effort")
    valeur = fields.Selection(
        [("debloque", "Débloque"), ("promesse", "Promesse"),
         ("confort", "Confort"), ("exploration", "Exploration")], "Apporte")
    tache_id = fields.Many2one("project.task", "Tâche liée", ondelete="set null")
