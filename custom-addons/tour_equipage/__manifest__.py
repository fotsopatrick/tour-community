# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
{
    "name": "Nakama — l'équipe",
    "version": "18.0.1.4.0",
    "summary": "Qui compose l'équipe, ce que chacun a réellement fait, et à quel niveau",
    "description": """
Nakama — l'équipe
===================

Une page qui montre les agents de la tour comme des personnages : un niveau,
de l'expérience, des compétences qui montent.

Ce n'est pas un habillage. **L'expérience se gagne uniquement par du travail
constaté** : une mission rendue, un défaut confirmé, un contrôle passé, un
guide écrit. Chaque point est une ligne datée dans un registre, et le niveau
n'est que la somme de ce registre. Personne — pas même l'administrateur — ne
peut écrire « niveau 5 » : le champ est calculé.

C'est la seule façon qu'une jauge veuille dire quelque chose. Une barre qu'on
remplit à la main décore ; une barre qu'on ne peut que mériter renseigne.
""",
    "author": "Code Nomi Nomi",
    "license": "OPL-1",
    "category": "Productivity",
    "depends": ["tour_dashboard", "base", "web", "tour_de_controle", "tour_discussion"],
    "data": [
        "security/ir.model.access.csv",
        "security/regles_perso.xml",
        "views/page_equipage.xml",
        "views/page_agent.xml",
        "views/page_specs_agents.xml",
        "views/page_recompense.xml",
        "views/membre_views.xml",
        "views/recrutement_views.xml",
        "data/membres.xml",
    ],
    "installable": True,
    "application": False,
}
