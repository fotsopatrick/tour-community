# -*- coding: utf-8 -*-
"""La page « Mes applications » : ce que la tour a construit pour vous.

Une application était publiée à une adresse, et rien dans la tour ne la
montrait. On l'apprenait par un courriel qu'on retrouvait trois jours plus tard,
ou pas du tout. Patrick l'a dit simplement : « les clients voient leurs apps
créées où ? »

La page liste ce qui est EN LIGNE et répond. Pas ce qui a été tenté : une
application dont l'adresse ne répond plus n'est pas une application, et
l'afficher comme telle ferait croire qu'on possède quelque chose qu'on n'a pas.
"""

from odoo import http
from odoo.http import request


class PageApps(http.Controller):

    @http.route("/tour/apps", type="http", auth="user", website=False)
    def apps(self, **kw):
        Mission = request.env["atelier.mission"].sudo()
        # CHACUN NE VOIT QUE SES APPLICATIONS. Trouvé par Patrick le 28/07 :
        # le sudo() sans filtre montrait TOUTES les apps publiées à tout
        # utilisateur connecté — un invité voyait celles du propriétaire.
        # L'erreur est passée parce que la page est née quand il était seul
        # utilisateur : chaque écran conçu pour une personne doit être relu
        # le jour où il y en a deux. L'administrateur, lui, voit tout.
        domaine = [("etat", "=", "terminee"), ("publier", "=", True),
                   ("url", "!=", False), ("nb_fichiers", ">", 0)]
        if not request.env.user.has_group("base.group_system"):
            domaine.append(("create_uid", "=", request.env.user.id))
        livrees = Mission.search(domaine, order="create_date desc")
        # PAS DE DOUBLONS PAR ADRESSE (corrigé le 31/07).
        #
        # Deux missions peuvent publier la MÊME adresse (ex : « Mon Sport »
        # relancée, ou une mission rejouée) : la page affichait deux cartes
        # pour la même application. Une application, c'est une adresse : on
        # ne garde que la plus récente pour chaque URL. On écarte aussi les
        # missions de test dont le nom le dit.
        vues, gardees = set(), request.env["atelier.mission"].sudo().browse()
        for m in livrees:
            cle = (m.url or "").rstrip("/")
            nom = (m.name or "").lower()
            if "test" in nom and "jetable" in nom:
                continue
            if cle in vues:
                continue
            vues.add(cle)
            gardees |= m
        livrees = gardees
        # LES ICONES (corrigé le 31/07) : chaque application affiche le
        # favicon de son site. On le cherche à la volée ; si introuvable,
        # une lettre dans une pastille fait l'icône — jamais un carré vide.
        icones = {}
        for m in livrees:
            base = (m.url or "").rstrip("/")
            icones[m.id] = "%s/favicon.ico" % base
        # La recette n'est visible que par l'administrateur : c'est le savoir-
        # faire de la maison, pas un mode d'emploi client.
        admin = request.env.user.has_group("base.group_system")
        recettes = {}
        if admin and "produit.modele" in request.env:
            for r in request.env["produit.modele"].sudo().search(
                    [("mission_id", "in", livrees.ids)]):
                recettes[r.mission_id.id] = r
        return request.render("tour_modeles.page_apps", {
            "apps": livrees,
            "icones": icones,
            "recettes": recettes,
            "admin": admin,
        })
