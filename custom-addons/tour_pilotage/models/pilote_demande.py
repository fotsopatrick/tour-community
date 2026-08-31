# -*- coding: utf-8 -*-
"""Le Pilote : un moteur qui joue un gabarit de circuit, porte par porte.

Idée de Patrick (10/08) : un modèle SIMPLE (qui ne réfléchit pas) peut piloter
la tour si on lui donne les méthodes (le gabarit de circuit), le processus
(les portes, une par une) et la consultation en ligne. Ce module est la MOITIE
tour de ce contrat : la demande, le suivi, l'API que le moteur hôte appelle.

Le moteur hôte (pilote.py, côté serveur) fait la boucle :
    demander la tâche (API) → appeler le modèle simple avec la consigne →
    consulter en ligne / lire la tour → rendre la réponse (API) → avancer.

RÈGLE FERME : le pilote exécute le gabarit qu'on lui DÉSIGNE dans la demande.
Il n'en ouvre jamais un tout seul, et les portes « patron » lui sont
interdites : il s'arrête là où Patrick doit trancher.

NOTE (10/08, Merline) : on n'utilise PAS la mécanique d'avancement de
circuit.instance (action_lancer / _porte_repondue) : elle dépose des missions
à l'atelier à chaque porte agent. Le pilote joue ses portes LUI-MÊME, et
consigne dans le passage de l'instance (visibilité cockpit) sans déposer de
mission.
"""

import datetime
import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PiloteDemande(models.Model):
    """Une demande de pilotage : quel gabarit, quel sujet, où ça en est."""
    _name = "pilote.demande"
    _description = "Demande de pilotage"
    _order = "create_date desc, id desc"

    name = fields.Char("Sujet", required=True,
                       help="Ce que le pilote doit faire : un titre, une "
                            "question, une demande.")
    modele_id = fields.Many2one(
        "circuit.modele", "Gabarit", required=True,
        domain="[('active', '=', True)]",
        help="Le gabarit de circuit que le pilote joue. Le pilote n'en "
             "choisit jamais un tout seul : c'est celui-là, désigné ici.")
    description = fields.Text("Le détail à donner au pilote")
    instance_id = fields.Many2one(
        "circuit.instance", "Instance de circuit", readonly=True,
        help="L'instance ouverte par le pilote pour cette demande.")
    etat = fields.Selection(
        [("brouillon", "Brouillon"),
         ("en_attente", "En attente du pilote"),
         ("en_cours", "Le pilote travaille"),
         ("termine", "Terminé"),
         ("refuse", "Refusé"),
         ("patron", "En attente de Patrick"),
         ("erreur", "Erreur")],
        "État", default="brouillon", readonly=True, tracking=True)
    journal = fields.Text("Journal", readonly=True)
    moteur = fields.Char("Moteur du pilote", default="deepseek-chat",
                         help="Le modèle SIMPLE utilisé par le moteur hôte. "
                              "Pas un modèle qui raisonne : c'est la consigne "
                              "et le gabarit qui portent la méthode.")
    passage_en_cours = fields.Many2one(
        "circuit.passage", "Porte en cours", readonly=True)
    porte_nom = fields.Char("Porte en cours", compute="_porte_info")
    nb_portes = fields.Integer("Portes", compute="_porte_info")
    nb_faites = fields.Integer("Portes passées", compute="_porte_info")

    @api.depends("passage_en_cours", "instance_id")
    def _porte_info(self):
        for d in self:
            inst = d.instance_id
            etapes = inst._etapes() if inst else []
            d.nb_portes = len(etapes)
            faites = inst.etape_courante if inst else 0
            d.nb_faites = max(0, min(faites, len(etapes)))
            p = d.passage_en_cours
            d.porte_nom = p.etape_id.name if p else ""

    # ------------------------------------------------------------------
    def _journaliser(self, texte):
        """Ajoute une ligne au journal (horodatée, append-only)."""
        self.ensure_one()
        ligne = "[%s] %s" % (datetime.datetime.now().strftime("%H:%M:%S"),
                             texte)
        self.journal = (self.journal + "\n" if self.journal else "") + ligne

    def _etat(self, nouvel_etat):
        self.ensure_one()
        self.etat = nouvel_etat
        self._journaliser("état → %s" % nouvel_etat)

    # ------------------------------------------------------------------
    def action_envoyer(self):
        """Lance la demande : crée l'instance du gabarit désigné et ouvre la
        première porte, sans passer par l'atelier (le pilote joue lui-même)."""
        self.ensure_one()
        if self.etat != "brouillon":
            raise UserError(_("Cette demande a déjà été envoyée."))
        if not self.modele_id.etape_ids:
            raise UserError(_("Ce gabarit n'a aucune porte."))
        inst = self.env["circuit.instance"].sudo().create({
            "modele_id": self.modele_id.id,
            "name": self.name,
            "sujet": self.description or self.name,
        })
        self.instance_id = inst.id
        inst.etat = "en_cours"
        self._etat("en_cours")
        self._declencher_porte(inst)
        return True

    # ------------------------------------------------------------------
    def _declencher_porte(self, inst):
        """Ouvre la porte suivante de l'instance et renvoie le passage, ou
        termine si toutes les portes sont passées."""
        inst.ensure_one()
        etapes = inst._etapes()
        if inst.etape_courante >= len(etapes):
            inst.etat = "publie_prive"
            inst.message_post(body=_(
                "Toutes les portes sont passées (pilote) — publié en PRIVÉ."))
            self.passage_en_cours = False
            self._etat("termine")
            self._journaliser("toutes les portes passées — terminé.")
            return None
        etape = etapes[inst.etape_courante]
        passage = self.env["circuit.passage"].create({
            "instance_id": inst.id, "etape_id": etape.id})
        inst.etape_courante += 1
        inst.message_post(body=_("Porte « %s » : ouverte par le pilote.")
                          % etape.name)
        self.passage_en_cours = passage.id
        if etape.role == "patron":
            # Le pilote ne touche JAMAIS aux portes de Patrick : il s'arrête
            # et crée UNE FICHE DÉCISION (comme le moteur de circuit normal,
            # _porte_patron) — c'est elle que le bloc Décisions de l'accueil
            # compte. Sans fiche, la validation de Patrick n'apparaissait
            # plus nulle part (trouvé le 10/08, demande 4).
            self._etat("patron")
            self._journaliser("porte « %s » : à Patrick (le pilote s'arrête)."
                              % etape.name)
            if "decision.fiche" in self.env:
                try:
                    fiche = self.env["decision.fiche"].sudo().create({
                        "name": _("Pilote — %s : %s — tu valides ?") % (
                            inst.modele_id.name, inst.name),
                        "origine": _("Pilote (%s)") % inst.modele_id.name,
                        "resume": inst.sujet or "",
                        "res_model": "circuit.instance", "res_id": inst.id,
                        "priorite": "2"})
                    passage.decision_id = fiche.id
                    self._journaliser("décision %s créée pour Patrick."
                                      % fiche.id)
                except Exception as exc:  # noqa: BLE001
                    self._journaliser("échec création décision : %s" % exc)
            return None
        if etape.role == "prod":
            # Mise en production : le pilote la signale, il n'applique pas une
            # mise en prod tout seul.
            self._etat("patron")
            self._journaliser("porte « %s » : mise en production — laissée à "
                              "l'équipe (le pilote ne déploie pas seul)."
                              % etape.name)
            return None
        # rôle « agent » : le pilote travaille la porte.
        self._etat("en_cours")
        self._journaliser("porte « %s » : confiée au pilote." % etape.name)
        return passage

    # ------------------------------------------------------------------
    # API — appelée par le moteur hôte (pilote.py)
    # ------------------------------------------------------------------
    @api.model
    def _api_tache(self, token=""):
        """La prochaine tâche du pilote : une porte à travailler, ou rien."""
        demande = self.search([("etat", "=", "en_cours"),
                               ("passage_en_cours", "!=", False)],
                              order="create_date asc", limit=1)
        if not demande:
            return {"ok": True, "tache": None}
        passage = demande.passage_en_cours
        inst = demande.instance_id
        contenu = re.sub(r"<[^>]+>", " ", inst.sujet or "")
        consigne = (
            "Tu es le PILOTE de la tour. On te confie UNE PORTE d'un circuit.\n"
            "CIRCUIT : %s\nSUJET : %s\nCONTENU :\n%s\n"
            "PORTE À TRAVAILLER : « %s »\n\n"
            "Fais ce que cette porte demande (produis le contenu, la "
            "vérification, la relecture). Reponds en commençant par APPROUVE "
            "ou REFUSE, puis donne ton travail et pourquoi."
            % (inst.modele_id.name, inst.name, (contenu or "")[:4000],
               passage.etape_id.name))
        return {
            "ok": True,
            "tache": {
                "demande_id": demande.id,
                "passage_id": passage.id,
                "instance_id": inst.id,
                "moteur": demande.moteur or "deepseek-chat",
                "consigne": consigne,
                "porte": passage.etape_id.name,
            },
        }

    @api.model
    def _api_repondre(self, token="", demande_id=0, approuve=False, avis=""):
        """Le moteur rend sa réponse à une porte. On avance nous-mêmes."""
        demande = self.browse(int(demande_id))
        if not demande.exists():
            return {"ok": False, "erreur": "demande inconnue"}
        passage = demande.passage_en_cours
        if not passage:
            return {"ok": False, "erreur": "aucune porte en cours"}
        inst = demande.instance_id
        passage.write({
            "etat": "approuve" if approuve else "refuse",
            "avis": avis or ""})
        inst.message_post(body=_("Porte « %s » : %s (pilote).")
                          % (passage.etape_id.name,
                             "approuvée" if approuve else "refusée"))
        demande._journaliser("porte « %s » → %s"
                             % (passage.etape_id.name,
                                "APPROUVE" if approuve else "REFUSE"))
        if not approuve:
            inst.etat = "refuse"
            demande.passage_en_cours = False
            demande._etat("refuse")
            return {"ok": True, "etat": "refuse"}
        demande.passage_en_cours = False
        demande._declencher_porte(inst)
        return {"ok": True, "etat": demande.etat}

    @api.model
    def _api_etat(self, token=""):
        """Ce que le cockpit hôte peut montrer : les demandes, une à une."""
        demandes = self.search([], order="create_date desc", limit=30)
        return {
            "ok": True,
            "demandes": [{
                "id": d.id, "name": d.name,
                "gabarit": d.modele_id.name,
                "etat": d.etat,
                "porte": d.porte_nom or "",
                "faites": d.nb_faites, "total": d.nb_portes,
                "journal": d.journal or "",
                "instance_id": d.instance_id.id,
            } for d in demandes],
        }
