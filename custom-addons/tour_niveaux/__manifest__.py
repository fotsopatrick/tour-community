# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
{
    'name': 'Tour — Système de Niveaux',
    'version': '1.0.0',
    'category': 'Productivity',
    'summary': 'Ajoute un système de niveaux et d\'XP aux utilisateurs de la tour',
    'description': """
Module de gamification pour la Tour de Contrôle.
- Champs XP et niveau sur les utilisateurs
- Attribution d'XP pour missions terminées
- Calcul automatique du niveau par paliers
- Affichage dans le profil et le tableau de bord
    """,
    'author': 'Clark (Tour de Contrôle)',
    'website': '',
    'depends': ['base', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_users_views.xml',
        'views/tour_dashboard_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
