"""Migration d'initialisation du système de niveaux.

Pour chaque utilisateur existant :
- Si aucune mission n'existe, niveau 1, XP = 0
- Si des missions terminées existent (modèle tour.mission), on calcule
  l'XP rétroactivement : 100 XP par mission terminée
"""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """Initialise les champs xp_total et niveau pour les utilisateurs existants."""
    env = api.Environment(cr, SUPERUSER_ID, {})

    # Vérifier si le modèle tour.mission existe déjà
    if 'tour.mission' in env.registry:
        users = env['res.users'].search([])
        for user in users:
            # Compter les missions terminées de cet utilisateur
            Mission = env['tour.mission']
            missions_terminees = Mission.search_count([
                ('assigned_to', '=', user.id),
                ('state', '=', 'terminee'),
            ])
            # 100 XP par mission terminée
            xp_initial = missions_terminees * 100
            if xp_initial > 0:
                user.write({
                    'xp_total': xp_initial,
                    'missions_terminees': missions_terminees,
                })
            # Le compute du niveau se déclenche via xp_total
    else:
        # Pas de modèle mission : on laisse les valeurs par défaut (XP=0, niveau=1)
        pass
