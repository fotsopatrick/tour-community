# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
{
    "name": "Débats de l'équipe",
    "version": "18.0.1.1.0",
    "summary": "Poser une question à un agent, ou à toute l'équipe",
    "description": """
Débats de l'équipe
==================

Chaque agent répond depuis **son** angle, sans voir les autres. Lois cherche ce
qui casse, Braignak regarde ce qui se fait ailleurs, Clark regarde le code. Une
même question posée à trois métiers donne trois réponses qui ne se ressemblent
pas — et c'est exactement ce qu'on cherche quand on hésite.

**Ils ne se lisent pas entre eux, et c'est délibéré.** Un agent qui lit la
réponse du précédent s'y aligne : on obtient des variations d'un même avis en
croyant avoir consulté plusieurs métiers.

**Ce que ça coûte est annoncé avant.** Chaque participant consomme une mission :
un débat à quatre agents coûte quatre fois un échange.

**Les agents sans moteur ne débattent pas.** Victor, Jimmy et Tess sont du code
déterministe — ils mesurent, ils n'ont pas d'avis.
""",
    "author": "Code Nomi Nomi",
    "license": "OPL-1",
    "category": "Productivity",
    "depends": ["base", "mail", "tour_dashboard", "tour_equipage", "tour_atelier"],
    "data": [
        "security/ir.model.access.csv",
        "security/debat_rules.xml",
        "views/debat_views.xml",
        "views/salle_templates.xml",
        "views/page_debats_public.xml",
    ],
    "installable": True,
    "application": False,
}
