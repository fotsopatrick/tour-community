from odoo import _, api, fields, models


class AppApporteur(models.Model):
    """Un apporteur d'affaires : quelqu'un qui amène des clients
    (ex. Imane et son affiche au tabac) et touche une rémunération
    sur les offres vendues grâce à lui.

    Deux principes tiennent tout le reste :

    1. **Il voit ce qu'il gagne, en direct.** Un apporteur qui doit demander
       « alors, ça a donné quoi ? » cesse d'apporter. On lui rattache un compte
       et il consulte sa propre fiche quand il veut.
    2. **On ne mélange jamais un abonnement avec un paiement unique.**
       Additionner 25 €/mois et 490 € one-shot donne un nombre qui ne veut rien
       dire — et c'est ce nombre qu'on lui montrerait. C'était le cas jusqu'au
       26/07.
    """

    _name = "app.apporteur"
    _description = "Apporteur d'affaires"
    _order = "name"

    name = fields.Char("Nom", required=True)
    telephone = fields.Char("Téléphone")
    email = fields.Char("E-mail")
    user_id = fields.Many2one(
        "res.users", string="Son compte",
        help="Le compte avec lequel il se connecte pour suivre ses apports. "
             "Rattaché ici, il ne voit QUE sa fiche et QUE les ventes qu'il a "
             "apportées — rien d'autre de la tour.",
    )
    actif = fields.Boolean("Actif", default=True)
    canal = fields.Char(
        "Canal",
        help="Comment il apporte : affiche en boutique, bouche-à-oreille, réseaux…",
    )

    # ------------------------------------------------------- rémunération
    mode = fields.Selection(
        [("pourcentage", "Pourcentage du prix"),
         ("fixe", "Redevance fixe par vente"),
         ("mixte", "Les deux")],
        string="Mode de rémunération", default="pourcentage", required=True,
        help="Le pourcentage suit le prix — il récompense les grosses ventes. "
             "La redevance fixe est prévisible et se comprend en une phrase, "
             "ce qui la rend plus facile à faire accepter.",
    )
    commission_pct = fields.Float(
        "Commission (%)", default=10.0,
        help="Part reversée sur chaque offre vendue grâce à lui.",
    )
    redevance_fixe = fields.Float(
        "Redevance fixe (€)", default=0.0,
        help="Montant versé par vente apportée, quel que soit le prix. "
             "Sur une offre récurrente, il est dû à chaque échéance.",
    )
    duree_mois = fields.Integer(
        "Durée (mois)", default=12,
        help="Combien de temps la rémunération court sur une offre récurrente. "
             "0 = sans limite. À faire figurer dans l'accord : c'est le point "
             "qui fâche quand personne ne l'a écrit.",
    )
    accord = fields.Html(
        "Accord",
        help="Ce qui a été convenu, par écrit ici pour ne jamais l'oublier "
             "(durée, assiette, mode de versement…).",
    )
    notes = fields.Html("Notes")

    offre_ids = fields.One2many("app.offre", "apporteur_id", string="Ventes apportées")
    nb_ventes = fields.Integer(compute="_compute_totaux", string="Ventes actives")
    du_mensuel = fields.Float(
        compute="_compute_totaux", string="Dû par mois (€)",
        help="Ce qu'il touche chaque mois sur les abonnements en cours. "
             "Les offres annuelles sont ramenées au mois pour être comparables.",
    )
    du_ponctuel = fields.Float(
        compute="_compute_totaux", string="Dû une seule fois (€)",
        help="Ce qu'il touche sur les ventes sans reconduction.",
    )
    resume_remuneration = fields.Char(
        compute="_compute_totaux", string="En clair",
        help="La phrase à lui dire.",
    )

    @api.depends("offre_ids.statut", "offre_ids.prix", "offre_ids.periodicite",
                 "commission_pct", "redevance_fixe", "mode")
    def _compute_totaux(self):
        for ap in self:
            actives = ap.offre_ids.filtered(lambda o: o.statut == "active")
            ap.nb_ventes = len(actives)
            mensuel = ponctuel = 0.0
            for offre in actives:
                part = 0.0
                if ap.mode in ("pourcentage", "mixte"):
                    part += (offre.prix or 0.0) * (ap.commission_pct or 0.0) / 100.0
                if ap.mode in ("fixe", "mixte"):
                    part += ap.redevance_fixe or 0.0
                # Une offre annuelle ramenée au mois : sinon on additionne des
                # euros qui n'ont pas la même unité de temps.
                if offre.periodicite == "mois":
                    mensuel += part
                elif offre.periodicite == "an":
                    mensuel += part / 12.0
                else:
                    ponctuel += part
            ap.du_mensuel = mensuel
            ap.du_ponctuel = ponctuel
            morceaux = []
            if mensuel:
                morceaux.append(_("%.2f € par mois") % mensuel)
            if ponctuel:
                morceaux.append(_("%.2f € en une fois") % ponctuel)
            ap.resume_remuneration = (
                " + ".join(morceaux) if morceaux
                else _("Rien pour l'instant — aucune vente active apportée."))

    # ------------------------------------------------------------------
    @api.model
    def _pour_utilisateur(self, user=None):
        """La fiche de cette personne, si elle est apporteur."""
        user = user or self.env.user
        return self.search([("user_id", "=", user.id), ("actif", "=", True)],
                           limit=1)


class AppOffreApporteur(models.Model):
    _inherit = "app.offre"

    apporteur_id = fields.Many2one(
        "app.apporteur", string="Apporté par",
        help="Qui a amené ce client — sa rémunération se calcule sur sa fiche.",
    )
