# -*- coding: utf-8 -*-
"""La bibliothèque de messages : garder ce qu'on réécrit sans cesse.

Le besoin, dit par Patrick : les messages qu'on prépare (invitations, accès,
remerciements) se perdaient dans le chat, et on les refaisait à chaque fois.

Le choix qui compte : ce modèle NE PART RIEN. Il garde, il affiche, il facilite
le copier. L'envoi reste un geste humain, dans l'outil de son choix. Un texte
gardé n'engage personne ; un envoi automatique décidé par la tour, si — et ce
n'est pas ce qu'on veut d'une simple bibliothèque.
"""

from odoo import fields, models

CATEGORIES = [
    ("invitation", "Invitation / accès"),
    ("client", "Client"),
    ("relance", "Relance"),
    ("remerciement", "Remerciement"),
    ("apporteur", "Apporteur d'affaires"),
    ("extra", "Extraordinaire"),
    ("perform", "Performance"),
    ("perso", "Perso"),
    # Les annonces publiques : ce qu on poste sur X, LinkedIn, Facebook.
    # Elles ne s ecrivent pas comme un message a une personne — d ou
    # leur categorie a elles (demande de Patrick, 05/08/2026).
    ("reseaux", "Réseaux sociaux"),
    ("autre", "Autre"),
]


class TourMessage(models.Model):
    _name = "tour.message"
    _description = "Message gardé, prêt à copier"
    _order = "categorie, sequence, id"

    name = fields.Char("Titre", required=True)
    user_id = fields.Many2one(
        "res.users", "À qui", required=True, index=True,
        default=lambda self: self.env.user,
        help="Le propriétaire de ce message. Chacun ne voit que les "
             "siens ; l'administrateur voit tout.")
    # `pour_qui` reste un texte libre : il dit à qui le message est
    # DESTINÉ (« le client », « Imane »). `user_id` dit à qui il
    # APPARTIENT. Les deux ne se confondent pas, et seul le second
    # peut servir de clé — un Char ne se compare pas à un user.id.
    categorie = fields.Selection(CATEGORIES, "Catégorie", default="autre", required=True)
    corps = fields.Text("Message", required=True,
                        help="Le texte prêt à coller. Les crochets comme "
                             "[Prénom] se remplacent à la main avant l'envoi.")
    pour_qui = fields.Char("Pour qui", help="À qui ce message est destiné, en un mot.")
    remarque = fields.Text("Quand l'utiliser")
    sequence = fields.Integer(default=10)
    active = fields.Boolean("Actif", default=True)

    # TRAITE : le message a servi, il sort de la liste sans etre perdu.
    #
    # Patrick : << il faut pouvoir marquer un message comme traite, il
    # disparait de la liste et est archive >>. Une bibliotheque qui ne fait que
    # grossir devient illisible : au bout de vingt messages, on ne retrouve
    # plus celui qu on cherche, et on le reecrit — exactement le probleme que
    # ce module devait resoudre.
    #
    # Archiver plutot que supprimer : un message envoye une fois resservira,
    # et on veut pouvoir le relire pour savoir ce qu on avait dit.
    traite = fields.Boolean("Traité", default=False, copy=False)
    traite_le = fields.Datetime("Traité le", readonly=True, copy=False)

    def action_traite(self):
        """Marquer traite : le message quitte la liste et part aux archives."""
        for rec in self:
            rec.write({"traite": True,
                       "traite_le": fields.Datetime.now(),
                       "active": False})
        return True

    def action_reprendre(self):
        """Le remettre dans la liste. Se tromper doit rester rattrapable."""
        for rec in self:
            rec.write({"traite": False, "traite_le": False, "active": True})
        return True
