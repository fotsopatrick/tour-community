from odoo import api, fields, models

class ResUsers(models.Model):
    _inherit = 'res.users'

    xp_total = fields.Integer(
        string="Points d'expérience (XP)",
        default=0,
        help="XP cumulé de l'utilisateur, source de vérité pour le niveau."
    )
    niveau = fields.Integer(
        string="Niveau",
        default=1,
        compute='_compute_niveau',
        store=True,
        help="Niveau actuel, calculé automatiquement à partir de l'XP total."
    )
    xp_prochain_niveau = fields.Integer(
        string="XP pour le prochain niveau",
        compute='_compute_niveau',
        store=False,
        help="XP nécessaire pour atteindre le prochain niveau."
    )
    xp_dans_le_niveau = fields.Integer(
        string="XP dans le niveau actuel",
        compute='_compute_niveau',
        store=False,
        help="XP acquis depuis le début du niveau actuel."
    )
    progression_pct = fields.Float(
        string="Progression %",
        compute='_compute_niveau',
        store=False,
        help="Pourcentage de progression vers le prochain niveau."
    )
    missions_terminees = fields.Integer(
        string="Missions terminées",
        default=0,
        help="Nombre total de missions terminées par l'utilisateur."
    )
    derniere_connexion = fields.Date(
        string="Dernière connexion",
        help="Date de la dernière connexion enregistrée."
    )

    @staticmethod
    def _seuil_niveau(n):
        """
        XP nécessaire pour atteindre le niveau N.
        Niveau 1 = 0 XP
        Niveau 2 = 100 XP
        Niveau 3 = 300 XP
        ...
        Formule : seuil(N) = (N-1) * N * 50   (pour N >= 1, seuil(1) = 0)
        """
        if n <= 1:
            return 0
        return (n - 1) * n * 50

    @api.depends('xp_total')
    def _compute_niveau(self):
        """Calcule le niveau à partir de l'XP total."""
        for user in self:
            xp = user.xp_total or 0
            # Trouver le plus grand N où seuil(N) <= xp
            n = 1
            while self._seuil_niveau(n + 1) <= xp:
                n += 1
            niveau = n
            if niveau < 1:
                niveau = 1

            user.niveau = niveau

            # Calcul de la progression
            seuil_actuel = self._seuil_niveau(niveau)
            seuil_prochain = self._seuil_niveau(niveau + 1)
            xp_dans_niveau = xp - seuil_actuel
            besoin_prochain = seuil_prochain - seuil_actuel

            user.xp_prochain_niveau = besoin_prochain
            user.xp_dans_le_niveau = xp_dans_niveau
            if besoin_prochain > 0:
                user.progression_pct = (xp_dans_niveau / besoin_prochain) * 100.0
            else:
                user.progression_pct = 0.0

    def ajouter_xp(self, points, raison=""):
        """Ajoute des points d'XP à l'utilisateur et déclenche le recalcul du niveau.

        Args:
            points (int): Nombre de points d'XP à ajouter.
            raison (str): Raison de l'attribution (log).
        """
        self.ensure_one()
        self.xp_total += points
        # Le compute _compute_niveau se déclenche via le depends xp_total
        if raison:
            self.message_post(
                body=f"<b>+{points} XP</b> — {raison}",
                subject="XP gagné"
            )
        return True

    def action_recalculer_niveau(self):
        """Action manuelle pour recalculer tous les niveaux (admin)."""
        for user in self.search([]):
            user._compute_niveau()
        return True
