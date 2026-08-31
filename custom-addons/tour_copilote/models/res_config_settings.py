from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    copilote_api_key = fields.Char(
        string="Cle API Anthropic",
        config_parameter="tour_copilote.api_key",
        help="Cle sk-ant-... creee sur platform.claude.com. Stockee cote "
        "serveur uniquement, jamais envoyee au navigateur.",
    )
    copilote_model = fields.Char(
        string="Modele Claude",
        config_parameter="tour_copilote.model",
        default="claude-opus-4-8",
    )
    # Tâche 433. Le signal « Claude est de retour » part quand la sonde des
    # agents voit la limite d'abonnement se lever (quota -> ok). Ce réglage
    # permet de le couper sans toucher au serveur — la sonde, elle, continue
    # de tourner : c'est le message qu'on coupe, pas la surveillance.
    copilote_notif_retour = fields.Boolean(
        string="Me prévenir quand Claude est de nouveau disponible",
        config_parameter="tour_copilote.notif_retour",
        default=True,
        help="Quand la limite d'abonnement Claude est atteinte puis se "
             "lève, un signal (et son courriel) te dit que tu peux "
             "recommencer — sans que tu aies à réessayer toutes les heures.",
    )
