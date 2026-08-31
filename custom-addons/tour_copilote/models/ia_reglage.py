# -*- coding: utf-8 -*-
"""Chaque compte peut brancher SON moteur et SA cle d'API.

Jusqu'ici, le chat ne savait choisir qu'un seul fournisseur, regle par le
parametre global `tour_copilote.fournisseur` — et une seule cle, partagee par
toute la base. Sur la demo, seize invites utilisaient les credits de Patrick.

Cette page donne a chaque utilisateur ses propres reglages : le moteur
(deepseek ou opencode) et la cle d'API correspondante. Le chat lit ces champs
en premier, et ne retombe sur la configuration globale que si la personne n'a
rien regle.

LA CLE NE SORT JAMAIS. Le navigateur ne recoit ni la valeur, ni une forme
reversible : seule la page connait son existence et ses 4 derniers caracteres
(assez pour la reconnaitre, pas assez pour l'utiliser). Elle s'ecrit, elle se
remplace, elle s'efface — elle ne se lit jamais.
"""

from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    ia_moteur = fields.Selection(
        [("", "Suivre la configuration de la tour"),
         ("deepseek", "DeepSeek (ma clé)"),
         ("opencode", "opencode (ma clé)")],
        string="Mon moteur IA",
        help="Le moteur utilise par le chat quand c'est toi qui lui parles. "
             "Vide = les réglages de la tour (celui que Patrick a choisi "
             "pour l'ensemble de la base).")

    ia_cle = fields.Char(
        string="Ma clé API",
        help="Stockée côté serveur, jamais renvoyée au navigateur. Vide = la "
             "clé de la tour fait foi.")

    ia_cle_definie = fields.Char(
        "Clé (masquée)", compute="_compute_ia_cle_definie")

    def _compute_ia_cle_definie(self):
        for user in self:
            cle = user.ia_cle or ""
            if len(cle) >= 4:
                user.ia_cle_definie = "définie (…%s)" % cle[-4:]
            elif cle:
                user.ia_cle_definie = "définie (trop courte)"
            else:
                user.ia_cle_definie = ""
