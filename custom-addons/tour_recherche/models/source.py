# -*- coding: utf-8 -*-
"""Les endroits où la tour a le droit de chercher.

Le problème vient d'un geste banal. On demande « retrouve mes candidatures »,
et il faut d'abord savoir où regarder. Tant que la réponse reste dans la tête
de celui qui demande, chaque agent invente son chemin, personne ne sait ce qui
a été fouillé, et on rate la moitié.

Un endroit = une fiche. Cochée, la recherche y va. Décochée, elle n'y va pas.

Le cercle est la deuxième moitié du module, et la plus importante. Une boîte
mail personnelle n'est pas un dossier de démonstration : chaque endroit porte
le cercle à partir duquel on a le droit d'entrer. Petit chiffre = fermé.

Un membre du cercle N voit les endroits de cercle N et de tous les cercles
suivants. Patrick (1) voit tout. Un agent (2) ne verra jamais le cercle 1.
Un invité de démonstration (4) ne voit que le cercle 4.

La règle est ici, en code, et pas dans une consigne écrite quelque part :
une consigne, on l'oublie ; une garde mécanique, non. `sources_pour()` filtre,
`verifier_acces()` refuse, et chaque passage laisse une trace — donc on peut
CONTRÔLER qu'un refus a bien eu lieu, au lieu de le croire.
"""
from odoo import _, api, fields, models
from odoo.exceptions import AccessError

# Les cercles. Le chiffre compte : plus il est petit, plus c'est fermé.
CERCLES = [
    ("1", "1 — Patrick, Raphaël, opencode"),
    ("2", "2 — Les agents"),
    ("3", "3 — Réservé"),
    ("4", "4 — Les invités en démonstration"),
]

# Ce qu'est l'endroit, physiquement. Sert à savoir COMMENT on y va.
GENRES = [
    ("mail", "Une boîte mail"),
    ("fichier", "Un dossier de fichiers"),
    ("web", "Un site public"),
    ("service", "Un service qui tourne sur le serveur"),
    ("base", "Une base de la tour"),
    ("depot", "Un dépôt de code"),
    ("autre", "Autre"),
]


class RechercheSource(models.Model):
    _name = "recherche.source"
    _description = "Un endroit où chercher"
    _inherit = ["mail.thread"]
    _order = "cercle, sequence, name"

    name = fields.Char("L'endroit", required=True, tracking=True)
    resume = fields.Char(
        "En une phrase",
        help="Ce qu'on y trouve. C'est ce qui s'affiche dans la liste.")
    genre = fields.Selection(
        GENRES, "Genre", required=True, default="web", index=True,
        help="Ce qu'est l'endroit. Sert à savoir comment on y va.")
    adresse = fields.Char(
        "L'adresse",
        help="L'adresse mail, le chemin du dossier, le lien du site, "
             "le port du service… prête à copier.")

    cercle = fields.Selection(
        CERCLES, "Cercle", required=True, default="1", index=True, tracking=True,
        help="À partir de quel cercle on a le droit d'entrer. "
             "Cercle 1 = le plus fermé.")

    actif = fields.Boolean(
        "On cherche ici", default=True, tracking=True,
        help="Décoché : la recherche n'y va pas, même pour Patrick. "
             "C'est l'interrupteur, pas une suppression.")

    pour_quoi = fields.Char(
        "On y cherche quoi",
        help="Ex. : mes candidatures, mon code, mes factures. "
             "Sert à ne pas fouiller les mails pour trouver du code.")
    comment_y_aller = fields.Text(
        "Comment y aller",
        help="Le mode d'emploi, en clair : l'outil à utiliser, la connexion "
             "à faire. JAMAIS de mot de passe ici.")

    sequence = fields.Integer("Ordre", default=10)
    passage_ids = fields.One2many(
        "recherche.passage", "source_id", "Passages", readonly=True)
    passages_count = fields.Integer(
        "Nombre de passages", compute="_compute_passages_count")
    dernier_passage = fields.Datetime(
        "Dernière fouille", compute="_compute_passages_count",
        help="Lu dans le journal, pas noté à la main : "
             "un compteur tenu à la main finit toujours par mentir.")

    _sql_constraints = [
        ("name_unique", "unique(name)", "Cet endroit est déjà dans la liste."),
    ]

    @api.depends("passage_ids")
    def _compute_passages_count(self):
        for rec in self:
            passages = rec.passage_ids
            rec.passages_count = len(passages)
            rec.dernier_passage = max(passages.mapped("create_date"), default=False)

    # ------------------------------------------------------------------
    # La garde. Tout le module tient dans ces méthodes.
    # ------------------------------------------------------------------
    @api.model
    def cercle_de(self, user=None):
        """Le cercle de quelqu'un, lu dans ses groupes.

        Lu, jamais saisi : un cercle noté à la main dans un champ finirait
        par dire autre chose que les droits réels. Ici les deux ne peuvent
        pas diverger, parce que c'est la même chose.
        """
        user = user or self.env.user
        if user.has_group("base.group_system") or \
                user.has_group("tour_recherche.group_recherche_cercle1"):
            return "1"
        if user.has_group("tour_recherche.group_recherche_cercle2"):
            return "2"
        return "4"

    @api.model
    def sources_pour(self, cercle, pour_quoi=None):
        """Les endroits où quelqu'un de ce cercle a le droit d'aller.

        `cercle` est une chaîne : "1", "2", "3" ou "4".
        On rend les endroits actifs de ce cercle ET des cercles suivants.
        """
        cercle = str(cercle or "4")
        domaine = [("actif", "=", True), ("cercle", ">=", cercle)]
        if pour_quoi:
            domaine.append(("pour_quoi", "ilike", pour_quoi))
        return self.sudo().search(domaine)

    def verifier_acces(self, cercle):
        """Refuse si ce cercle n'a rien à faire ici. Lève une erreur, sec."""
        cercle = str(cercle or "4")
        for rec in self.sudo():
            if not rec.actif:
                raise AccessError(_(
                    "« %s » est décoché : on ne cherche pas ici.") % rec.name)
            if rec.cercle < cercle:
                raise AccessError(_(
                    "« %s » est du cercle %s. Le cercle %s n'y entre pas.")
                    % (rec.name, rec.cercle, cercle))
        return True

    def noter_passage(self, cercle, qui, cherche, trouve=0, note=None):
        """Écrit dans le journal qu'on est passé ici. Vérifie d'abord."""
        self.ensure_one()
        self.verifier_acces(cercle)
        return self.env["recherche.passage"].sudo().create({
            "source_id": self.id,
            "cercle": str(cercle),
            "qui": qui,
            "cherche": cherche,
            "trouve": trouve,
            "note": note,
            "refuse": False,
        })

    @api.model
    def noter_refus(self, source_id, cercle, qui, cherche, motif):
        """Écrit dans le journal qu'on a REFUSÉ.

        Sans cette trace, un refus est invisible : on croit que la garde
        marche, on ne le sait pas. Là, on peut le lire.
        """
        return self.env["recherche.passage"].sudo().create({
            "source_id": source_id,
            "cercle": str(cercle),
            "qui": qui,
            "cherche": cherche,
            "trouve": 0,
            "note": motif,
            "refuse": True,
        })
