import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Les noms de vilains. Un agent sanctionné en reçoit un : le nom dit ce qui
# s'est passé, sans qu'on ait à ouvrir la fiche. Ils viennent des mêmes
# univers que les prénoms de l'équipe — la maison a sa mythologie, ses
# héros et ses tombés.
VILAINS = [
    "Zod", "Lex", "Doomsday", "Brainiac", "Metallo", "Darkseid",
    "Bizarro", "Titan", "Parasite", "Toyman",
]

# Ce qu'on ne sanctionne jamais, quoi qu'on en pense.
#
# Patrick n'est pas un agent : c'est le propriétaire, sa fiche existe pour
# porter ses consignes. Se sanctionner soi-même n'a pas de sens, et un
# système qui le permet finit par le faire par accident.
INTOUCHABLES = ("Patrick",)


class EquipeSanction(models.Model):
    """Une sanction prononcée contre un agent. Elle ne s'efface pas.

    Trois gestes en un : le nom de vilain (ce qui s'est passé se lit sur
    la fiche), l'extinction (plus de moteur, plus de conversation), et la
    naissance d'un successeur qui reprend le poste sans l'expérience.

    La fiche reste après coup, motif compris. Un système qui efface ses
    fautes ne peut pas en tirer de leçon, et une punition qu'on ne peut
    pas relire est une punition qu'on ne peut pas contester.
    """

    _name = "equipe.sanction"
    _description = "Sanction d'un agent (protocole Zod)"
    _inherit = ["mail.thread"]
    _order = "date desc, id desc"

    name = fields.Char("Référence", readonly=True, copy=False, default="Nouvelle")
    membre_id = fields.Many2one("equipe.membre", "L'agent sanctionné",
                                required=True, ondelete="restrict")
    nom_avant = fields.Char("Son nom avant", readonly=True, copy=False)
    nom_vilain = fields.Char(
        "Son nom de vilain",
        help="Laisser vide : le prochain nom libre de la liste est pris.")
    motif = fields.Text("Ce qu'on lui reproche", required=True,
                        help="Écrit une fois, lu longtemps. Sois précis : "
                             "c'est ce que liront ceux qui viennent après.")
    date = fields.Datetime("Prononcée le", readonly=True, copy=False)
    etat = fields.Selection(
        [("brouillon", "Brouillon"),
         ("executee", "Exécutée")],
        "État", default="brouillon", required=True, readonly=True,
        tracking=True)
    successeur = fields.Boolean(
        "Faire naître un successeur", default=True,
        help="Le poste reste à tenir. Le successeur hérite du poste, du "
             "périmètre et des refus — jamais de l'expérience.")
    nom_successeur = fields.Char(
        "Nom du successeur",
        help="Laisser vide : il reprend le nom d'origine de l'agent.")
    successeur_id = fields.Many2one("equipe.membre", "Né de cette sanction",
                                    readonly=True, copy=False)

    def _prochain_vilain(self):
        pris = set(self.env["equipe.membre"].with_context(active_test=False)
                   .sudo().search([]).mapped("name"))
        for v in VILAINS:
            if v not in pris:
                return v
        return "Zod-%s" % fields.Datetime.now().strftime("%d%m%H%M")

    def action_executer(self):
        """Le geste. Il n'est pas défait par un bouton : c'est le principe."""
        for s in self:
            if s.etat == "executee":
                raise UserError(_("Cette sanction a déjà été exécutée."))
            m = s.membre_id
            if (m.name or "") in INTOUCHABLES:
                raise UserError(_(
                    "%s n'est pas un agent : c'est le propriétaire de la "
                    "tour. On ne le sanctionne pas.", m.name))
            if not m.active:
                raise UserError(_(
                    "%s est déjà éteint. Une sanction ne se prononce que "
                    "contre un agent en service.", m.name))

            nom_origine = m.name
            vilain = (s.nom_vilain or "").strip() or s._prochain_vilain()

            # 1. Le nom de vilain, et le poste qui dit ce qui s'est passé.
            # 2. L'extinction : sans moteur, il ne peut plus être interrogé
            #    ni recevoir de mission — l'écran le montre, il ne travaille
            #    plus. On garde ses compétences et ses faits : ils ont eu
            #    lieu.
            m.sudo().write({
                "name": vilain,
                "poste": "%s — déchu (%s)" % (m.poste or "", nom_origine),
                "moteur": False,
                "active": False,
                "origine": "Sanctionné le %s. Était %s. Motif : %s" % (
                    fields.Date.today(), nom_origine,
                    (s.motif or "")[:200]),
            })

            # 3. La renaissance. Le poste reste à tenir, l'expérience ne se
            #    transmet pas : le successeur repart de zéro, et ça se voit.
            successeur = False
            if s.successeur:
                successeur = self.env["equipe.membre"].sudo().create({
                    "name": (s.nom_successeur or "").strip() or nom_origine,
                    "poste": (m.poste or "").split(" — déchu")[0] or "Agent",
                    "embleme": m.embleme,
                    "sequence": m.sequence,
                    "moteur": False,
                    "perimetre": m.perimetre,
                    "refus": m.refus,
                    "consignes": m.consignes,
                    "origine": "Né du protocole Zod le %s, après la chute de "
                               "%s (devenu %s)." % (fields.Date.today(),
                                                    nom_origine, vilain),
                })

            s.write({
                "name": "ZOD-%s" % (s.id or 0),
                "nom_avant": nom_origine,
                "nom_vilain": vilain,
                "date": fields.Datetime.now(),
                "etat": "executee",
                "successeur_id": successeur and successeur.id or False,
            })
            s.message_post(body=_(
                "<p><b>%(a)s</b> est devenu <b>%(v)s</b> et a été éteint.</p>"
                "<p>Motif : %(m)s</p>%(s)s",
                a=nom_origine, v=vilain, m=s.motif or "",
                s=(_("<p>Successeur : <b>%s</b>, expérience à zéro. Son "
                     "moteur doit être posé à la main : un agent neuf ne "
                     "parle pas avant qu'on lui donne la parole.</p>")
                   % successeur.name) if successeur else ""))
            self._signaler(nom_origine, vilain, s.motif, successeur)
        return True

    def _signaler(self, avant, vilain, motif, successeur):
        if "tour.signal" not in self.env:
            return
        try:
            self.env["tour.signal"]._signaler(
                agent="Le protocole Zod",
                titre=_("%(a)s est déchu — devenu %(v)s", a=avant, v=vilain),
                corps_html=_(
                    "<p><b>%(a)s</b> a été sanctionné et éteint. Il porte "
                    "désormais le nom de <b>%(v)s</b>.</p><p>Motif : %(m)s</p>"
                    "%(s)s",
                    a=avant, v=vilain, m=motif or "",
                    s=(_("<p>%s reprend le poste, avec une expérience à "
                         "zéro.</p>") % successeur.name) if successeur else ""),
                ton="attention")
        except Exception:  # noqa: BLE001
            _logger.exception("Zod : signal raté")

    @api.model
    def _limites(self):
        """Ce que le protocole ne sait pas faire — dit, pas caché.

        Sert la page d'explication et le compte rendu. Une fonctionnalité
        de sanction qui ne dit pas ses limites donne l'illusion d'un
        pouvoir qu'elle n'a pas.
        """
        return [
            "L'expérience de l'agent déchu reste attachée à son ancien nom : "
            "certains compteurs cherchent le nom (les avis de débat, par "
            "exemple). Le successeur repart donc vraiment de zéro, et "
            "l'historique du déchu ne se recolle pas.",
            "Le successeur naît SANS moteur : il ne parle pas tant qu'on ne "
            "lui en donne pas un. C'est volontaire — un agent neuf qui "
            "répond avant d'être configuré dirait n'importe quoi.",
            "Rien n'est supprimé : l'agent déchu reste consultable, "
            "sanction et motif compris. Ce n'est pas un bouton d'effacement.",
            "Le geste n'a pas de bouton « annuler » : on peut rallumer un "
            "agent à la main, mais son nom de vilain et sa fiche de "
            "sanction restent. Une punition qui s'efface n'en est pas une.",
            "Le propriétaire de la tour ne peut pas être sanctionné : sa "
            "fiche n'est pas celle d'un agent.",
        ]
