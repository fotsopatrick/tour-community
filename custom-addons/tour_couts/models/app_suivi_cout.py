# -*- coding: utf-8 -*-
"""Le coût mensuel remonte sur la fiche du projet.

Un tableau de coûts qu'il faut aller ouvrir n'est pas lu. Le chiffre doit
apparaître là où on regarde déjà le projet.

Le partage des dépenses communes est la seule vraie difficulté. Le serveur sert
tous les projets : lui affecter 9 € sur chacun fabriquerait 72 € qui n'existent
pas. On divise donc par le nombre de projets actifs — c'est grossier, et c'est
assumé : une répartition à l'usage réel (processeur, disque, requêtes) demande
une mesure par projet que la tour ne sait pas faire aujourd'hui. Mieux vaut une
clé simple qu'on comprend qu'une clé savante à laquelle personne ne croit.

**L'arrondi, trouvé par le retest du premier passage.** Avec deux décimales,
14,05 € partagés entre huit projets redonnaient 14,08 € : la somme des arrondis
n'est pas l'arrondi de la somme. Trois centimes, donc rien — sauf que c'est le
mécanisme exact du défaut qu'on voulait éviter, en plus petit. On garde quatre
décimales dans le calcul et on arrondit à l'affichage : le total réparti colle
alors au total dépensé, au dixième de centime près.
"""
from odoo import api, fields, models


class AppSuivi(models.Model):
    _inherit = "app.suivi"

    cout_direct = fields.Float(
        "Coût propre (€/mois)", compute="_compute_couts", digits=(12, 4),
        help="Ce que ce projet coûte à lui seul.")
    cout_partage = fields.Float(
        "Part des frais communs (€/mois)", compute="_compute_couts",
        digits=(12, 4),
        help="Sa part du serveur, des domaines et de tout ce qui sert à tous.")
    cout_mensuel = fields.Float(
        "Coût total (€/mois)", compute="_compute_couts", digits=(12, 4))
    cout_poste_ids = fields.Many2many(
        "cout.poste", string="Postes de coût", compute="_compute_couts")

    @api.depends("statut")
    def _compute_couts(self):
        Poste = self.env["cout.poste"].sudo()
        communs = Poste.search([("commun", "=", True)])
        total_commun = sum(communs.mapped("montant_mensuel"))
        # Le diviseur : les projets actifs. Jamais zéro — une division par zéro
        # ici afficherait une erreur sur le tableau de bord entier.
        actifs = max(1, self.env["app.suivi"].sudo().search_count([]))
        for app in self:
            propres = Poste.search([("app_ids", "in", app.id)])
            app.cout_direct = sum(propres.mapped("montant_mensuel"))
            app.cout_partage = total_commun / actifs
            app.cout_mensuel = app.cout_direct + app.cout_partage
            app.cout_poste_ids = propres | communs
