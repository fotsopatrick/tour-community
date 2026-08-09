# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
"""Webapp « Projets » : un kanban simple pour piloter les projets sans vivre
dans Odoo.

À gauche la liste des projets, à droite les colonnes Backlog / À faire /
En cours / Fait / Test / QA, et au clic sur une carte le détail de la tâche.

Les stages Odoo actuels sont incohérents (Boîte de réception, Aujourd'hui,
Cette semaine, Ce mois, Plus tard, Terminé…) : on ne les touche pas. La
webapp range chaque tâche dans une colonne LOGIQUE selon le nom de son
stage. Quand on déplace une carte vers une colonne dont le stage n'existe
pas encore pour le projet, on crée le stage (Backlog, Test, QA) — c'est le
nettoyage progressif voulu par Patrick.
"""
import json
import unicodedata

from odoo import http
from odoo.http import request


class TourProjets(http.Controller):

    COLONNES = ["backlog", "afaire", "encours", "fait", "test", "qa"]
    TITRES = {
        "backlog": "Backlog",
        "afaire": "À faire",
        "encours": "En cours",
        "fait": "Fait",
        "test": "Test",
        "qa": "QA",
    }

    def _pilote(self):
        # Patrick (admin) et les pilotes de la démo. Un invité ne voit
        # jamais les projets : la lecture se fait SANS sudo, donc avec les
        # règles d'accès d'Odoo — un utilisateur ne voit que ce qu'il a
        # le droit de voir.
        return request.env.user._is_admin()

    @staticmethod
    def _colonne(nom):
        n = (nom or "").strip().lower().replace("'", "").replace("’", "")
        n = n.replace("-", " ").replace("_", " ")
        # Ote les accents : le stage reel s ecrit « À faire » avec l accent,
        # et sans normalisation il retombait toujours dans backlog.
        n = "".join(c for c in unicodedata.normalize("NFD", n)
                    if unicodedata.category(c) != "Mn")
        if n in ("", "inbox", "boite de reception", "aujourd hui",
                 "today", "cette semaine", "this week", "ce mois",
                 "this month", "plus tard", "later", "backlog",
                 "a trier", "a classer", "en attente de priorisation"):
            return "backlog"
        if n in ("a faire", "to do", "todo", "en attente", "pending",
                 "a traiter"):
            return "afaire"
        if "bloque" in n or n in ("en cours", "in progress", "doing",
                                  "en pause", "paused"):
            return "encours"
        if n in ("fait", "termine", "done", "livre", "valide", "cloture"):
            return "fait"
        if "test" in n:
            return "test"
        if n in ("qa", "recette", "qualite"):
            return "qa"
        if n in ("annule", "cancelled", "abandonne"):
            return "annule"
        return "backlog"

    def _stage_ou_creer(self, projet, colonne):
        nom = self.TITRES.get(colonne)
        if not nom:
            return False
        Stage = request.env["project.task.type"]
        existing = Stage.search(
            [("name", "=", nom), ("project_ids", "in", [projet.id])],
            limit=1)
        if existing:
            return existing
        other = Stage.search([("name", "=", nom)], limit=1)
        if other:
            other.write({"project_ids": [(4, projet.id)]})
            return other
        return Stage.create({"name": nom, "project_ids": [(4, projet.id)]})

    def _carte(self, t):
        return {
            "id": t.id,
            "name": t.name,
            "priority": t.priority,
            "deadline": str(t.date_deadline or ""),
            "stage": t.stage_id.name if t.stage_id else "",
            "user": ", ".join(t.user_ids.mapped("name")),
            "tags": [x.name for x in t.tag_ids],
        }

    def _json(self, obj):
        return request.make_json_response(obj)

    # ---------------------------------------------------------------- pages

    @http.route("/tour/projets", type="http", auth="user", website=False)
    def page(self, **kw):
        if not self._pilote():
            return request.redirect("/community")
        return request.render("tour_projets.page", {})

    @http.route("/tour/projets/data", type="http", auth="user", website=False)
    def data(self, projet_id=None, **kw):
        if not self._pilote():
            return self._json({"err": "non autorise"})
        if projet_id:
            try:
                projet_id = int(projet_id)
            except (TypeError, ValueError):
                projet_id = None
        Projects = request.env["project.project"]
        Tasks = request.env["project.task"]
        projets = []
        for p in Projects.search([], order="name"):
            n = Tasks.search_count([("project_id", "=", p.id)])
            if n or p.id == projet_id:
                projets.append({"id": p.id, "name": p.name, "count": n})
        if not projet_id:
            return self._json({"projets": projets})
        taches = Tasks.search(
            [("project_id", "=", projet_id)],
            order="priority desc, date_deadline asc, id desc")
        colonnes = {c: [] for c in self.COLONNES}
        compteur = {}
        for t in taches:
            col = self._colonne(t.stage_id.name if t.stage_id else "")
            if col == "annule":
                continue
            colonnes[col].append(self._carte(t))
            for g in t.tag_ids:
                compteur[g.name] = compteur.get(g.name, 0) + 1
        tags = [{"name": n, "count": c} for n, c in sorted(
            compteur.items(), key=lambda kv: (-kv[1], kv[0]))]
        return self._json({"projets": projets, "colonnes": colonnes,
                           "tags": tags, "projet": projet_id})

    @http.route("/tour/projets/detail/<int:tid>", type="http", auth="user",
                website=False)
    def detail(self, tid=0, **kw):
        if not self._pilote():
            return self._json({"err": "non autorise"})
        t = request.env["project.task"].browse(tid)
        if not t.exists():
            return self._json({"err": "introuvable"})
        return self._json({
            "id": t.id,
            "name": t.name,
            "description": t.description or "",
            "stage": t.stage_id.name if t.stage_id else "",
            "colonne": self._colonne(t.stage_id.name if t.stage_id else ""),
            "project": t.project_id.name if t.project_id else "",
            "priority": t.priority,
            "deadline": str(t.date_deadline or ""),
            "user": ", ".join(t.user_ids.mapped("name")),
            "tags": [x.name for x in t.tag_ids],
            "create": str(t.create_date or ""),
            "write": str(t.write_date or ""),
            "odoo": "/odoo/web#id=%d&model=project.task&view_type=form" % t.id,
        })

    @http.route("/tour/projets/deplacer", type="http", auth="user",
                methods=["POST"], website=False)
    def deplacer(self, **kw):
        if not self._pilote():
            return self._json({"ok": False, "err": "non autorise"})
        try:
            tid = int(kw.get("task_id", 0))
            colonne = kw.get("colonne", "")
        except (TypeError, ValueError):
            return self._json({"ok": False, "err": "parametres invalides"})
        if colonne not in self.TITRES:
            return self._json({"ok": False, "err": "colonne inconnue"})
        t = request.env["project.task"].browse(tid)
        if not t.exists() or not t.project_id:
            return self._json({"ok": False, "err": "tache introuvable"})
        stage = self._stage_ou_creer(t.project_id, colonne)
        if not stage:
            return self._json({"ok": False, "err": "stage introuvable"})
        t.stage_id = stage.id
        return self._json({"ok": True, "stage": stage.name})
