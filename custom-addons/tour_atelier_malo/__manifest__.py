# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
{
    'name': 'Tour — Atelier Malo',
    'version': '18.0.1.0.0',
    'category': 'Tour',
    'summary': 'Envoyer des missions à l\'atelier Malo (cerveau local, Ollama sur le Raspberry Pi)',
    'description': 'Une webapp pour confier une mission au cerveau local. Aucune clé consommée : le modèle qwen2.5:1.5b tourne sur le Raspberry de la maison, le tunnel Ollama est maintenu par le Pi. Utile quand DeepSeek est à sec et pour les tâches simples.',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/atelier_malo_templates.xml',
        'data/cron.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'OPL-1',
    'author': 'Patrick Orel Kamdem Fotso — Code Nomi Nomi',
}
