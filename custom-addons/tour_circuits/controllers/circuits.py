# -*- coding: utf-8 -*-
"""Le cockpit des circuits (31/07, Patrick).

Patrick : « si possible une webapp pour les circuits déjà présents avec la
même logique de design que cockpit pour mieux ». Les données des circuits
vivent dans la base (pas sur l'hôte) : la page est donc rendue par le
serveur, dans le langage du cockpit (radar, bandeaux de vol, panneaux).

Même verrou que le cockpit agents : base.group_system (pas _is_admin, qui
ouvre au compte démo).
"""
import json

from markupsafe import Markup

from odoo import http
from odoo.http import request

class CircuitsCockpit(http.Controller):

    @http.route("/tour/cockpit/pacman", type="http", auth="user",
                website=False)
    def pacman(self, **kw):
        """Pacman — la donnée qui avance de porte en porte (02/08, Patrick).

        La webapp Pacman des circuits : chaque circuit devient un couloir de
        portes, et la donnée (le pacman) les mange une par une. Mêmes données
        que la carte 2D, mêmes circuits en cours. Même verrou que le cockpit.
        """
        if not request.env.user.has_group("base.group_system"):
            return request.redirect("/tour/dashboard")
        Modele = request.env["circuit.modele"].sudo()
        Instance = request.env["circuit.instance"].sudo()
        # Dernier ajout EN PREMIER (Patrick, 05/08 — redemandé).
        gabarits = Modele.search([("active", "=", True)], order="id desc")
        en_cours = Instance.search(
            [("etat", "=", "en_cours")], order="create_date desc", limit=40)
        membres = request.env["equipe.membre"].sudo().search(
            [("active", "=", True), ("moteur", "!=", False)], order="id")

        circuits = []
        for g in gabarits:
            portes = [{
                "sequence": e.sequence,
                "nom": e.name,
                "agent": (e.membre_id.name
                          if e.role == "agent" and e.membre_id
                          else "Patrick"),
                "role": e.role,
                "obligatoire": e.obligatoire,
            } for e in g.etape_ids.sorted("sequence")]
            circuits.append({
                "name": g.name, "type_operation": g.type_operation,
                "etat": "gabarit", "nb_etapes": g.nb_etapes, "portes": portes,
                "etape_courante": 0,
            })
        for i in en_cours:
            g = i.modele_id
            portes = [{
                "sequence": e.sequence,
                "nom": e.name,
                "agent": (e.membre_id.name
                          if e.role == "agent" and e.membre_id
                          else "Patrick"),
                "role": e.role,
                "obligatoire": e.obligatoire,
            } for e in (g.etape_ids.sorted("sequence"))]
            circuits.append({
                "name": i.name, "type_operation": g.type_operation,
                "etat": "en_cours", "nb_etapes": len(portes), "portes": portes,
                "etape_courante": i.etape_courante or 0,
            })

        return request.render("tour_circuits.page_pacman", {
            "nb_agents": len(membres),
            "nb_gabarits": len(gabarits),
            "nb_en_cours": len(en_cours),
            "pacman_json": Markup(json.dumps(
                {"circuits": circuits},
                ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e")),
        })

    @http.route("/tour/cockpit/carte3d", type="http", auth="user",
                website=False)
    def carte3d(self, **kw):
        """L'ancienne vue 3D est DÉSACTIVÉE (02/08, Patrick).

        Le Pacman est maintenant LA vue. L'URL historique redirige vers le
        jeu pour ne plus laisser personne sur le vieux plan électronique.
        """
        return request.redirect("/tour/cockpit/pacman")

    @http.route("/tour/cockpit/circuits", type="http", auth="user",
                website=False)
    def circuits(self, **kw):
        if not request.env.user.has_group("base.group_system"):
            return request.redirect("/tour/dashboard")
        Modele = request.env["circuit.modele"].sudo()
        Instance = request.env["circuit.instance"].sudo()
        # Dernier ajout EN PREMIER (Patrick, 05/08 — redemandé).
        gabarits = Modele.search([("active", "=", True)], order="id desc")
        detectes = Modele.search(
            [("detecte", "=", True), ("active", "=", False)],
            order="create_date desc", limit=30)
        en_cours = Instance.search(
            [("etat", "=", "en_cours")], order="create_date desc", limit=40)
        publies = Instance.search(
            [("etat", "in", ("publie_prive", "publie_public"))],
            order="create_date desc", limit=20)
        evolutions = []
        if "equipe.membre" in request.env:
            membres = request.env["equipe.membre"].sudo().search(
                [("active", "=", True), ("moteur", "!=", False)], order="id")
            for m in membres:
                missions = m._evolution(limite=6)
                if missions:
                    evolutions.append({"agent": m.name, "missions": missions})

        # --- LA CARTE (plan « circuit imprimé ») --------------------------------
        # Chaque agent devient un composant, chaque circuit une piste qui relie
        # ses portes dans l'ordre. Les données sont passées en JSON à la page,
        # qui les dessine en SVG (aucune librairie externe).
        agents = [{"name": m.name} for m in membres] if "equipe.membre" in request.env else []
        circuits = []
        for g in gabarits:
            portes = [{
                "sequence": e.sequence,
                "nom": e.name,
                "agent": (e.membre_id.name
                          if e.role == "agent" and e.membre_id
                          else "Patrick"),
                "role": e.role,
                "obligatoire": e.obligatoire,
            } for e in g.etape_ids.sorted("sequence")]
            circuits.append({
                "name": g.name, "type_operation": g.type_operation,
                "etat": "gabarit", "nb_etapes": g.nb_etapes, "portes": portes,
                "modele_id": g.id,
            })
        for i in en_cours:
            g = i.modele_id
            portes = [{
                "sequence": e.sequence,
                "nom": e.name,
                "agent": (e.membre_id.name
                          if e.role == "agent" and e.membre_id
                          else "Patrick"),
                "role": e.role,
                "obligatoire": e.obligatoire,
            } for e in (g.etape_ids.sorted("sequence"))]
            circuits.append({
                "name": i.name, "type_operation": g.type_operation,
                "etat": "en_cours", "nb_etapes": len(portes), "portes": portes,
                "instance_id": i.id,
                "etape_courante": i.etape_courante or 0,
                "etape_nom": i.etape_nom or "",
            })
        return request.render("tour_circuits.page_circuits", {
            "gabarits": gabarits,
            "detectes": detectes,
            "en_cours": en_cours,
            "publies": publies,
            "evolutions": evolutions,
            "nb_detectes": len(detectes),
            "nb_gabarits": len(gabarits),
            "nb_en_cours": len(en_cours),
            "nb_publies": len(publies),
            "agents": agents,
            "circuits": circuits,
            "board_json": Markup(json.dumps(
                {"agents": agents, "circuits": circuits},
                ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e")),
            "csrf_token": request.csrf_token(),
            # Le verdict du dernier « ▶ Lancer » (voir la route ci-dessous).
            "lance": kw.get("lance") or "",
            "lance_nom": kw.get("nom") or "",
            "lance_etat": kw.get("etat") or "",
            "echec": kw.get("echec") or "",
        })

    @http.route("/tour/cockpit/circuits/lancer", type="http", auth="user",
                website=False, methods=["POST"], csrf=True)
    def lancer(self, **kw):
        """Relance un gabarit : crée une instance (brouillon) et la démarre.
        C'est le « rejouer » de la carte (piste en pointillés cliquable)."""
        if not request.env.user.has_group("base.group_system"):
            return request.redirect("/tour/dashboard")
        # 06/08 : cette route avalait toute erreur en silence et
        # redirigeait a l'identique. Reussite ou echec, l'ecran ne bougeait
        # pas : impossible de savoir si le play avait fait quelque chose.
        # Desormais le verdict revient dans l'URL et s'affiche en haut.
        from urllib.parse import quote as url_quote
        mid = kw.get("modele_id", "")
        try:
            m = request.env["circuit.modele"].sudo().browse(int(mid))
            if not m.exists():
                raise ValueError("gabarit introuvable")
            inst = request.env["circuit.instance"].sudo().create({
                "modele_id": m.id, "name": m.name,
                "sujet": m.name, "etat": "brouillon",
            })
            inst.action_lancer()
            inst.invalidate_recordset()
            return request.redirect(
                "/tour/cockpit/circuits?lance=%s&nom=%s&etat=%s"
                % (inst.id, url_quote(m.name or ""), inst.etat or ""))
        except Exception as e:  # noqa: BLE001
            request.env.cr.rollback()
            return request.redirect(
                "/tour/cockpit/circuits?echec=%s"
                % url_quote(("%s : %s" % (type(e).__name__, e))[:200]))

    @http.route("/tour/cockpit/circuits/positions", type="http", auth="user",
                website=False)
    def positions(self, **kw):
        """Les positions des circuits EN COURS, pour la carte animée.

        10/08 (Merline) : la carte anime des points qui avancent le long des
        pistes, position = porte courante de chaque instance. Le navigateur
        relit cette route toutes les ~20 s (aucune librairie, fetch simple).
        Même verrou que le cockpit : base.group_system.
        """
        if not request.env.user.has_group("base.group_system"):
            return request.make_response(
                json.dumps({"error": "reserve au pilote"}, ensure_ascii=False),
                status=403,
                headers=[("Content-Type", "application/json; charset=utf-8")])
        Instance = request.env["circuit.instance"].sudo()
        en_cours = Instance.search(
            [("etat", "=", "en_cours")], order="create_date desc", limit=40)
        positions = [{
            "id": i.id,
            "etape_courante": i.etape_courante or 0,
            "etape_nom": i.etape_nom or "",
            "nb_etapes": len(i.modele_id.etape_ids),
        } for i in en_cours]
        return request.make_response(
            json.dumps({"positions": positions}, ensure_ascii=False),
            headers=[("Content-Type", "application/json; charset=utf-8")])
