# -*- coding: utf-8 -*-
"""Comparer ce qui tourne en production, en démo et en test.

Trois copies d'un produit vivent en parallèle, et elles divergent forcément.
C'est justement la divergence qu'on ne voit jamais — jusqu'au jour où on teste
sur une base qui n'a pas le module dont on parle, ou où on montre une démo qui
n'a plus la fonctionnalité qu'on vend.

**Rien n'est saisi à la main.** La liste des modules est lue en direct dans
chaque base. Une liste tenue à la main ment dès la semaine suivante, et une
comparaison qui ment est pire que pas de comparaison : on lui fait confiance.

**Un environnement appartient à un projet.** La tour a les siens, un autre
produit aura les siens — la question « qu'est-ce qui diffère » ne se pose
qu'entre copies du MÊME produit.
"""

import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class TourEnvironnement(models.Model):
    _name = "tour.environnement"
    _description = "Un environnement d'un projet (prod, démo, test)"
    _order = "projet_id, sequence, id"

    name = fields.Char("Nom", required=True, help="Production, Démo, Test…")
    projet_id = fields.Many2one(
        "project.project", "Projet", required=True, index=True, ondelete="cascade",
        help="La comparaison n'a de sens qu'entre copies du même produit.")
    role = fields.Selection(
        [("prod", "Production — ce qui sert"),
         ("demo", "Démo — ce qu'on montre"),
         ("test", "Test — ce qu'on essaie")],
        "Rôle", required=True, default="test")
    base = fields.Char(
        "Base de données", required=True,
        help="Le nom exact de la base PostgreSQL. C'est là qu'on va lire.")
    url = fields.Char("Adresse")
    sequence = fields.Integer(default=10)
    actif = fields.Boolean("Suivi", default=True)

    # CE QU ON ATTEND DE CET ENVIRONNEMENT, et c est la vraie question.
    #
    # Patrick, le 28/07 : << tout ce qui est sur test est directement migre sur
    # prod ? je pense pas. on peut mettre sur test des produits non finis, donc
    # faut pas afficher diff prod et test aussi >>. Il a raison, et ca change
    # tout le sens de la page.
    #
    # Une difference n est pas une anomalie en soi. Elle l est pour la DEMO —
    # ce qu on montre doit exister pour de vrai — et elle est NORMALE pour la
    # test, dont le metier est justement de porter ce qui n est pas fini.
    #
    # Sans cette distinction, la page criait 55 anomalies dont la plupart
    # etaient saines : on apprend a l ignorer, et on rate la seule qui compte.
    attendu = fields.Selection(
        [("miroir", "Doit refléter la production"),
         ("avance", "Peut avoir de l'avance (essais en cours)"),
         ("libre", "Indépendant — ne pas comparer")],
        "Ce qu'on en attend", required=True, default="miroir",
        help="Une différence n'est une anomalie que si cet environnement est "
             "censé refléter la production. Une base de test a le droit "
             "d'avoir de l'avance : c'est son métier.")

    nb_modules = fields.Integer("Modules installés", readonly=True)
    releve_le = fields.Datetime("Dernière lecture", readonly=True)
    repond = fields.Boolean("Répond", readonly=True)

    def _modules_installes(self):
        """Les modules reellement installes sur CETTE base.

        On ouvre une connexion vers la base visee, avec le meme mecanisme
        qu Odoo utilise pour servir plusieurs bases sur un serveur. Pas besoin
        d extension PostgreSQL : la premiere version passait par dblink, qui
        n est pas installe — la demo ressortait a << 0 module >> et la page
        annoncait 125 differences la ou il n y en avait aucune.

        C etait exactement le defaut contre lequel j avais mis en garde deux
        paragraphes plus haut : une comparaison qui ment est pire que pas de
        comparaison, parce qu on lui fait confiance. Verifier vaut mieux
        qu ecrire la regle.

        Chaque lecture est isolee : une base eteinte ne doit pas empecher de
        comparer les autres.
        """
        self.ensure_one()
        if not self.base:
            return set()
        if self.base == self.env.cr.dbname:
            mods = self.env["ir.module.module"].sudo().search(
                [("state", "=", "installed")])
            return set(mods.mapped("name"))
        try:
            import odoo.sql_db
            connexion = odoo.sql_db.db_connect(self.base)
            with connexion.cursor() as cr:
                cr.execute("SELECT name FROM ir_module_module "
                           "WHERE state = %s", ("installed",))
                return {r[0] for r in cr.fetchall()}
        except Exception as exc:  # noqa: BLE001
            _logger.info("Environnements : base %s illisible (%s)", self.base, exc)
            return set()

    @api.model
    def comparer(self, projet_id=None):
        """Le tableau des differences, en NOMS LISIBLES.

        La premiere version affichait les noms techniques : l10n_fr_pos_cert,
        barcodes_gs1_nomenclature. Patrick a demande si la page << revele de
        facon claire >> ce qui manque — la reponse etait non. Un tableau qu il
        faut dechiffrer ne revele rien, il donne juste l impression d avoir
        repondu.

        On affiche donc le vrai nom du module, celui qu Odoo montre partout
        ailleurs, et on resume par environnement : combien il en manque, et
        lesquels.

        On ne montre QUE ce qui differe : lister les modules identiques
        noierait les lignes qui comptent.
        """
        domaine = [("actif", "=", True)]
        if projet_id:
            domaine.append(("projet_id", "=", int(projet_id)))
        envs = self.search(domaine)
        listes = {}
        for env_ in envs:
            mods = env_._modules_installes()
            listes[env_.id] = mods
            env_.write({"nb_modules": len(mods),
                        "releve_le": fields.Datetime.now(),
                        "repond": bool(mods)})
        tous = set()
        for m in listes.values():
            tous |= m

        # Le vrai nom de chaque module, lu une seule fois.
        Mod = self.env["ir.module.module"].sudo()
        noms = {m.name: (m.shortdesc or m.name)
                for m in Mod.search([("name", "in", list(tous))])}

        lignes, manques = [], {e.id: [] for e in envs}
        for cle in sorted(tous, key=lambda n: (noms.get(n) or n).lower()):
            presence = {e.id: (cle in listes.get(e.id, set())) for e in envs}
            if len(set(presence.values())) == 1:
                continue                      # present partout, ou absent partout
            lignes.append({"module": cle,
                           "nom": noms.get(cle, cle),
                           "presence": presence})
            for e in envs:
                if not presence[e.id]:
                    manques[e.id].append(noms.get(cle, cle))
        # On separe ce qui MANQUE (present en prod, absent ici) de ce qui est
        # EN AVANCE (present ici, absent en prod). Les deux n ont rien a voir :
        # l un est un trou, l autre est un essai en cours.
        prod = next((e for e in envs if e.role == "prod"), None)
        mods_prod = listes.get(prod.id, set()) if prod else set()
        avances, anomalies = {e.id: [] for e in envs}, {e.id: [] for e in envs}
        for e in envs:
            if not prod or e.id == prod.id:
                continue
            miens = listes.get(e.id, set())
            for cle in sorted(mods_prod - miens):
                if e.attendu == "miroir":
                    anomalies[e.id].append(noms.get(cle, cle))
            for cle in sorted(miens - mods_prod):
                avances[e.id].append(noms.get(cle, cle))
        return {"environnements": envs, "lignes": lignes,
                "manques": manques, "anomalies": anomalies, "avances": avances,
                "prod": prod,
                "identiques": len(tous) - len(lignes)}
