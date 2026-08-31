from urllib.parse import quote

from markupsafe import Markup

from odoo import api, fields, models


class AppSuivi(models.Model):
    """Une ligne par app : le tableau de bord de l'ecosysteme perso.

    Mis a jour par Claude a chaque session de travail (regle CLAUDE.md),
    en miroir du fichier Desktop/BILAN-APPS.md.
    """

    _name = "app.suivi"
    _description = "Suivi d'une app"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    emoji = fields.Char(default="📱")
    repo = fields.Char(string="Repo GitHub")
    # Pourquoi ce champ existe : le 27/07, Patrick a du redire pour la deuxieme
    # fois que la tour de controle n'est PAS un projet de rentabilite. Sans une
    # distinction ecrite quelque part, chaque nouvelle session repart du reflexe
    # commercial — « et les clients ? », « et le prix ? » — sur un projet dont
    # ce n'est pas l'objet. Ce reflexe est juste pour Duelle. Il est hors sujet
    # pour la tour, et il fatigue.
    finalite = fields.Selection(
        [("outil", "Outil personnel"),
         ("rentable", "Produit destine a rapporter"),
         ("mixte", "Outil d'abord, revenus en arriere-plan")],
        string="Finalite", default="outil", required=True,
        help="Ce que ce projet cherche a produire. Un outil personnel se juge "
             "a ce qu'il permet de faire, pas a ce qu'il rapporte : lui "
             "appliquer une grille commerciale conduit a de mauvais conseils.")
    statut = fields.Selection(
        [
            ("concept", "Concept"),
            ("dev", "En développement"),
            ("beta", "Bêta"),
            ("v1", "Sortie (v1)"),
            ("organe", "Donneur d'organes"),
            ("pause", "En pause"),
        ],
        default="dev",
        required=True,
    )
    progression = fields.Integer(string="Progression (%)", default=0)
    en_cours = fields.Char(
        string="En ce moment",
        help="Ce sur quoi on travaille actuellement — la ligne 'live' du tableau.",
    )
    site_url = fields.Char(
        string="URL du site / de l'app",
        help="Pour les apps/sites externes suivis dans la tour : l'apercu "
        "de la premiere page s'affiche automatiquement.",
    )
    screenshot_html = fields.Html(
        string="Apercu du site",
        compute="_compute_screenshot_html",
        sanitize=False,
    )
    fait = fields.Html(string="Fait")
    reste_v01 = fields.Html(string="Reste pour v0.1")
    reste_v1 = fields.Html(string="Reste pour v1")

    @api.depends("site_url")
    def _compute_screenshot_html(self):
        """Apercu de la premiere page via le service mshots (gratuit, mis en
        cache et rafraichi periodiquement cote service) — v1 du "screenshot
        temps reel" ; un rendu maison viendra avec l'offre hebergee."""
        for rec in self:
            if rec.site_url:
                src = "https://s0.wp.com/mshots/v1/%s?w=1200" % quote(
                    rec.site_url, safe=""
                )
                rec.screenshot_html = (
                    Markup(
                        '<a href="%s" target="_blank">'
                        '<img src="%s" style="max-width:100%%;'
                        'border-radius:8px;" alt="Apercu du site"/></a>'
                    )
                    % (rec.site_url, src)
                )
            else:
                rec.screenshot_html = False
