{
    "name": "Messages — la bibliothèque",
    "version": "18.0.1.0.1",
    "summary": "Garder les messages qu'on réécrit à chaque fois, et les copier en un geste",
    "description": """
Messages — la bibliothèque
==========================

Une invitation à un testeur, un message d'accès à un client, un remerciement
après un achat : ce sont toujours les mêmes, et on les réécrit à chaque fois
parce qu'ils vivaient dans une conversation qui a défilé.

Ici on les garde. Chacun a un titre, une catégorie et un corps prêt à coller —
avec un bouton Copier, pour qu'un message parte du téléphone en un geste plutôt
qu'en le retapant. On adapte le prénom, on envoie.

Ce que ce n'est PAS : un module d'envoi automatique. La tour n'envoie rien à ta
place ici — tu copies, tu colles où tu veux (WhatsApp, SMS, courriel). Un texte
gardé n'engage personne ; un envoi automatique, si.
""",
    "author": "Code Nomi Nomi",
    "license": "AGPL-3",
    "category": "Productivity",
    "depends": ["base", "web"],
    "data": [
        "security/ir.model.access.csv",
        "security/regles.xml",
        "views/message_views.xml",
        "views/page_messages.xml",
        "data/messages.xml",
        "data/annonces-jeux.xml",
    ],
    "installable": True,
    "application": True,
}
