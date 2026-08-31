# -*- coding: utf-8 -*-
# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
{
    'name': 'Chloe — webapp (onglets, contexte, étapes)',
    'version': '18.0.1.0.0',
    'category': 'Tour',
    'summary': 'Une nouvelle Chloé : onglets de chat à gauche, étapes des missions cochées à droite. Ne touche pas au copilote existant.',
    'description': "Webapp Chloe : conversations en onglets (contexte par onglet), "
                   "même moteur que le copilote (executer_chat), panneau de droite "
                   "avec les missions et leurs étapes (atelier.mission.etape) cochées en direct.",
    'author': 'Code Nomi Nomi',
    'depends': ['base', 'web', 'tour_copilote', 'tour_atelier'],
    'data': [
        'security/ir.model.access.csv',
        'security/ir.rule.xml',
        'views/chloe_templates.xml',
        'data/actions_menu.xml',
    ],
    'license': 'OPL-1',
    'installable': True,
}
