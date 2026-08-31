# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
{
    "name": "Le protocole Zod — sanctionner un agent",
    "version": "18.0.1.0.0",
    "summary": "Renommer, éteindre, faire renaître : la sanction d'un agent, tracée et réversible sur le principe",
    "description": """
Le protocole Zod
================

Un agent qui s'amuse, qui déborde ou qui ne sert plus doit pouvoir être
arrêté — et que ça se voie. Le protocole Zod fait trois choses d'un geste :

1. il renomme l'agent avec un nom de vilain (le nom dit ce qui s'est passé) ;
2. il l'éteint : plus de moteur, plus de conversation, plus de mission ;
3. il fait naître un successeur qui reprend le poste, avec une expérience
   à zéro — le travail se transmet, la réputation ne se transmet pas.

Ce que ce n'est PAS : un bouton de suppression. Rien n'est effacé. La
sanction laisse une fiche datée, avec son motif, et l'agent éteint reste
consultable. Un système qui efface ses fautes ne peut pas en tirer de
leçon — et une punition qu'on ne peut pas relire est une punition qu'on
ne peut pas contester.

Réservé au propriétaire de la tour (administrateur). Chez un client, c'est
LUI l'administrateur : il sanctionne ses agents, pas les nôtres.
""",
    "author": "Code Nomi Nomi",
    "license": "OPL-1",
    "category": "Productivity",
    "depends": ["tour_equipage"],
    "data": [
        "security/ir.model.access.csv",
        "views/sanction_views.xml",
    ],
    "installable": True,
    "application": False,
}
