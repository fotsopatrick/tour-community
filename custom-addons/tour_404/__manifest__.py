{
    'name': 'Tour 404 — page d erreur avec le header de la vitrine',
    'version': '18.0.1.0.0',
    'category': 'Tour',
    'summary': 'Remplace la 404 web d Odoo par le design de la vitrine (header compris).',
    'description': 'La 404 de la tour montrait le logo Odoo par defaut. Ce module surcharge '
                   'http_routing.404 avec la page construite par la vitrine (header, carte 404).',
    'author': 'Patrick Orel Kamdem Fotso — Code Nomi Nomi',
    'license': 'OPL-1',
    'depends': ['base'],
    'data': [
        'views/404_templates.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
