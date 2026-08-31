# -*- coding: utf-8 -*-
"""La salle des débats : une page vivante pour revoir toutes les tentatives.

Même parti pris que le Chrono et l'Équipe : une page HTML rendue par le serveur
(`web.layout`), rafraîchie toute seule, sans une ligne d'OWL ni le moindre
paquet d'assets. C'est robuste, ça marche sur le téléphone, et rien ne casse à
la mise à jour.

Le bornage suit celui de l'accueil : l'administrateur voit tous les débats, un
interne ne voit que les siens et ceux qui ont été ouverts à l'équipe (case
`publie`). La salle ne montre donc jamais plus que ce que le verrou du 30/07
autorise déjà à voir ailleurs.
"""

from odoo import http
from odoo.http import request

import json
import re

from markupsafe import Markup


def _nettoyer_avis(texte):
    """Enlève l'en-tête technique des comptes rendus d'atelier : on garde
    l'avis (le vrai contenu), on jette le squelette du rapport (03/08)."""
    lignes = texte.splitlines()
    # Couper au DERNIER en-tête de section « === ... === » (le vrai avis suit).
    for i in range(len(lignes) - 1, -1, -1):
        if lignes[i].strip().startswith("==="):
            lignes = lignes[i + 1:]
            break
    bruit = re.compile(
        r"(?im)^.*(CONSTRUIT PAR|OBSERV[EÉ] PAR|appels d'outils|jetons|"
        r"ATTENTION|aucun fichier|analyse, pas une livraison|Tours?\s*:).*$")
    gardees = []
    for l in lignes:
        s = l.strip()
        if not s:
            continue
        if s.startswith("- ") or s.startswith("-"):
            continue  # puces de « ce que j'ai compris »
        if bruit.match(s):
            continue
        gardees.append(l)
    return "\n".join(gardees).strip()


ETATS = {
    "brouillon": ("Brouillon", "○"),
    "en_cours": ("Ils réfléchissent", "🕐"),
    "rendu": ("Avis rendus", "✓"),
}


class SalleDebats(http.Controller):

    @http.route("/tour/debats", type="http", auth="user", website=False)
    def salle(self, **kw):
        env = request.env
        user = env.user
        est_admin = user.has_group("base.group_system")

        Debat = env["debat.sujet"].sudo()
        # Le verrou de confidentialité : un interne ne voit que ses débats et
        # ceux ouverts à l'équipe. On ne teste `publie` que s'il existe (il est
        # arrivé le 30/07 ; garder la page installable même sans lui).
        if est_admin:
            domaine = []
        elif "publie" in Debat._fields:
            domaine = ["|", ("create_uid", "=", user.id), ("publie", "=", True)]
        else:
            domaine = [("create_uid", "=", user.id)]
        debats = Debat.search(domaine, order="create_date desc")

        stats = Debat._stats_salle(debats)

        cartes = []
        for d in debats:
            etat_nom, etat_signe = ETATS.get(d.etat, (d.etat, "•"))
            cartes.append({
                "id": d.id,
                "question": d.name,
                "etat": d.etat,
                "etat_nom": etat_nom,
                "etat_signe": etat_signe,
                "tranche": d._est_tranche(),
                "nb_avis": d.nb_avis,
                "nb_attendus": d.nb_attendus,
                # Les emblèmes des participants : le visage de chacun, comme sur
                # la page de l'équipe. Un débat sans participant encore choisi
                # n'en montre aucun.
                "emblemes": [
                    (m.embleme or "•", m.name)
                    for m in d.avis_ids.mapped("membre_id")
                ],
            })

        # --- LA TABLE DE DÉBAT (02/08, Patrick) : une table rectangulaire
        # verticale avec les membres de l'équipe AUTOUR, et en bas une zone
        # de discussion où les avis défilent. La donnée vient de la base,
        # rien n'est dessiné à la main.
        debat_json = []
        for d in debats[:10]:
            participants = [
                {
                    "nom": (a.membre_id.name or "?")[:18],
                    "embleme": (a.membre_id.embleme or "•"),
                    "avis": bool(a.reponse),
                }
                for a in d.avis_ids
            ]
            messages = [
                {
                    "auteur": (a.membre_id.name or "?"),
                    "texte": _nettoyer_avis(a.reponse or "")[:4000],
                }
                for a in d.avis_ids if a.reponse
            ]
            messages = [m for m in messages if m["texte"].strip()]
            debat_json.append({
                "id": d.id,
                "question": (d.name or "")[:80],
                "etat": d.etat,
                "nb_avis": d.nb_avis,
                "nb_attendus": d.nb_attendus,
                "synthese": (d.synthese or "")[:600],
                "participants": participants,
                "messages": messages,
            })

        return request.render("tour_debat.page_salle", {
            "stats": stats,
            "cartes": cartes,
            "est_admin": est_admin,
            "debat_json": Markup(json.dumps(
                debat_json, ensure_ascii=False)
                .replace("<", "\\u003c").replace(">", "\\u003e")),
        })

    @http.route("/tour/debats-public", type="http", auth="public",
                website=False)
    def debats_public(self, **kw):
        """La salle des débats VUE DE LA VITRINE (03/08) : uniquement les
        débats marqués `publie` — jamais les internes. Chaque débat se
        REPJOUE (bouton « Rejouer » : les avis défilent dans l'ordre)."""
        Debat = request.env["debat.sujet"].sudo()
        if "publie" not in Debat._fields:
            return request.not_found()
        debats = Debat.search([("publie", "=", True)],
                              order="create_date desc")

        debat_json = []
        for d in debats:
            participants = [
                {
                    "nom": (a.membre_id.name or "?")[:18],
                    "embleme": (a.membre_id.embleme or "•"),
                    "avis": bool(a.reponse),
                }
                for a in d.avis_ids
            ]
            messages = [
                {
                    "auteur": (a.membre_id.name or "?"),
                    "texte": _nettoyer_avis(a.reponse or "")[:4000],
                }
                for a in d.avis_ids if a.reponse
            ]
            messages = [m for m in messages if m["texte"].strip()]
            debat_json.append({
                "id": d.id,
                "question": (d.name or "")[:80],
                "etat": d.etat,
                "nb_avis": d.nb_avis,
                "nb_attendus": d.nb_attendus,
                "synthese": (d.synthese or "")[:600],
                "participants": participants,
                "messages": messages,
            })

        return request.render("tour_debat.page_debats_public", {
            "total": len(debats),
            "debat_json": Markup(json.dumps(
                debat_json, ensure_ascii=False)
                .replace("<", "\\u003c").replace(">", "\\u003e")),
        })
