from odoo import fields, models


class EchangeBesoin(models.Model):
    """Un message qu'on doit a quelqu'un — detecte, jamais envoye d'ici.

    La fiche vit le temps du courrier : detectee (a rediger), brouillon
    pret dans Messages (redige), partie (envoye) ou devenue inutile
    (sans suite). Le code est unique : un meme constat ne cree jamais
    deux fiches, il rouvre la sienne.
    """

    _name = "echange.besoin"
    _description = "Un message qu'on doit a quelqu'un"
    _order = "date desc, id desc"

    name = fields.Char("Le besoin", required=True)
    code = fields.Char("Code", required=True, index=True)
    type_dest = fields.Selection(
        [
            ("client", "Client"),
            ("partenaire", "Partenaire"),
            ("invite", "Invité"),
            ("demo", "Démo"),
            ("autre", "Autre"),
        ],
        string="À qui", required=True, default="autre")
    qui = fields.Char("Destinataire")
    origine = fields.Char("Ce qui l'a déclenché")
    detail = fields.Text("Détail")
    date = fields.Datetime("Détecté le", default=fields.Datetime.now)
    etat = fields.Selection(
        [
            ("a_rediger", "À rédiger"),
            ("redige", "Brouillon prêt"),
            ("envoye", "Envoyé"),
            ("sans_suite", "Sans suite"),
        ],
        string="État", required=True, default="a_rediger")
    message_id = fields.Many2one("tour.message", string="Brouillon dans Messages")

    _sql_constraints = [
        ("code_unique", "unique(code)",
         "Un besoin par constat : ce code existe déjà."),
    ]

    def action_envoye(self):
        self.write({"etat": "envoye"})

    def action_sans_suite(self):
        self.write({"etat": "sans_suite"})

    def action_voir_brouillon(self):
        self.ensure_one()
        if not self.message_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "res_model": "tour.message",
            "res_id": self.message_id.id,
            "view_mode": "form",
            "target": "current",
        }
