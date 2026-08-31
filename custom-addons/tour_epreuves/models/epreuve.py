# -*- coding: utf-8 -*-
"""Les épreuves : savoir qu'un agent a régressé, avant qu'il ne serve.

Le besoin, dit par Patrick le 28/07 : « on doit pouvoir tester nos agents
lorsqu'ils évoluent ou lorsqu'ils s'entraînent, et de manière automatique, pour
être sûr que rien n'a régressé ».

Le problème est réel et il est particulier aux agents. Un module qui casse
lève une erreur ; **un agent qui régresse répond quand même** — juste moins
bien, ou à côté. La panne est silencieuse et polie. On ne s'en aperçoit qu'en
relisant, c'est-à-dire jamais.

TROIS PRINCIPES

**On teste la CAPACITÉ, pas la formulation.** Demander qu'une réponse soit
identique mot pour mot condamne l'épreuve à échouer dès la première évolution.
On vérifie qu'un mot attendu est là, qu'un mot interdit ne l'est pas, et que la
réponse n'est pas vide. Une épreuve trop stricte finit désactivée.

**Une épreuve naît d'une panne réelle, jamais d'une imagination.** Les premières
sont écrites d'après ce qui a vraiment cassé : Lois rendue muette, Chloe qui
improvise faute d'outil, Braignak qui échoue sans le dire.

**Elle ne parle que sur une RÉGRESSION** — une épreuve qui passait et qui ne
passe plus. Une alerte qui crie tout le temps n'est plus une alerte : c'est la
même règle que pour Jimmy.
"""

import logging
import re

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class AgentEpreuve(models.Model):
    _name = "agent.epreuve"
    _description = "Épreuve d'un agent"
    _order = "membre_id, sequence, id"

    name = fields.Char("Ce qu'on vérifie", required=True)
    membre_id = fields.Many2one("equipe.membre", "Agent", required=True,
                                ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean("Active", default=True)

    genre = fields.Selection(
        [("outil", "Il a l'outil qu'il faut"),
         ("perimetre", "Son périmètre est écrit"),
         ("moteur", "Son moteur répond"),
         ("controle", "Son contrôle rend le bon verdict"),
         ("trace", "Il laisse une trace de ce qu'il fait")],
        "Nature", required=True, default="outil",
        help="Ce qu'on met à l'épreuve. On teste une CAPACITÉ, pas une "
             "formulation : une épreuve trop stricte finit désactivée.")

    cible = fields.Char(
        "Sur quoi", help="Nom d'outil, de moteur, de modèle ou de méthode, "
                         "selon la nature de l'épreuve.")
    attendu = fields.Char("Doit contenir")
    interdit = fields.Char("Ne doit pas contenir")

    dernier_etat = fields.Selection(
        [("ok", "Passe"), ("ko", "Échoue"), ("inconnu", "Jamais passée")],
        "Dernier résultat", default="inconnu", readonly=True)
    dernier_detail = fields.Char("Ce qui s'est passé", readonly=True)
    passe_le = fields.Datetime("Dernier passage", readonly=True)

    # ------------------------------------------------------------------
    def _executer(self):
        """Rend (ok, detail). Ne lève jamais : une épreuve qui plante est une
        épreuve qui échoue, pas un cron qui s'éteint."""
        self.ensure_one()
        try:
            methode = getattr(self, "_e_%s" % self.genre, None)
            if not methode:
                return False, _("Nature d'épreuve inconnue : %s") % self.genre
            return methode()
        except Exception as exc:  # noqa: BLE001
            return False, _("L'épreuve a planté : %s") % str(exc)[:150]

    def _e_outil(self):
        """L'agent a-t-il l'outil nommé ? C'est la panne de Chloe le 27/07 :
        sans outil, un assistant n'annonce pas son manque, il improvise."""
        from odoo.addons.tour_copilote.controllers import main as copilote
        noms = {o["name"] for o in (copilote.TOOLS + copilote.CLARK_TOOLS)}
        present = (self.cible or "") in noms
        return present, (_("outil « %s » présent") % self.cible if present
                         else _("outil « %s » ABSENT — il improvisera") % self.cible)

    def _e_perimetre(self):
        """Son périmètre et ses refus sont-ils écrits ? Règle 1 du socle."""
        m = self.membre_id
        manque = []
        if not (m.perimetre or "").strip():
            manque.append(_("son périmètre"))
        if not (m.refus or "").strip():
            manque.append(_("ce qu'il ne fait pas"))
        if manque:
            return False, _("Non écrit : %s") % ", ".join(manque)
        return True, _("périmètre et refus écrits")

    def _e_moteur(self):
        """Son moteur existe-t-il vraiment sur le serveur ?

        On vérifie la PRÉSENCE, pas la réponse : lancer le moteur à chaque
        épreuve consommerait des jetons à chaque passage, tous les jours, pour
        vérifier une chose que la santé des agents surveille déjà.
        """
        import os
        nom = self.cible or self.membre_id.moteur
        if not nom:
            return True, _("agent sans moteur (aucune IA) — rien à vérifier")
        chemin = "/mnt/atelier/moteurs/%s.sh" % nom
        existe = os.path.isfile(chemin)
        return existe, (_("moteur « %s » installé") % nom if existe
                        else _("moteur « %s » INTROUVABLE — il échouera") % nom)

    def _e_controle(self):
        """Un contrôle déterministe rend-il un verdict lisible ?

        On l'appelle deux fois : un contrôle qui ne rend pas le même verdict
        deux fois de suite n'est pas un contrôle, et c'est précisément ce qu'on
        promet de Victor et d'Emil.
        """
        # On coupe au DERNIER point : un nom de modele en contient
        # deja un (securite.agent), donc couper au premier donnait
        # modele=securite et methode=agent._c_... Ma propre epreuve a
        # attrape le defaut au premier passage — c est ce qu on lui
        # demande.
        cible = (self.cible or "").strip()
        modele, methode = cible.rsplit(".", 1) if "." in cible else (cible, None)
        if not methode or modele not in self.env:
            return False, _("cible illisible : « %s »") % self.cible
        obj = self.env[modele].sudo()
        fn = getattr(obj, methode, None)
        if not fn:
            return False, _("méthode « %s » absente") % methode
        r1 = fn()
        r2 = fn()
        if r1 != r2:
            return False, _("verdict différent d'un appel à l'autre — "
                            "ce n'est pas un contrôle")
        return True, _("verdict stable : %s") % str(r1)[:60]

    def _e_trace(self):
        """L'agent laisse-t-il une trace de ce qu'il fait ? Règle 2 du socle."""
        modele = self.cible or ""
        if modele not in self.env:
            return False, _("modèle « %s » absent") % modele
        champs = self.env[modele]._fields
        trace = "message_ids" in champs or "create_date" in champs
        return trace, (_("laisse une trace datée") if trace
                       else _("AUCUNE trace — ingérable"))


class AgentPassage(models.Model):
    """Une session d'épreuves. C'est elle qui permet de voir une régression :
    sans historique, on ne sait pas si ça passait hier."""

    _name = "agent.passage"
    _description = "Passage des épreuves"
    _order = "date desc, id desc"

    date = fields.Datetime("Quand", default=fields.Datetime.now, required=True)
    total = fields.Integer("Épreuves", readonly=True)
    reussies = fields.Integer("Passent", readonly=True)
    echouees = fields.Integer("Échouent", readonly=True)
    regressions = fields.Text("Régressions", readonly=True,
                              help="Ce qui passait avant et ne passe plus. "
                                   "C'est la seule chose qui déclenche une alerte.")

    @api.model
    def _cron_eprouver(self):
        """Passe toutes les épreuves. Ne prévient que sur une RÉGRESSION."""
        Epreuve = self.env["agent.epreuve"].sudo()
        epreuves = Epreuve.search([("active", "=", True)])
        regressions, ok, ko = [], 0, 0
        for e in epreuves:
            avant = e.dernier_etat
            reussi, detail = e._executer()
            e.write({"dernier_etat": "ok" if reussi else "ko",
                     "dernier_detail": (detail or "")[:250],
                     "passe_le": fields.Datetime.now()})
            if reussi:
                ok += 1
            else:
                ko += 1
                # Une régression, c'est ce qui PASSAIT et ne passe plus. Un
                # échec qui dure n'est pas une nouvelle : c'est un chantier
                # connu, et le répéter chaque jour apprend à ignorer l'alerte.
                if avant == "ok":
                    regressions.append("%s — %s : %s"
                                       % (e.membre_id.name, e.name, detail))
        passage = self.create({
            "total": len(epreuves), "reussies": ok, "echouees": ko,
            "regressions": "\n".join(regressions) or False,
        })
        if regressions and "tour.signal" in self.env:
            corps = "<p>Ce qui passait hier et ne passe plus :</p><ul>%s</ul>" % (
                "".join("<li>%s</li>" % r for r in regressions))
            self.env["tour.signal"]._signaler(
                agent="Les épreuves",
                titre=_("%s régression(s) dans l'équipe") % len(regressions),
                corps_html=corps, ton="echec")
        _logger.info("Epreuves : %s passent, %s echouent, %s regression(s)",
                     ok, ko, len(regressions))
        return passage
