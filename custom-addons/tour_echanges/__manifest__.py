# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
{
    "name": "Échanges — le courrier qu'on doit (Jonathan)",
    "version": "18.0.1.0.3",
    "summary": "Détecter les messages qu'on doit aux gens, préparer les brouillons, prévenir par courriel",
    "description": """
Échanges — le courrier qu'on doit
=================================

Un invité qui ne s'est jamais connecté, un client à prévenir, la clé de la
démo qui meurt sans bruit : autant de messages qu'on doit à quelqu'un et
qu'on découvre trop tard, parce que personne n'avait le poste.

Jonathan tient ce poste. Chaque jour il fait le tour : les comptes invités
restés muets, la santé de la clé d'IA de la démo, le pouls de la démo. Pour
chaque message dû il ouvre un besoin, prépare le brouillon dans Messages,
et envoie UN courriel de synthèse au responsable — jamais un par trouvaille.

Ce que ce n'est PAS : un module d'envoi automatique. Jonathan écrit les
brouillons et prévient ; l'envoi aux gens reste un geste humain, comme
partout dans Messages. Un veilleur qui écrirait aux clients à ta place
enverrait un jour le mauvais mot au mauvais moment.

La veille ne tourne que là où on l'a armée (paramètre
tour_echanges.veille_active) : la tour mère veille, la démo et les
instances clientes se taisent.
""",
    "author": "Code Nomi Nomi",
    "license": "OPL-1",
    "category": "Productivity",
    "depends": ["base", "tour_messages"],
    "data": [
        "security/ir.model.access.csv",
        "views/besoin_views.xml",
        "data/cron_data.xml",
    ],
    "installable": True,
    "application": False,
}
