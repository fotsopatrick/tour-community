# -*- coding: utf-8 -*-
# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
"""Page Appels API — la consommation DeepSeek en carte circuit animée.

10/08 (Merline) : la page devient une carte « circuit imprimé » animée, dans
le langage de la carte des circuits (tour_circuits) : chaque agent est un
composant, la clé DeepSeek est l'alimentation, chaque flux d'appels est une
piste dont l'épaisseur porte le volume. Les données arrivent en JSON et la
page les dessine en SVG, sans librairie externe.
"""
import json
from datetime import date as date_cls, timedelta

from markupsafe import Markup

from odoo import http
from odoo.http import request

# Tarifs DeepSeek (euros par million de jetons), mêmes que le modèle.
COUT = ("(coalesce(tokens_entree,0)/1000000.0)*0.25"
        " + (coalesce(tokens_sortie,0)/1000000.0)*1.0")


class PageAppels(http.Controller):

    def _periode(self, depuis, par_heure=False):
        """Agrégats d'une période (depuis une date) : par agent + totaux.

        par_heure : quand la période est « aujourd'hui », la série est par
        heure (0..23) ; sinon par jour.
        """
        cr = request.env.cr
        sql = ("SELECT agent, count(*) AS nb,"
               " coalesce(sum(tokens_entree),0) AS entree,"
               " coalesce(sum(tokens_sortie),0) AS sortie,"
               " coalesce(sum(%s),0) AS cout, sum(refuse::int) AS refus"
               " FROM api_appel WHERE date >= %%s"
               " GROUP BY agent ORDER BY cout DESC" % COUT)
        cr.execute(sql, (depuis,))
        agents = [{
            "agent": r[0] or "?", "nb": r[1], "entree": r[2],
            "sortie": r[3], "cout": round(r[4] or 0, 4), "refus": r[5] or 0,
        } for r in cr.fetchall()]
        sql = ("SELECT count(*), coalesce(sum(tokens_entree),0),"
               " coalesce(sum(tokens_sortie),0), coalesce(sum(%s),0)"
               " FROM api_appel WHERE date >= %%s" % COUT)
        cr.execute(sql, (depuis,))
        t = cr.fetchone()
        serie = []
        if par_heure:
            cr.execute("""
                SELECT EXTRACT(hour FROM horodatage)::int AS h, count(*),
                       coalesce(sum(tokens_entree),0),
                       coalesce(sum(tokens_sortie),0)
                FROM api_appel WHERE date = %s GROUP BY h ORDER BY h""",
                       (depuis,))
            serie = [{"cle": "%02dh" % r[0], "nb": r[1], "entree": r[2],
                      "sortie": r[3]} for r in cr.fetchall()]
        else:
            cr.execute("""
                SELECT date, count(*), coalesce(sum(tokens_entree),0),
                       coalesce(sum(tokens_sortie),0)
                FROM api_appel WHERE date >= %s GROUP BY date ORDER BY date""",
                       (depuis,))
            serie = [{"cle": str(r[0]), "nb": r[1], "entree": r[2],
                      "sortie": r[3]} for r in cr.fetchall()]
        return {
            "agents": agents,
            "totaux": {"nb": t[0], "entree": t[1], "sortie": t[2],
                       "cout": round(t[3] or 0, 4)},
            "serie": serie,
        }

    def _top_missions(self, depuis, limite=12):
        """Les missions qui consomment le plus, titres résolus depuis
        atelier.mission (jeton ou nom)."""
        cr = request.env.cr
        sql = ("SELECT mission, count(*), sum(tokens_entree),"
               " sum(tokens_sortie), sum(%s)"
               " FROM api_appel"
               " WHERE mission <> '' AND date >= %%s"
               " GROUP BY mission ORDER BY 5 DESC LIMIT %s" % (COUT, limite))
        cr.execute(sql, (depuis,))
        rows = [{"mission": r[0], "nb": r[1], "entree": r[2], "sortie": r[3],
                 "cout": round(r[4] or 0, 4)} for r in cr.fetchall()]
        slugs = [r["mission"] for r in rows]
        if slugs and "atelier.mission" in request.env:
            Mission = request.env["atelier.mission"].sudo()
            titres = {}
            for m in Mission.search([("jeton", "in", slugs)]):
                titres[m.jeton] = m.name
            for m in Mission.search([("name", "in", slugs)]):
                titres[m.name] = m.name
            for r in rows:
                r["titre"] = titres.get(r["mission"]) or r["mission"]
        # Largeur de barre pré-calculée (le % en dur dans le gabarit QWeb est
        # décodé par QWeb avant le formatage : payé le 10/08, « incomplete
        # format » sur la page appels).
        max_cout = max((r["cout"] or 0) for r in rows) if rows else 0
        for r in rows:
            r["pct"] = round((r["cout"] or 0) / max_cout * 100, 1) \
                if max_cout else 0
            r["cout_txt"] = "%.3f EUR" % (r["cout"] or 0)
        return rows

    @http.route("/tour/appels", type="http", auth="user", website=False)
    def appels(self, **kw):
        if not request.env.user.has_group("base.group_system"):
            return request.redirect("/tour/dashboard")
        Appel = request.env["api.appel"].sudo()
        appels = Appel.search([], order="horodatage desc", limit=60)
        # cout_estime est un champ CALCULÉ non stocké : on recalcule en SQL
        # (tarifs DeepSeek 0.25/1.0 par million), pas de colonne en base.
        request.env.cr.execute("""
            SELECT agent, count(*) AS nb,
                   coalesce(sum(tokens_entree),0) AS entree,
                   coalesce(sum(tokens_sortie),0) AS sortie,
                   coalesce(sum(%s),0) AS cout,
                   sum(refuse::int) AS refus
            FROM api_appel
            GROUP BY agent ORDER BY cout DESC
        """ % COUT)
        par_agent = [{
            "agent": r[0] or "?", "nb": r[1], "entree": r[2],
            "sortie": r[3], "cout": r[4], "refus": r[5],
        } for r in request.env.cr.fetchall()]
        request.env.cr.execute("""
            SELECT count(*), coalesce(sum(tokens_entree),0),
                   coalesce(sum(tokens_sortie),0), coalesce(sum(%s),0)
            FROM api_appel
        """ % COUT)
        totals = request.env.cr.fetchone()
        # Solde DeepSeek RÉEL (API) vs consommé ESTIMÉ (01/08) : l'estimation
        # interne mentait (tarif Opus sur DeepSeek) — on la confronte au réel.
        solde = request.env["deepseek.solde"].sudo()._comparatif() \
            if "deepseek.solde" in request.env else False
        # Consommation du copilote PAR UTILISATEUR (le vrai consommateur).
        par_user = []
        if "copilote.usage" in request.env:
            Usage = request.env["copilote.usage"].sudo()
            request.env.cr.execute("""
                SELECT u.login, count(*),
                       coalesce(sum(c.tokens_entree),0),
                       coalesce(sum(c.tokens_sortie),0),
                       coalesce(sum(c.cout_estime),0)
                FROM copilote_usage c
                LEFT JOIN res_users u ON u.id = c.user_id
                GROUP BY u.login ORDER BY 5 DESC
            """)
            par_user = [{
                "login": r[0] or "?", "nb": r[1], "entree": r[2],
                "sortie": r[3], "cout": round(r[4] or 0, 2),
            } for r in request.env.cr.fetchall()]

        # --- LA CARTE (10/08, Merline) ------------------------------------
        # Trois périodes servies d'un coup : la page bascule sans recharger.
        aujourdhui = date_cls.today()
        carte = {
            "coeur": {"nom": "Clé DeepSeek",
                      "modele": "deepseek-chat · deepseek-reasoner"},
            "periodes": {
                "24h": self._periode(aujourdhui, par_heure=True),
                "7j": self._periode(aujourdhui - timedelta(days=6)),
                "30j": self._periode(aujourdhui - timedelta(days=29)),
            },
            "missions": self._top_missions(
                aujourdhui - timedelta(days=6)),
        }
        carte_json = Markup(json.dumps(
            carte, ensure_ascii=False).replace("<", "\\u003c")
            .replace(">", "\\u003e"))

        return request.render("tour_appels.page_appels", {
            "appels": appels,
            "par_agent": par_agent,
            "totals": totals,
            "solde": solde,
            "par_user": par_user,
            "carte_json": carte_json,
            "missions_top": carte["missions"],
            "serie_24h": carte["periodes"]["24h"]["serie"],
        })

    @http.route("/tour/ma-consommation", type="http", auth="user",
                website=False)
    def ma_consommation(self, **kw):
        """Chacun suit SA consommation : appels copilote + coût estimé,
        sur son propre compte. Pas besoin d'être admin — ce sont SES données
        (règle : un invité ne voit que ses propres données)."""
        user = request.env.user
        Usage = request.env["copilote.usage"].sudo()
        # relevés : aujourd'hui / 7 jours / 30 jours
        def stats(depuis=None):
            domain = [("user_id", "=", user.id)]
            if depuis:
                domain.append(("jour", ">=", depuis))
            rows = Usage.search(domain)
            return {"nb": len(rows),
                    "cout": round(sum(rows.mapped("cout_estime") or [0]), 2),
                    "tokens": sum(rows.mapped("tokens_entree") or [0])}
        from odoo import fields as f
        jours = {"aujourdhui": stats(f.Date.today()),
                 "7j": stats(f.Date.today() - f.timedelta(days=6)),
                 "30j": stats(f.Date.today() - f.timedelta(days=29))}
        quota = Usage._quota_du_jour(user)
        consomme_jour = jours["aujourdhui"]["nb"]
        return request.render("tour_appels.ma_consommation", {
            "user": user,
            "jours": jours,
            "quota": quota,
            "reste": max(0, quota - consomme_jour) if quota > 0 else None,
        })
