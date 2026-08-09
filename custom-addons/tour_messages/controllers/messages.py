# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request



def _acces_invite(url, secours):
    """Cet utilisateur peut-il ouvrir `url` ?

    La reponse vient de tour.actions.config : le drapeau « Invites ? » ET la
    case de l'environnement. Meme regle que celle qui decide d'afficher le
    lien dans le menu Actions. Si le module de config n'est pas installe, on
    rend `secours` — le garde d'origine.
    """
    env = request.env
    if "tour.actions.config" in env:
        return env["tour.actions.config"].sudo().autorise(url)
    return secours()

class PageMessages(http.Controller):

    @http.route("/tour/messages", type="http", auth="user", website=False)
    def messages(self, **kw):
        # La bibliothèque de messages appartient au propriétaire : admin seul.
        # (01/08, audit des pages : un interne non-admin ne doit pas y voir les
        # messages préparés pour les clients et les invités.)
        if not _acces_invite("/tour/messages", lambda: request.env.user.has_group("base.group_system")):
            return request.redirect("/community")
        Message = request.env["tour.message"]
        libelles = dict(Message._fields["categorie"].selection)
        # Filtre par catégorie, pas par date (demande Patrick, 03/08).
        cat = kw.get("categorie", "")
        cherche = (kw.get("q") or "").strip()

        # LE COMPTE PAR CATEGORIE, CALCULE SUR TOUT, PAS SUR CE QU ON AFFICHE.
        #
        # Payé le 05/08 : 61 messages sur 89 dormaient dans « Autre ». Les
        # filtres se ressemblaient tous, donc on cliquait au hasard et on
        # réécrivait le message qu'on avait déjà — exactement ce que ce module
        # devait éviter. Un filtre qui dit son nombre se choisit d'un coup
        # d'oeil ; un filtre vide n'a rien à faire à l'écran.
        compte_par_cat = {}
        for grp in Message.read_group([], ["categorie"], ["categorie"]):
            compte_par_cat[grp["categorie"]] = grp["categorie_count"]

        domaine = []
        if cat in libelles:
            domaine.append(("categorie", "=", cat))
        if cherche:
            # On cherche dans le titre, le texte et le « pour qui » : c'est
            # rarement le titre exact dont on se souvient.
            domaine += ["|", "|", ("name", "ilike", cherche),
                        ("corps", "ilike", cherche), ("pour_qui", "ilike", cherche)]

        # Dernier message ajouté en premier.
        msgs = Message.search(domaine, order="id desc")
        # Regroupés par catégorie, dans l'ordre du modèle.
        groupes = {}
        for m in msgs:
            groupes.setdefault(m.categorie, []).append(m)
        ordre = [c for c in libelles if c in groupes]
        # Un filtre par catégorie NON VIDE, avec son nombre.
        filtres = [(c, libelles[c], c == cat, compte_par_cat.get(c, 0))
                   for c in libelles if compte_par_cat.get(c, 0)]
        return request.render("tour_messages.page_messages", {
            "groupes": [(libelles[c], groupes[c]) for c in ordre],
            "total": len(msgs),
            "tout": sum(compte_par_cat.values()),
            "filtres": filtres,
            "categorie": cat,
            "cherche": cherche,
        })

    @http.route("/tour/messages/<int:mid>/traite", type="http", auth="user",
                methods=["POST"], csrf=True)
    def traite(self, mid, **kw):
        """Marquer traite depuis la page, puis revenir a la liste.

        En POST et non en GET : une action qui MODIFIE ne doit jamais tenir
        dans un lien. Un lien se preouvre, se partage, se recharge — et le
        message se retrouverait archive sans que personne ait clique.
        """
        msg = request.env["tour.message"].browse(int(mid))
        if msg.exists():
            msg.action_traite()
        return request.redirect("/tour/messages")

    @http.route("/tour/messages/archives", type="http", auth="user", website=False)
    def archives(self, **kw):
        """Les messages traites. Archives, pas supprimes : un message envoye
        une fois resservira, et on veut relire ce qu on avait dit."""
        if not request.env.user.has_group("base.group_system"):
            return request.redirect("/community")
        msgs = request.env["tour.message"].with_context(active_test=False).search(
            [("traite", "=", True)], order="traite_le desc")
        return request.render("tour_messages.page_archives", {"msgs": msgs})
