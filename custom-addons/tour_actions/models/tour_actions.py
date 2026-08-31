# -*- coding: utf-8 -*-
"""Configuration de la visibilité du menu « Actions » de l'accueil.

Chaque entrée correspond à un item du menu Actions du tableau de bord. Deux
drapeaux : visible en PROD et/ou en DEMO. Le template du dashboard lit ces
réglages pour savoir quels liens afficher à un compte donné au lieu de
conditions codées en dur.

Privé : on n'y accède que connecté à la tour (les vues sont groupées à
`base.group_user`, et le menu racine est réservé; les comptes portail n'y ont
pas droit).

06/08 — LE TROISIEME DRAPEAU, ET POURQUOI IL EST SEPARE DES DEUX AUTRES.

`prod` et `demo` disent OU un item s'affiche. Ils ne disent rien de QUI a le
droit de le voir. Tant que les items sensibles étaient cachés par le rôle
(`est_admin` / `est_owner`), la question ne se posait pas.

Ouvrir des items aux invités demande un drapeau de plus, `ouvrable_invite`,
et il ne peut pas être fondu dans les deux premiers : « je montre cet item sur
la démo » et « j'accepte qu'un invité voie cette page » sont deux décisions
différentes. Confondre les deux, c'est ouvrir le journal de Patrick le jour où
quelqu'un coche une case pour tester un affichage.

D'où la règle mécanique implémentée par `autorise()` :

    un invité voit l'item  <=>  ouvrable_invite ET la case de l'environnement

Les deux doivent être vraies. Une seule ne suffit jamais. Et `autorise()` est
appelée AUX DEUX BOUTS — par le template pour afficher le lien, par le
contrôleur de la page pour laisser entrer. Cacher un lien ne protège rien :
un invité qui tape l'adresse à la main arrive quand même sur la page. La seule
protection qui tienne est celle du serveur, et elle doit lire exactement la
même règle que l'affichage, sinon les deux divergent au premier changement.
"""
from odoo import api, fields, models


class TourActionsConfig(models.Model):
    _name = "tour.actions.config"
    _description = "Menu Actions — visibilité PROD/DEMO"
    _order = "sequence, name"
    _rec_name = "name"

    name = fields.Char(string="Item du menu Actions", required=True)
    groupe = fields.Char(string="Groupe", help="Groupe du menu (Piloter, Équipe, Moi & contenu…).")
    url = fields.Char(string="Adresse", help="Le lien / l'action ouverte par cet item.")
    sequence = fields.Integer(string="Ordre", default=10)
    prod = fields.Boolean(string="PROD", default=True, help="Visible sur la production.")
    demo = fields.Boolean(string="DEMO", default=True, help="Visible sur la démo.")
    ouvrable_invite = fields.Boolean(
        string="Invités ?", default=False,
        help="Un invité (compte sans droits d'administration) peut voir cet "
             "item, à condition que la case de l'environnement soit cochée "
             "elle aussi. Décoché = jamais visible par un invité, quelle que "
             "soit la case PROD/DEMO.")

    # ------------------------------------------------------------------
    # L'environnement courant
    # ------------------------------------------------------------------
    @api.model
    def _est_prod(self):
        """La prod est la base 'tour'. Toute autre base est traitée comme la
        démo : on ne présume JAMAIS la prod, sinon une base inconnue
        hériterait des droits les plus larges."""
        return self.env.cr.dbname == "tour"

    @api.model
    def reglages(self):
        """Renvoie la liste des items pour le template.

        `visible` vaut True si l'item est coché pour l'environnement courant
        (prod ou démo), autrement False.
        """
        est_prod = self._est_prod()
        result = []
        for it in self.search([], order="sequence, name"):
            result.append({
                "groupe": it.groupe,
                "name": it.name,
                "url": it.url or "",
                "visible": it.prod if est_prod else it.demo,
                "ouvrable_invite": it.ouvrable_invite,
                "invite_possible": self._invite_possible(it.url),
                "item_id": it.id,
            })
        return result

    # ------------------------------------------------------------------
    # LA règle d'autorisation — une seule, lue par tout le monde
    # ------------------------------------------------------------------
    @api.model
    def autorise(self, url, user=None):
        """Cet utilisateur a-t-il le droit d'ouvrir cette adresse ?

        Rend True/False. Appelée par le template (afficher le lien) ET par le
        contrôleur de la page (laisser entrer). Deux appels, une seule règle :
        c'est ce qui empêche l'affichage et la protection de diverger.

        - un admin ou le propriétaire passe toujours ;
        - un invité passe si, ET SEULEMENT SI, l'item est ouvrable aux invités
          et coché pour l'environnement courant ;
        - une adresse inconnue de la table ne passe pas pour un invité. Un
          item qu'on a oublié de déclarer doit rester fermé, jamais s'ouvrir
          par défaut — le défaut se paie du mauvais côté.
        """
        user = user or self.env.user
        if user.has_group("base.group_system"):
            return True
        if self._est_proprietaire(user):
            return True

        item = self.sudo().search([("url", "=", url)], limit=1)
        if not item:
            return False
        if not item.ouvrable_invite:
            return False
        return item.prod if self._est_prod() else item.demo

    @api.model
    def _est_proprietaire(self, user):
        """Le propriétaire de la tour.

        On lit le MEME paramètre que le tableau de bord
        (`tour_owner.identifiants`, hors git) — une seule source de vérité,
        deux listes de propriétaires finissant toujours par se contredire.

        Mais on le lit avec `self.env`, pas via le `_owner_ids()` du
        contrôleur : celui-là passe par `request.env`, donc il n'existe que
        pendant une requête web. Le retest du 06/08 l'a montré en appelant
        `autorise()` depuis un shell — « object is not bound ». Une règle
        d'autorisation qu'on ne peut jouer que dans un navigateur est une
        règle qu'on ne peut pas tester.
        """
        val = self.env["ir.config_parameter"].sudo().get_param(
            "tour_owner.identifiants", "") or ""
        proprietaires = {x.strip().lower() for x in val.split(",") if x.strip()}
        return (user.login or "").lower() in proprietaires

    @api.model
    def urls_autorisees(self, user=None):
        """L'ensemble des adresses que cet utilisateur peut ouvrir.

        Le template en a besoin d'un coup : appeler `autorise()` quarante fois
        ferait quarante recherches pour rendre une page.
        """
        user = user or self.env.user
        if user.has_group("base.group_system") or self._est_proprietaire(user):
            return set(self.sudo().search([]).mapped("url")) - {False, ""}
        est_prod = self._est_prod()
        ok = set()
        for it in self.sudo().search([("ouvrable_invite", "=", True)]):
            if (it.prod if est_prod else it.demo) and it.url:
                ok.add(it.url)
        return ok

    # Une webapp reellement accessible aux invites ? Les pages internes Odoo
    # et les pages protegees (ssh, /sites/*) ne peuvent PAS s'ouvrir aux
    # invites : la case INVITES n'a de sens que sur des adresses publiques.
    PREFIXES_OUVRABLES_INVITES = (
        "https://matourdecontrole.fr/",
        "https://duelle.matourdecontrole.fr",
        "/zone-detresse/",
        "/tour/debats-public",
        "/tour/mon-ia",
    )

    @api.model
    def _invite_possible(self, url):
        return any((url or "").startswith(p)
                   for p in self.PREFIXES_OUVRABLES_INVITES)
