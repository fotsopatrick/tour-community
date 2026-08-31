# -*- coding: utf-8 -*-
"""Choix granulaire du périmètre du Clone (31/07).

Patrick veut choisir case par case ce que le clone peut faire, au lieu de
deux blocs globaux. Chaque capacité devient une case à cocher sur la fiche
Décisions ; à l'approbation, les cases sont recopiées sur le membre Clone
(qui les lit pour savoir quoi faire).

Les INTERDITS ne sont pas des cases à décocher par erreur : ils sont VRAIS
par défaut (le clone ne peut pas envoyer/publier/modifier/décider) et ne
deviennent permis que si Patrick le coche expressément. Prudence par défaut.
"""
from odoo import fields, models


class DecisionFicheClone(models.Model):
    _inherit = "decision.fiche"

    # --- Ce que le clone PEUT faire (cases à cocher) ---
    clone_peut_apprendre = fields.Boolean(
        "Apprendre ton style chaque jour",
        default=True,
        help="Le cron quotidien relit tes décisions et versionne sa fiche persona.")
    clone_peut_veiller = fields.Boolean(
        "Proposer « si j'étais Patrick » chaque jour",
        default=True,
        help="Le cron quotidien rend une fiche Réponses sur les décisions récentes.")
    clone_peut_proposer = fields.Boolean(
        "Rédiger des propositions (textes, reformulations)",
        default=True,
        help="Il écrit « comme toi » — toujours pour validation.")
    clone_peut_envoyer = fields.Boolean(
        "Envoyer des messages",
        default=False,
        help="⚠️ Décocher par défaut : le clone ne doit PAS envoyer. "
             "À ne cocher que si tu veux lui donner ce droit.")
    clone_peut_publier = fields.Boolean(
        "Publier des contenus",
        default=False,
        help="⚠️ Décocher par défaut : le clone ne doit PAS publier.")
    clone_peut_modifier = fields.Boolean(
        "Modifier les fichiers de la tour",
        default=False,
        help="⚠️ Décocher par défaut : le clone ne touche pas à la tour.")
    clone_peut_decider = fields.Boolean(
        "Décider seul (sans validation)",
        default=False,
        help="⚠️ Décocher par défaut : toute proposition du clone attend "
             "ton feu vert.")

    # Les pré-décisions du clone découpées une par une (31/07) : Patrick
    # tranche chaque ligne (d'accord / pas d'accord + pourquoi), et c'est
    # cette matière qui rapproche le clone de sa façon de penser.
    clone_feedback_ids = fields.One2many(
        "clone.feedback", "decision_id", "Tes corrections du clone")

    # ------------------------------------------------------------------
    def action_approuver(self):
        # La fiche de validation du clone : on recopie les cases sur le membre
        # AVANT d'appeler l'approbation d'origine (qui agit sur l'origine).
        for d in self:
            if d.name and "CLONE" in d.name.upper():
                clone = self.env["equipe.membre"].sudo().search(
                    [("name", "=", "Clone de Patrick")], limit=1)
                if clone:
                    clone.action_appliquer_permissions(
                        clone_peut_apprendre=d.clone_peut_apprendre,
                        clone_peut_veiller=d.clone_peut_veiller,
                        clone_peut_proposer=d.clone_peut_proposer,
                        clone_peut_envoyer=d.clone_peut_envoyer,
                        clone_peut_publier=d.clone_peut_publier,
                        clone_peut_modifier=d.clone_peut_modifier,
                        clone_peut_decider=d.clone_peut_decider,
                    )
        return super().action_approuver()
