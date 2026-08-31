from datetime import datetime, time
from odoo import api, fields, models

class TourMission(models.Model):
    """Modèle simplifié de mission pour la tour de contrôle.
    Permet de tester le système de niveaux : terminer une mission donne +100 XP.
    """
    _name = 'tour.mission'
    _description = 'Mission de la Tour'
    _order = 'date_creation desc'

    name = fields.Char(string="Titre de la mission", required=True)
    description = fields.Text(string="Description")
    assigned_to = fields.Many2one(
        'res.users',
        string="Assigné à",
        required=True,
        default=lambda self: self.env.user
    )
    state = fields.Selection([
        ('brouillon', 'Brouillon'),
        ('en_cours', 'En cours'),
        ('terminee', 'Terminée'),
        ('annulee', 'Annulée'),
    ], string="Statut", default='brouillon', required=True)
    date_creation = fields.Datetime(
        string="Date de création",
        default=fields.Datetime.now
    )
    date_limite = fields.Date(string="Date limite")
    date_terminee = fields.Datetime(string="Date de terminaison")
    xp_gagne = fields.Integer(
        string="XP gagné",
        default=0,
        help="XP attribué lors de la terminaison de cette mission."
    )

    def action_demarrer(self):
        """Passe la mission en cours."""
        for mission in self:
            if mission.state == 'brouillon':
                mission.state = 'en_cours'

    def action_terminer(self):
        """Termine la mission et attribue l'XP à l'utilisateur assigné."""
        for mission in self:
            if mission.state == 'terminee':
                continue

            now_dt = fields.Datetime.now()

            mission.write({
                'state': 'terminee',
                'date_terminee': now_dt,
                'xp_gagne': 100,  # XP de base pour une mission
            })

            # Bonus si rendue avant la date limite
            xp_bonus = 0
            if mission.date_limite and mission.date_terminee:
                # Convertir date_limite (Date) en datetime pour comparaison
                limite_dt = datetime.combine(
                    mission.date_limite,
                    time(23, 59, 59)
                )
                # Comparer les datetime native
                if isinstance(mission.date_terminee, datetime):
                    terminee_dt = mission.date_terminee
                else:
                    terminee_dt = fields.Datetime.from_string(mission.date_terminee)

                if terminee_dt <= limite_dt:
                    xp_bonus = 50
                    mission.xp_gagne += xp_bonus

            # Attribution de l'XP à l'utilisateur
            if mission.assigned_to:
                raison = f"Mission terminée : {mission.name}"
                if xp_bonus:
                    raison += f" (dont {xp_bonus} XP bonus avance)"
                mission.assigned_to.ajouter_xp(mission.xp_gagne, raison)

            # Incrémentation du compteur de missions terminées
            if mission.assigned_to:
                mission.assigned_to.missions_terminees += 1

    def action_annuler(self):
        """Annule la mission."""
        for mission in self:
            mission.state = 'annulee'
