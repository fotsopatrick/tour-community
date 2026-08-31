# -*- coding: utf-8 -*-
"""Décisions — la webapp, détachée du backend Odoo.

Chacun voit SES décisions : la règle d'accès « rule_decision_proprietaire »
borne la lecture à `user_id = user.id` (base.group_user), et la règle admin
permet à l'administrateur de voir tout. On ne passe jamais par sudo pour la
liste : la règle est la protection, pas le contrôleur.

Les trois gestes (Approuver / Rejeter / Archiver) appellent les MÊMES
méthodes que le backend — une seule vérité, pas deux écritures qui
divergent. La fiche à décider est relue dans l'environnement de l'appelant :
une fiche qu'on ne voit pas (règle d'accès) est une fiche qu'on ne peut pas
décider. Aucun lien vers /odoo/… ni /web#… ne sort d'ici.
"""
from urllib.parse import quote

from odoo import fields, http
from odoo.http import request


class DecisionWeb(http.Controller):

    def _carte(self, d):
        """Une décision telle qu'elle s'affiche à l'écran, sans backend."""
        return {
            "id": d.id,
            "name": d.titre_lisible or d.name,
            "origine": d.origine_lisible or d.origine or "La tour",
            "resume": d.resume or "",
            "priorite": d.priorite,
            "attend_reponses": d.attend_reponses,
            "depuis": fields.Datetime.context_timestamp(
                d, d.create_date).strftime("%d/%m à %Hh%M"),
            "placeholder": ("Tes réponses, point par point — elles partent à "
                            "l'agent. (Pour rejeter : ce qui ne va pas, en une "
                            "ou deux phrases.)" if d.attend_reponses else
                            "Si tu rejettes, dis pourquoi — l'agent s'en "
                            "servira pour reproposer."),
        }

    @http.route("/tour/decisions", type="http", auth="user", website=False)
    def decisions(self, **kw):
        Decision = request.env["decision.fiche"]
        en_attente = Decision.search(
            [("etat", "=", "attente")], order="priorite, create_date desc")
        decidees = Decision.search(
            [("etat", "in", ("approuve", "rejete", "archive"))],
            order="decide_le desc", limit=15)
        libelles_etat = dict(Decision._fields["etat"].selection)
        libelles_prio = dict(Decision._fields["priorite"].selection)
        carte_decidee = lambda d: {  # noqa: E731
            "id": d.id,
            "name": d.titre_lisible or d.name,
            "etat": libelles_etat.get(d.etat, d.etat),
            "decide_le": (fields.Datetime.context_timestamp(
                d, d.decide_le).strftime("%d/%m à %Hh%M")
                if d.decide_le else ""),
        }
        return request.render("tour_decisions.page_decisions", {
            "en_attente": [self._carte(d) for d in en_attente],
            "decidees": [carte_decidee(d) for d in decidees],
            "libelles_prio": libelles_prio,
            "erreur": (kw.get("erreur") or "").strip(),
            "fait": (kw.get("fait") or "").strip(),
        })

    @http.route("/tour/decisions/decider", type="http", methods=["POST"],
                auth="user", website=False)
    def decider(self, **kw):
        """Approuver / Rejeter / Archiver depuis la page.

        En POST : une action qui MODIFIE ne tient jamais dans un lien — un
        lien se pré-ouvre et se recharge. Le commentaire est écrit sur la
        fiche avant le geste : l'approbation d'un agent bloqué a besoin de
        tes réponses, et un rejet a besoin de son motif.
        """
        Decision = request.env["decision.fiche"]
        try:
            fiche = Decision.browse(int(kw.get("id") or 0))
        except (TypeError, ValueError):
            return request.redirect("/tour/decisions")
        if not fiche.exists() or fiche.etat != "attente":
            return request.redirect("/tour/decisions")

        commentaire = (kw.get("commentaire") or "").strip()
        action = kw.get("action")
        if commentaire:
            fiche.commentaire = commentaire
        try:
            if action == "approuver":
                fiche.action_approuver()
                retour = "/tour/decisions?fait=%s" % quote("Décision approuvée.")
            elif action == "rejeter":
                fiche.action_rejeter()
                retour = "/tour/decisions?fait=%s" % quote("Décision rejetée.")
            elif action == "archiver":
                fiche.action_archiver()
                retour = "/tour/decisions?fait=%s" % quote("Décision classée sans suite.")
            else:
                retour = "/tour/decisions"
        except Exception as exc:  # noqa: BLE001 — UserError remonte à l'écran
            retour = "/tour/decisions?erreur=%s" % quote(str(exc) or "Geste impossible.")
        return request.redirect(retour)
