{
    "name": "Cloisonnement de la tour",
    "summary": "Les donnees de Patrick et le travail interne ne sont pas lisibles par un compte sans droits",
    "description": """
Mesure du 06/08/2026, sous l'identite reelle d'un compte sans droits : sur 92
modeles portant des donnees, 49 etaient ENTIEREMENT visibles. Dont le CV de
Patrick, ses pointages, ses corrections du Clone, et les 2012 etapes de
missions pourtant fermees.

Ce module pose deux regles par modele concerne : chacun les siennes (ou rien
du tout pour ce qui n'appartient a personne), et l'administrateur voit tout.

Ce qui reste COMMUN, volontairement : la vitrine — equipe.membre,
tour.nouveaute, actus.article, roadmap.*. On verifie avant de fermer qu'aucune
page publique ne lit le modele sans sudo().
""",
    "version": "18.0.1.0.0",
    "author": "Code Nomi Nomi",
    # Proprietaire : rend applicable une revente a un seul niveau.
    "license": "OPL-1",
    "category": "Productivity",
    # AUCUNE dependance vers les 27 modules concernes : les regles sont
    # posees par code, et un modele absent est saute au lieu de tout casser.
    "depends": ["base"],
    "data": [],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
    "auto_install": False,
}
