from odoo import fields, models


class AppOffre(models.Model):
    """Une offre commerciale (service géré, abonnement, one-shot),
    liable à une app du suivi. Gérée depuis la tour — et avec Claude,
    comme tout le reste (odoo shell)."""

    _name = "app.offre"
    _description = "Offre commerciale"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    app_id = fields.Many2one(
        "app.suivi",
        string="App liée",
        help="L'app ou le site que cette offre couvre (optionnel : une offre "
        "peut être générique, ex. « VPS géré »).",
    )
    statut = fields.Selection(
        [
            ("brouillon", "Brouillon"),
            ("active", "Active"),
            ("archivee", "Archivée"),
        ],
        default="brouillon",
        required=True,
    )
    prix = fields.Float(string="Prix (€)")
    periodicite = fields.Selection(
        [
            ("unique", "One-shot"),
            ("mois", "Par mois"),
            ("an", "Par an"),
        ],
        default="mois",
        required=True,
    )
    client = fields.Char(
        string="Client",
        help="Renseigné quand l'offre est vendue à quelqu'un.",
    )
    description = fields.Html(string="Ce que comprend l'offre")
    notes = fields.Html(string="Notes internes")


class AppSuiviOffres(models.Model):
    _inherit = "app.suivi"

    offre_ids = fields.One2many("app.offre", "app_id", string="Offres liées")
