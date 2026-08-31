# -*- coding: utf-8 -*-
import json
import logging
import re

from odoo import api, fields, models

from . import classement_local as local

_logger = logging.getLogger(__name__)

CATEGORIES = ["Idée", "Business", "Technique", "Perso", "Famille",
              "Santé", "Sport", "Divers"]

# Réglages, tous surchargeables en paramètres système — pour pouvoir les
# durcir sans toucher au code, et pour pouvoir provoquer chaque comportement
# en le testant.
DEFAUTS = {
    "tour_depot.local_actif": "True",
    "tour_depot.seuil_doublon": "0.55",
    "tour_depot.seuil_confiance": "0.02",
    "tour_depot.accord_minimum": "0.80",
    "tour_depot.exemples_minimum": "12",
    "tour_depot.couverture_minimum": "0.25",
}


class DepotNote(models.Model):
    """La boîte à vrac : on y balance ce qui n'a pas encore de place —
    un texte, une note .txt, un fichier (glisser-déposer dans le fil en
    bas de la fiche). Le Copilote sait chercher dedans, et le rangeur
    automatique classe, résume et repère les doublons (cron 30 min).

    Depuis le 26/07, le rangeur essaie d'abord **sans IA** : les doublons se
    trouvent par distance de Jaccard, le classement par un Bayes naïf qui a
    appris des notes déjà rangées, le résumé par extraction. L'appel au modèle
    n'a lieu que si le classement local ne se juge pas assez sûr — ou s'il n'a
    pas encore fait ses preuves. Voir `classement_local.py`.
    """

    _name = "depot.note"
    _description = "Dépôt (vrac)"
    _inherit = ["mail.thread"]
    # La dernière DÉPOSÉE en premier, et rien d'autre. `write_date desc` (posé
    # à l'origine) classait par dernière MODIFICATION : le rangeur automatique
    # écrit `categorie`, `resume_ia` et `traite` sur les vieilles notes toutes
    # les 30 min, ce qui les remontait en tête devant des notes plus récentes.
    # Constaté le 13/08 : la note #35 (créée à 06:05) passait devant la #36
    # (créée à 06:06). Une boîte à vrac dont l'ordre bouge tout seul n'est plus
    # une pile — on n'y retrouve pas ce qu'on vient d'y jeter.
    # `id desc` en second : deux notes déposées dans la même seconde gardent
    # quand même un ordre stable.
    _order = "create_date desc, id desc"

    name = fields.Char("Titre", required=True, tracking=True)
    contenu = fields.Text("Contenu")
    source = fields.Char(
        "Source",
        help="D'où ça vient : collé à la main, importé du bureau, dicté…",
    )
    categorie = fields.Char("Catégorie", readonly=True,
                            help="Posée automatiquement par le rangeur.")
    resume_ia = fields.Char("Résumé", readonly=True)
    doublon_id = fields.Many2one(
        "depot.note", string="Doublon probable de", readonly=True,
        help="Le rangeur pense que cette note répète celle-ci.")
    traite = fields.Boolean("Rangée", default=False, readonly=True)
    range_par = fields.Selection(
        [("local", "Sans IA (algorithme)"), ("ia", "Par l'IA")],
        string="Rangée par", readonly=True,
        help="Sert à mesurer ce que le classement local fait économiser.")

    # ------------------------------------------------------------------
    def _param(self, clef):
        icp = self.env["ir.config_parameter"].sudo()
        return icp.get_param(clef, DEFAUTS.get(clef, ""))

    def _texte(self):
        self.ensure_one()
        return "%s\n%s" % (self.name or "", (self.contenu or "")[:4000])

    # ------------------------------------------------------------------
    # Le rangeur automatique
    # ------------------------------------------------------------------
    @api.model
    def _cron_ranger(self, limite=10):
        notes = self.sudo().search([("traite", "=", False)], limit=limite,
                                   order="create_date")
        if not notes:
            return

        classifieur, accord = None, 0.0
        if self._param("tour_depot.local_actif") == "True":
            classifieur, accord = self._preparer_classifieur()

        client = None  # créé à la demande : pas d'IA appelée = pas de client
        for note in notes:
            try:
                if note._ranger_sans_ia(classifieur, accord):
                    continue
                if client is None:
                    client = self._client_ia()
                if client is None:
                    # Pas de clé : on range ce qu'on peut sans IA plutôt que
                    # de tout reporter indéfiniment.
                    note._ranger_sans_ia(classifieur, accord, force=True)
                    continue
                note._ranger_une(client)
            except Exception:  # noqa: BLE001 — une note en échec ne bloque pas
                _logger.exception("Depot : rangement de la note %s en echec", note.id)
                note.sudo().traite = True

    @api.model
    def _client_ia(self):
        icp = self.env["ir.config_parameter"].sudo()
        api_key = (icp.get_param("tour_copilote.api_key") or "").strip()
        if not api_key:
            _logger.info("Depot : pas de cle API, rangement IA indisponible.")
            return None
        try:
            import anthropic
        except ImportError:
            return None
        return anthropic.Anthropic(api_key=api_key, timeout=60.0, max_retries=1)

    # ------------------------------------------------------------------
    # Le chemin sans IA
    # ------------------------------------------------------------------
    @api.model
    def _preparer_classifieur(self):
        """Apprend depuis les notes déjà rangées, et mesure son accord.

        Le chiffre rendu est le taux d'accord en validation croisée avec ce
        que l'IA avait posé. C'est lui, et lui seul, qui autorise à se passer
        du modèle : sous le seuil, on ne bascule pas.
        """
        rangees = self.sudo().search(
            [("traite", "=", True), ("categorie", "!=", False)],
            order="write_date desc", limit=400)
        exemples = [(n._texte(), n.categorie) for n in rangees]
        mini = int(self._param("tour_depot.exemples_minimum") or 12)
        conf = float(self._param("tour_depot.seuil_confiance") or 0.02)
        justesse, couverture, nb = local.evaluer(
            exemples, minimum=mini, seuil_confiance=conf)
        if nb < mini:
            _logger.info("Depot : %s exemples seulement, l IA garde la main.", nb)
            return None, 0.0
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param("tour_depot.justesse_mesuree", "%.3f" % justesse)
        icp.set_param("tour_depot.couverture_mesuree", "%.3f" % couverture)
        icp.set_param("tour_depot.exemples_connus", str(nb))
        seuil = float(self._param("tour_depot.accord_minimum") or 0.8)
        couverture_min = float(self._param("tour_depot.couverture_minimum") or 0.25)
        if justesse < seuil or couverture < couverture_min:
            _logger.info(
                "Depot : justesse %.0f%% (seuil %.0f%%), couverture %.0f%% "
                "(seuil %.0f%%) — l IA garde la main.",
                justesse * 100, seuil * 100, couverture * 100, couverture_min * 100)
            return None, justesse
        _logger.info("Depot : classement local actif — justesse %.0f%%, "
                     "couverture %.0f%%, %s exemples.",
                     justesse * 100, couverture * 100, nb)
        return local.entrainer(exemples), justesse

    def _ranger_sans_ia(self, classifieur, accord, force=False):
        """Range la note par calcul. Rend True si elle est rangée.

        `force` : on n'a pas d'IA disponible — on fait au mieux plutôt que de
        laisser la note en plan. Le champ « Rangée par » gardera la trace.
        """
        self.ensure_one()
        texte = self._texte()

        # 1. Le doublon, toujours en local : c'est du calcul, pas du sens.
        seuil_d = float(self._param("tour_depot.seuil_doublon") or 0.55)
        autres = self.sudo().search(
            [("id", "!=", self.id), ("traite", "=", True)],
            order="write_date desc", limit=200)
        trouve = local.chercher_doublon(
            texte, [(n.id, n._texte()) for n in autres], seuil=seuil_d)
        vals = {}
        if trouve:
            vals["doublon_id"] = trouve[0]

        # 2. La catégorie, seulement si le classifieur a fait ses preuves ET
        #    se juge sûr sur CETTE note.
        categorie = None
        if classifieur is not None:
            prediction, confiance = classifieur.predire(texte)
            seuil_c = float(self._param("tour_depot.seuil_confiance") or 0.02)
            if prediction in CATEGORIES and (confiance >= seuil_c or force):
                categorie = prediction

        if categorie is None and not force:
            # On a peut-être trouvé un doublon ; on ne l'écrit pas encore,
            # l'IA repassera sur la note entière.
            return False

        if categorie:
            vals["categorie"] = categorie
        vals["resume_ia"] = local.resumer(self.contenu or self.name or "")
        vals["traite"] = True
        vals["range_par"] = "local"
        self.sudo().write(vals)
        self._compter("tour_depot.appels_evites")
        return True

    @api.model
    def _compter(self, clef):
        icp = self.env["ir.config_parameter"].sudo()
        try:
            n = int(icp.get_param(clef, "0"))
        except ValueError:
            n = 0
        icp.set_param(clef, str(n + 1))

    # ------------------------------------------------------------------
    # Le chemin avec IA (inchangé, il reste le professeur)
    # ------------------------------------------------------------------
    def _ranger_une(self, client):
        self.ensure_one()
        existantes = self.sudo().search(
            [("id", "!=", self.id), ("traite", "=", True)],
            order="write_date desc", limit=60)
        catalogue = "\n".join(
            f"- id {n.id} : {n.name} [{n.categorie or '-'}] {(n.resume_ia or '')[:80]}"
            for n in existantes) or "(aucune)"
        prompt = (
            "Tu ranges la boite a vrac d'un utilisateur. Voici une NOTE :\n"
            f"TITRE : {self.name}\nCONTENU : {(self.contenu or '')[:2500]}\n\n"
            f"NOTES DEJA RANGEES :\n{catalogue}\n\n"
            f"Categories autorisees : {', '.join(CATEGORIES)}.\n"
            "Reponds UNIQUEMENT ce JSON : {\"categorie\": \"...\", "
            "\"resume\": \"une phrase en francais\", "
            "\"doublon_id\": <id de la note dupliquee ou null>, "
            "\"titre_ameliore\": \"titre court et clair ou null si le titre actuel est bon\"}"
        )
        reponse = client.messages.create(
            model="claude-haiku-4-5", max_tokens=300,
            messages=[{"role": "user", "content": prompt}])
        brut = "".join(b.text for b in reponse.content if b.type == "text")
        m = re.search(r"\{.*\}", brut, re.DOTALL)
        data = json.loads(m.group(0)) if m else {}
        vals = {"traite": True, "range_par": "ia"}
        if data.get("categorie") in CATEGORIES:
            vals["categorie"] = data["categorie"]
        if data.get("resume"):
            vals["resume_ia"] = str(data["resume"])[:250]
        doublon = data.get("doublon_id")
        if doublon and self.sudo().browse(int(doublon)).exists():
            vals["doublon_id"] = int(doublon)
        if data.get("titre_ameliore"):
            vals["name"] = str(data["titre_ameliore"])[:120]
        self.sudo().write(vals)
        self._compter("tour_depot.appels_ia")
