# -*- coding: utf-8 -*-
"""Voir et récupérer les sauvegardes depuis la tour.

Le dossier des sauvegardes est monté en LECTURE SEULE dans le conteneur : la
tour peut lister et servir les fichiers, jamais les modifier ni les effacer.
Le script de sauvegarde reste seul maître du dossier — une application qui
peut supprimer ses propres sauvegardes n'en a pas.

Réservé aux administrateurs : ces fichiers contiennent la totalité des données
et, pour la copie du .env, la totalité des secrets.
"""
import logging
import os
from datetime import datetime

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class TourSauvegarde(models.Model):
    _name = "tour.sauvegarde"

    def _dossier(self):
        """Dossier des sauvegardes. Parametrable (sauvegardes.dossier) ;
        par defaut, un dossier local du module (edition Community)."""
        import os
        return self.env["ir.config_parameter"].sudo().get_param(
            "sauvegardes.dossier",
            os.path.join(os.path.dirname(os.path.dirname(__file__)),
                         "sauvegardes"))
    _description = "Sauvegarde disponible"
    _order = "date desc, name"

    name = fields.Char("Fichier", required=True, readonly=True)
    type_fichier = fields.Selection(
        [("base", "Base de données"), ("filestore", "Pièces jointes"),
         ("secrets", "Secrets (.env)"), ("depots", "Dépôts (git)"),
         ("tout", "Tout-en-un (tout le serveur)"), ("autre", "Autre")],
        string="Contenu", readonly=True)
    base_concernee = fields.Char("Base", readonly=True)
    # Taille en Ko (Integer Odoo, plafond ~2 Gio) : les archives chiffrées
    # dépassent 2 Gio et un Integer en octets débordait (NumericValueOutOfRange).
    taille_ko = fields.Integer("Taille (Ko)", readonly=True)
    taille_lisible = fields.Char("Taille", compute="_compute_taille_lisible")
    date = fields.Datetime("Date", readonly=True)
    presente = fields.Boolean("Toujours présente", default=True, readonly=True)

    def _compute_taille_lisible(self):
        # La vraie taille est relue depuis le disque quand le fichier est la :
        # `taille_ko` est un Integer tronque a l unite, et un .env de 209 o
        # serait affiche « 0 Ko » alors qu il n est pas vide. On prefere le
        # valeur reelle (octets) quand on peut la lire, sinon on retombe sur
        # le stocke.
        for rec in self:
            # La vraie taille est relue depuis le disque quand on la connait ;
            # sinon on retombe sur `taille_ko` (Integer, donc arrondi).
            o = 0.0
            if rec.presente and rec.name and not rec.name.startswith("/"):
                try:
                    o = float(os.path.getsize(os.path.join(self._dossier(), rec.name)))
                except OSError:
                    o = float(rec.taille_ko or 0) * 1024.0
            else:
                o = float(rec.taille_ko or 0) * 1024.0
            for unite in ("o", "Ko", "Mo", "Go", "To"):
                if o < 1024:
                    rec.taille_lisible = "%.0f %s" % (o, unite)
                    break
                o /= 1024.0

    # ------------------------------------------------------------------
    # Les fichiers auxiliaires SQLite (-shm / -wal) naissent a cote du
    # snapshot .sqlite quand better-sqlite3 le copie (db.backup). Ce ne sont
    # pas des sauvegardes : on ne les liste pas de peur qu'un « 0 Ko » passe
    # pour un snapshot vide aux yeux de quelqu'un qui scanne la liste.
    FINAUX_SQLITE = (".sqlite-shm", ".sqlite-wal")

    @api.model
    def _classer(self, nom):
        if nom.startswith("tout-"):
            return "tout", False
        if nom.startswith("filestore-"):
            return "filestore", False
        if nom.startswith("env-"):
            return "secrets", False
        if nom.startswith("repos-"):
            return "depots", False
        if nom.endswith(".dump"):
            return "base", nom.rsplit("-", 2)[0]
        return "autre", False

    @api.model
    def action_scanner(self):
        """Aligne la liste sur ce qui existe réellement sur le disque."""
        if not self.env.user.has_group("base.group_system"):
            raise UserError(_("Réservé aux administrateurs."))
        if not os.path.isdir(self._dossier()):
            raise UserError(_(
                "Le dossier des sauvegardes n'est pas visible depuis "
                "l'application (%s). Vérifier que le montage en lecture seule "
                "est bien déclaré dans la configuration de déploiement.", self._dossier()))

        connus = {s.name: s for s in self.sudo().search([])}
        vus = set()
        for nom in sorted(os.listdir(self._dossier())):
            if nom.endswith(self.FINAUX_SQLITE):
                continue
            chemin = os.path.join(self._dossier(), nom)
            if not os.path.isfile(chemin):
                continue
            vus.add(nom)
            st = os.stat(chemin)
            type_f, base = self._classer(nom)
            vals = {
                "name": nom,
                "type_fichier": type_f,
                "base_concernee": base,
                # st_size // 1024 : pour un fichier de 209 o, la division
                # entiere donne 0 — une sauvegarde NON vide s afficherait
                # « 0 Ko » et serait prise pour un fichier vide. Un fichier
                # present de moins de 1 Ko compte donc pour 1. (Patrick, 07/08)
                "taille_ko": max(1, st.st_size // 1024),
                "date": datetime.utcfromtimestamp(st.st_mtime),
                "presente": True,
            }
            if nom in connus:
                connus[nom].sudo().write(vals)
            else:
                self.sudo().create(vals)

        # Ce qui a été purgé par la rétention : on le marque plutôt que de
        # l'effacer, pour garder la trace de ce qui a existé.
        for nom, rec in connus.items():
            if nom not in vus and rec.presente:
                rec.sudo().presente = False
        return True

    def action_telecharger(self):
        self.ensure_one()
        if not self.presente:
            raise UserError(_(
                "Ce fichier a été purgé par la rétention (15 jours) et n'est "
                "plus sur le serveur."))
        return {
            "type": "ir.actions.act_url",
            "url": "/tour/sauvegarde/%s" % self.id,
            "target": "self",
        }

    @api.model
    def _cron_scanner(self):
        """Le scan, en version tolérante : une tâche planifiée ne doit pas
        remplir le journal d'erreurs parce qu'un dossier manque."""
        try:
            self.sudo().action_scanner()
        except Exception as exc:  # noqa: BLE001
            _logger.info("Sauvegardes : scan impossible (%s)", exc)
        return True

    # ==================================================================
    # Surveillance
    #
    # Deux pannes silencieuses, et ce sont les deux qui coûtent le plus cher :
    # une sauvegarde qui échoue sans que personne ne le sache, et un disque
    # qui se remplit. Le disque plein arrête PostgreSQL — c'est la panne
    # numéro un d'un petit serveur, et elle arrive toujours un dimanche.
    #
    # Aucun outil supplémentaire : la tour voit déjà le dossier et sait déjà
    # envoyer des courriels. Ajouter une pile de supervision pour surveiller
    # une seule machine coûterait plus que ce que ça rapporte.
    # ==================================================================
    SEUIL_DISQUE = 15          # % d'espace libre en dessous duquel on alerte
    AGE_MAX_HEURES = 30        # une sauvegarde quotidienne + 6 h de marge

    @api.model
    def _reglage(self, cle, defaut):
        """Un seuil réglable sans toucher au code.

        Deux raisons : un serveur plus gros n'a pas les mêmes seuils qu'un
        petit, et surtout on peut PROVOQUER l'alerte pour vérifier qu'elle
        part vraiment. Une alerte qu'on n'a jamais vue partir n'existe pas.
        """
        valeur = self.env["ir.config_parameter"].sudo().get_param(
            "tour_sauvegardes.%s" % cle)
        # get_param renvoie False quand le parametre n'existe pas, et
        # int(False) vaut 0 SANS lever d'erreur. Sans ce garde-fou, un seuil
        # absent devient un seuil de zero : l'alerte se declenche en
        # permanence, on cesse de la lire, et le jour ou elle est vraie on ne
        # la voit pas. Bug reel, trouve en provoquant l'alerte.
        if not valeur:
            return defaut
        try:
            return int(valeur)
        except (TypeError, ValueError):
            return defaut

    @api.model
    def _destinataire_alerte(self):
        icp = self.env["ir.config_parameter"].sudo()
        adresse = (icp.get_param("tour_sauvegardes.alerte_email") or "").strip()
        if adresse:
            return adresse
        admin = self.env.ref("base.user_admin", raise_if_not_found=False)
        if admin and admin.email:
            return admin.email
        return (self.env.company.email or "").strip()

    @api.model
    def _diagnostic(self):
        """Ce qui ne va pas, en clair. Liste vide = tout va bien."""
        soucis = []

        if not os.path.isdir(self._dossier()):
            return [_("Le dossier des sauvegardes (%s) n'est pas visible "
                      "depuis l'application. La surveillance ne peut rien "
                      "vérifier du tout.", self._dossier())]

        # 1. Le témoin écrit par le script à chaque exécution.
        temoin = os.path.join(self._dossier(), "dernier-etat.txt")
        if not os.path.exists(temoin):
            soucis.append(_(
                "Aucun témoin d'état. Soit la sauvegarde n'a jamais tourné "
                "depuis la mise en place de la surveillance, soit le script "
                "installé sur le serveur est une version antérieure."))
        else:
            try:
                with open(temoin, encoding="utf-8", errors="replace") as f:
                    ligne = (f.read() or "").strip()
                morceaux = ligne.split("|")
                statut = morceaux[0] if morceaux else "?"
                quand = morceaux[1] if len(morceaux) > 1 else "?"
                detail = morceaux[3] if len(morceaux) > 3 else ""
                if statut != "OK":
                    soucis.append(_(
                        "La dernière sauvegarde a ÉCHOUÉ (%(q)s) : %(d)s",
                        q=quand, d=detail or _("raison non précisée")))
                age = (datetime.utcnow()
                       - datetime.utcfromtimestamp(os.path.getmtime(temoin)))
                heures = age.total_seconds() / 3600
                if heures > self._reglage("age_max_heures", self.AGE_MAX_HEURES):
                    soucis.append(_(
                        "Aucune sauvegarde depuis %(h)s heures. La tâche "
                        "planifiée de 3 h ne tourne peut-être plus.",
                        h=int(heures)))
            except OSError as exc:
                soucis.append(_("Témoin d'état illisible : %s", exc))

        # 2. L'espace disque.
        try:
            st = os.statvfs(self._dossier())
            libre = st.f_bavail * st.f_frsize
            total = st.f_blocks * st.f_frsize
            pourcent = (libre * 100.0 / total) if total else 0
            if pourcent < self._reglage("seuil_disque", self.SEUIL_DISQUE):
                soucis.append(_(
                    "Disque à %(p).1f %% d'espace libre (%(g).1f Go sur "
                    "%(t).1f Go). Sous ce seuil, la base de données peut "
                    "s'arrêter d'écrire.",
                    p=pourcent, g=libre / 1e9, t=total / 1e9))
        except OSError as exc:
            soucis.append(_("Espace disque non mesurable : %s", exc))

        return soucis

    @api.model
    def _cron_surveiller(self):
        """Alerte s'il y a un problème. Ne dit rien quand tout va bien.

        Une alerte quotidienne « tout va bien » finit dans un dossier ignoré,
        et le jour où elle manque personne ne le remarque. On n'écrit que
        lorsqu'il y a quelque chose à faire.
        """
        soucis = self._diagnostic()
        icp = self.env["ir.config_parameter"].sudo()
        empreinte = " / ".join(soucis)

        if not soucis:
            icp.set_param("tour_sauvegardes.dernier_souci", "")
            return True

        # Ne pas répéter la même alerte tous les jours : on ré-alerte quand le
        # problème CHANGE, ou une fois par semaine s'il persiste.
        precedent = icp.get_param("tour_sauvegardes.dernier_souci") or ""
        depuis = icp.get_param("tour_sauvegardes.dernier_envoi") or ""
        if empreinte == precedent and depuis:
            try:
                if (datetime.utcnow()
                        - datetime.fromisoformat(depuis)).days < 7:
                    return True
            except ValueError:
                pass

        destinataire = self._destinataire_alerte()
        if not destinataire:
            _logger.warning("Sauvegardes : probleme detecte mais aucune "
                            "adresse d'alerte configuree (%s)", empreinte)
            return False

        corps = "<p>La surveillance de la tour a détecté un problème :</p><ul>"
        corps += "".join("<li>%s</li>" % s for s in soucis)
        corps += ("</ul><p>Tant que ce n'est pas réglé, considérez que vous "
                  "<b>n'avez pas de sauvegarde utilisable</b>. Le détail des "
                  "exécutions est dans <code>~/logs/backup.log</code> sur le "
                  "serveur.</p>")

        self.env["mail.mail"].sudo().create({
            "subject": "[Tour de contrôle] Sauvegarde ou disque : %s problème(s)"
                       % len(soucis),
            "email_to": destinataire,
            "body_html": corps,
            "auto_delete": False,
        }).send()

        icp.set_param("tour_sauvegardes.dernier_souci", empreinte)
        icp.set_param("tour_sauvegardes.dernier_envoi",
                      datetime.utcnow().isoformat())
        _logger.warning("Sauvegardes : alerte envoyee a %s (%s)",
                        destinataire, empreinte)
        return True
