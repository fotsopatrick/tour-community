# -*- coding: utf-8 -*-
"""Page de gestion du menu Actions — réservée à l'admin.

À l'accueil (menu Actions), on coche pour chaque item s'il est visible en
PROD et/ou en DEMO, sans passer par le backend Odoo. C'est la même donnée que
`tour.actions.config`, accessible ici depuis la tour.

Privé : `auth="user"`. La modification passe par `est_admin` (groupe
base.group_system) — seuls les admins peuvent changer la visibilité. Les
comptes ordinaires sont redirigés vers l'accueil.
"""
from odoo import http
from odoo.http import request


class TourActionsConfigWeb(http.Controller):

    def _defaut_env(self):
        """L'environnement courant : 'prod' (base tour) ou 'demo' (autre)."""
        return "prod" if (request.env.cr.dbname or "") == "tour" else "demo"

    @http.route("/tour/actions-config", type="http", auth="user",
                website=False, csrf=False)
    def actions_config(self, **kw):
        env = request.env
        user = env.user
        if not user.has_group("base.group_system"):
            return request.redirect("/tour/dashboard")

        items = env["tour.actions.config"].sudo().search(
            [], order="sequence, name")
        # On construit le HTML des lignes en Python : fiable quel que soit le
        # moteur QWeb (le même pattern que le dashboard pour le groupement).
        groupes = {}
        for it in items:
            groupes.setdefault(it.groupe or "Autre", []).append(it)
        def echape(s):
            return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;"))
        blocs = []
        Modele = env["tour.actions.config"]
        for g, liste in groupes.items():
            lignes = []
            for it in liste:
                possible = Modele._invite_possible(it.url)
                lignes.append(
                    '<tr data-id="{id}"><td class="nom">{nom}</td>'
                    '<td class="encoche"><input type="checkbox" class="cb-prod"{p}/></td>'
                    '<td class="encoche"><input type="checkbox" class="cb-demo"{d}/></td>'
                    '<td class="encoche"><input type="checkbox" class="cb-invite"{i}{dis}/></td></tr>'.format(
                        id=it.id, nom=echape(it.name),
                        p=" checked" if it.prod else "",
                        d=" checked" if it.demo else "",
                        i=" checked" if (it.ouvrable_invite and possible) else "",
                        dis="" if possible else " disabled title=\"reserve aux webapps publiques\""))
            blocs.append(
                '<div class="carte"><div class="groupe-titre">{g}</div>'
                '<table><thead><tr><th class="nom">Item</th>'
                '<th class="colenr">PROD</th><th class="colenr">DEMO</th>'
                '<th class="colenr" title="Un invite peut voir cet item, '
                'si la case de l environnement est cochee elle aussi">'
                'INVITES</th></tr></thead>'
                '<tbody>{lignes}</tbody></table></div>'.format(
                    g=echape(g), lignes="".join(lignes)))
        return request.render("tour_actions.page_actions_config", {
            "blocs_html": "".join(blocs),
            "environnement": self._defaut_env(),
        })

    @http.route("/tour/actions-config/enregistrer", type="http", methods=["POST"],
                auth="user", csrf=False)
    def enregistrer(self, **kw):
        env = request.env
        user = env.user
        if not user.has_group("base.group_system"):
            return request.make_json_response({"ok": False, "erreur": "refus"})
        data = request.httprequest.get_json(silent=True) or {}
        updates = data.get("items") or []
        cfg = env["tour.actions.config"].sudo()
        for it in updates:
            rec = cfg.browse(int(it.get("id", 0)))
            if rec.exists():
                vals = {
                    "prod": bool(it.get("prod")),
                    "demo": bool(it.get("demo")),
                }
                # La case INVITES n'est autorisee que sur les webapps
                # publiques. Defense en profondeur : meme un POST forge a la
                # main ne peut pas ouvrir un item interne aux invites.
                if cfg._invite_possible(rec.url):
                    vals["ouvrable_invite"] = bool(it.get("ouvrable_invite"))
                else:
                    vals["ouvrable_invite"] = False
                rec.write(vals)
        return request.make_json_response({"ok": True})
