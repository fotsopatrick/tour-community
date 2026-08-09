# -*- coding: utf-8 -*-
"""Le cockpit des tests (01/08, Patrick : « je veux la webpage des tests »).

Tout ce que la tour sait des tests, au même design que le cockpit :
- les cahiers de recette et leurs étapes (dont « Tests manuels (consigne) ») ;
- les sites surveillés par Vibe et leur dernier état ;
- le dernier passage en détail (ce qui passe, ce qui échoue) ;
- les étapes nées d'un bug (tache_id) — la tâche qui ne peut plus revenir
  en silence.

Même verrou que les autres cockpits : base.group_system.

LE BANC DE TESTS (02/08, Patrick) : « je veux le journal de test et les
tests, pouvoir sélectionner un test à jouer ; s'il réussit un point vert
partout, s'il bloque un point rouge et à côté ce qui bloque ; un récap
ludique de tous les tests ». La page gagne une matrice tests × sites,
jouable à la main, + un journal des derniers passages détaillés.
"""
from odoo import http
from odoo.http import request

import json
from markupsafe import Markup


class TestsCockpit(http.Controller):

    def _chemin_ordres(self, sous):
        """Chemin où déposer/lire les ordres. Paramétrable
        (recette.chemin_ordres) pour qu'un site avec atelier le branche sur
        son dossier ; par défaut, le data_dir d'Odoo (écrivable)."""
        import os
        base = request.env["ir.config_parameter"].sudo().get_param(
            "recette.chemin_ordres", "")
        if base:
            p = os.path.join(base, sous)
        else:
            p = os.path.join(os.path.expanduser("~/.local/share/Odoo"),
                             "ordres", sous)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        return p

    @http.route("/tour/cockpit/recap/rejouer", type="http", auth="user",
                methods=["POST"], csrf=False, website=False)
    def recap_rejouer(self, **kw):
        """Depose l ordre : l atelier rejouera deploy/recap-jour.sh."""
        import json as _json
        import os
        if not request.env.user.has_group("base.group_system"):
            return request.make_response(
                _json.dumps({"ok": False, "erreur": "réservé à l administrateur"}),
                [("Content-Type", "application/json")])
        try:
            p = self._chemin_ordres("recap.ordre")
            with open(p, "w", encoding="utf-8") as f:
                f.write("rejouer le recap du jour (demande depuis le cockpit)\n")
            return request.make_response(_json.dumps({"ok": True}),
                                         [("Content-Type", "application/json")])
        except Exception as exc:  # noqa: BLE001
            return request.make_response(
                _json.dumps({"ok": False, "erreur": str(exc)[:120]}),
                [("Content-Type", "application/json")])


    @http.route("/tour/cockpit/grande-maintenance/rejouer", type="http",
                auth="user", methods=["POST"], csrf=False, website=False)
    def gm_rejouer(self, **kw):
        """Depose l ordre : l atelier rejouera deploy/grande-maintenance.sh
        (bache + tous les tests + reouverture seulement si vert)."""
        import json as _json
        import os
        if not request.env.user.has_group("base.group_system"):
            return request.make_response(
                _json.dumps({"ok": False, "erreur": "réservé à l administrateur"}),
                [("Content-Type", "application/json")])
        try:
            p = self._chemin_ordres("grande-maintenance.ordre")
            with open(p, "w", encoding="utf-8") as f:
                f.write("grande maintenance (demande depuis le cockpit test)\n")
            return request.make_response(_json.dumps({"ok": True}),
                                         [("Content-Type", "application/json")])
        except Exception as exc:  # noqa: BLE001
            return request.make_response(
                _json.dumps({"ok": False, "erreur": str(exc)[:120]}),
                [("Content-Type", "application/json")])

    def _derniere_gm(self):
        """Le dernier passage de grande maintenance, avec sa date."""
        import datetime
        import os
        chemin = self._chemin_ordres("grande-maintenance/dernier.txt")
        if not os.path.exists(chemin):
            return {"quand": "", "texte": "", "verdict": "jamais rejouée"}
        try:
            quand = datetime.datetime.fromtimestamp(
                os.path.getmtime(chemin)).strftime("%d/%m à %H:%M")
            texte = open(chemin, encoding="utf-8").read()[-4000:]
            verdict = "TOUT VERT" if "TOUT VERT" in texte else (
                "ROUGE" if "ROUGE" in texte else "?")
            return {"quand": quand, "texte": texte, "verdict": verdict}
        except Exception:  # noqa: BLE001
            return {"quand": "", "texte": "", "verdict": "illisible"}

    def _dernier_recap(self):
        """Le dernier resultat rejoue, avec sa date. Sans date, on n affirme
        rien : c est la regle du jour."""
        import datetime
        import os
        chemin = self._chemin_ordres("recap/dernier.txt")
        if not os.path.exists(chemin):
            return {"quand": "", "texte": "", "verdict": "jamais rejoué"}
        try:
            quand = datetime.datetime.fromtimestamp(
                os.path.getmtime(chemin)).strftime("%d/%m à %H:%M")
            texte = open(chemin, encoding="utf-8").read()[-4000:]
            verdict = ""
            for ligne in texte.splitlines():
                if "VERDICT" in ligne:
                    verdict = ligne.strip()
            return {"quand": quand, "texte": texte,
                    "verdict": verdict or "sans verdict"}
        except Exception:  # noqa: BLE001
            return {"quand": "", "texte": "", "verdict": "illisible"}

    @http.route("/tour/cockpit/tests", type="http", auth="user",
                website=False)
    def tests(self, **kw):
        if not request.env.user.has_group("base.group_system"):
            return request.redirect("/community")
        Cahier = request.env["recette.cahier"].sudo()
        Etape = request.env["recette.etape"].sudo()
        Cible = request.env["recette.cible"].sudo()
        Passage = request.env["recette.passage"].sudo()

        # Dernier ajout EN PREMIER (Patrick, 05/08 — redemandé) : le tri par
        # nom enterrait les cahiers neufs au milieu de l'alphabet.
        cahiers = Cahier.search([], order="id desc")
        etapes = Etape.search([], order="cahier_id, sequence, id")
        cibles = Cible.search([], order="name")
        passages = Passage.search([], order="create_date desc", limit=8)

        # Le dernier passage de chaque cible, avec le détail étape par étape.
        cibles_detaillees = []
        for c in cibles:
            dernier = Passage.search(
                [("cible_id", "=", c.id)], order="create_date desc", limit=1)
            cibles_detaillees.append({
                "cible": c,
                "dernier": dernier,
                "resultats": dernier.resultat_ids if dernier else [],
            })

        nb_regressions = Passage.search_count([("regression", "=", True)])
        # Le cahier « Tests manuels (consigne) » mérite son propre bandeau.
        manuels = Cahier.search([("name", "=", "Tests manuels (consigne)")],
                                limit=1)

        # --- LE BANC DE TESTS (02/08) : matrice cahier × (sites × tests) ---
        banc = []
        for cahier in cahiers:
            etapes_cahier = cahier.etape_ids.sorted(lambda e: (e.sequence, e.id))
            if not etapes_cahier:
                continue
            cibles_cahier = Cible.search(
                [("cahier_id", "=", cahier.id), ("actif", "=", True)],
                order="name")
            lignes = []
            for c in cibles_cahier:
                dernier = Passage.search(
                    [("cible_id", "=", c.id)],
                    order="create_date desc", limit=1)
                par_etape = {}
                if dernier:
                    for r in dernier.resultat_ids:
                        if r.etape_id:
                            par_etape[r.etape_id.id] = {
                                "etat": r.etat,
                                "detail": (r.detail or ""),
                                # QUAND (04/08) : un resultat sans date ne dit
                                # pas s il vaut encore aujourd hui.
                                "quand": (dernier.create_date.strftime(
                                    "%d/%m à %H:%M")
                                    if dernier.create_date else ""),
                            }
                lignes.append({"cible": c, "par_etape": par_etape})
            # UN CAHIER SANS CIBLE RESTE UN CAHIER (04/08, Patrick : « tous les
            # tests n y sont pas »). Il etait saute ici : ses etapes existaient
            # mais n apparaissaient sur aucune carte. On l affiche, sans ligne.
            banc.append({
                "cahier": cahier,
                "etapes": [{"id": e.id, "name": e.name,
                            "type_etape": e.type_etape,
                            "critique": e.critique} for e in etapes_cahier],
                "lignes": lignes,
            })

        # --- LA CARTE : le banc façon circuit imprimé (03/08, Patrick) ---
        # Chaque cahier devient un composant, chaque test une pastille dorée
        # cliquable (vert = passe partout, rouge = bloque, doré = jamais joué).
        banc_json = []
        for b in banc:
            etapes_carte = []
            for e in b["etapes"]:
                etats = []
                for l in b["lignes"]:
                    r = l["par_etape"].get(e["id"])
                    if r:
                        etats.append(r["etat"])
                etat = ("ok" if etats and all(x == "ok" for x in etats)
                        else ("ko" if any(x == "ko" for x in etats) else "jamais"))
                quand = ""
                for l in b["lignes"]:
                    r = l["par_etape"].get(e["id"])
                    if r and r.get("quand") and r["quand"] > quand:
                        quand = r["quand"]
                etapes_carte.append({
                    "id": e["id"], "name": e["name"],
                    "type": e["type_etape"], "critique": e["critique"],
                    "etat": etat, "nb_cibles": len(b["lignes"]),
                    "quand": quand,
                })
            # LE GROUPE = la cible du cahier (vitrine, tour, boutique...).
            # Il sert au filtre rapide du selecteur — SANS CIBLE est un groupe
            # comme un autre, pas une raison de disparaitre.
            groupe = (b["lignes"][0]["cible"].name if b["lignes"] else "Sans cible")
            banc_json.append({
                "cahier": {"id": b["cahier"].id, "name": b["cahier"].name},
                "groupe": groupe,
                "etapes": etapes_carte,
            })

        # --- LE JOURNAL : derniers passages, avec ce qui bloque en détail ---
        journal = []
        for p in Passage.search([], order="create_date desc", limit=14):
            bloques = []
            for r in p.resultat_ids:
                if r.etat == "ko":
                    bloques.append({"nom": r.nom, "detail": (r.detail or "")})
            journal.append({
                "cible": p.cible_id.name,
                "date": p.create_date,
                "nb_ok": p.nb_ok, "nb_ko": p.nb_ko,
                "regression": p.regression,
                "bloques": bloques[:4],
            })

        return request.render("tour_recette.page_tests", {
            "cahiers": cahiers,
            "etapes": etapes,
            "cibles_detaillees": cibles_detaillees,
            "passages": passages,
            "banc": banc,
            "journal": journal,
            "nb_cahiers": len(cahiers),
            "nb_etapes": len(etapes),
            "nb_cibles": len(cibles),
            "nb_ko_dernier": sum(
                (c["dernier"].nb_ko or 0) for c in cibles_detaillees),
            "nb_regressions": nb_regressions,
            "cahier_manuels": manuels,
            "recap": self._dernier_recap(),
            "gm": self._derniere_gm(),
            "banc_json": Markup(json.dumps(banc_json, ensure_ascii=False)
                                .replace("<", "\\u003c").replace(">", "\\u003e")),
            "csrf_token": request.csrf_token(),
        })

    @http.route("/tour/cockpit/tests/jouer/<int:etape_id>", type="http",
                auth="user", methods=["POST"], csrf=True, website=False)
    def jouer(self, etape_id, **kw):
        """Joue UN test (02/08, Patrick) et répond en JSON.

        Le point vert/rouge vient d'ICI : on exécute la vérification en
        direct (réutilise _executer_etape de Vibe), on consigne un passage
        dans le journal, et la page met à jour les points.
        """
        if not request.env.user.has_group("base.group_system"):
            return request.make_json_response(
                {"ok": False, "detail": "Non autorisé"})
        Etape = request.env["recette.etape"].sudo()
        Cible = request.env["recette.cible"].sudo()
        Passage = request.env["recette.passage"].sudo()

        etape = Etape.browse(etape_id)
        if not etape.exists():
            return request.make_json_response(
                {"ok": False, "detail": "Test introuvable"})

        cibles = Cible.search(
            [("cahier_id", "=", etape.cahier_id.id), ("actif", "=", True)])
        if not cibles:
            return request.make_json_response(
                {"ok": False, "detail": "Aucun site ne porte ce test"})

        resultats = []
        for c in cibles:
            ok, detail = c._executer_etape(etape)
            etat = "ignore" if ok is None else ("ok" if ok else "ko")
            # Consigner dans le journal (un passage minimal, sans conclusion :
            # un jeu manuel ne déclenche pas d'alerte de régression).
            Passage.create({
                "cible_id": c.id,
                "nb_ok": 1 if ok is True else 0,
                "nb_ko": 1 if ok is False else 0,
                "resultat_ids": [(0, 0, {
                    "etape_id": etape.id,
                    "nom": etape.name,
                    "etat": etat,
                    "detail": detail,
                    "critique": etape.critique,
                })],
            })
            resultats.append({
                "cible": c.name,
                "ok": ok,
                "detail": detail,
            })

        return request.make_json_response({
            "etape": etape.name,
            "resultats": resultats,
        })
