# -*- coding: utf-8 -*-
"""Guides et mémoire technique.

Deux besoins, un seul endroit : « comment on fait ça dans la tour » pour les
utilisateurs qui ne connaissent pas Odoo, et « qu'est-ce qui a été construit,
et pourquoi » pour répondre à un client des semaines plus tard sans se fier à
sa mémoire.

Tout est cherchable en plein texte : la recherche porte sur le titre, le
résumé, le contenu et les mots-clés.
"""
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# Le « Cahier de reproduction » décrit tout ce que la tour sait faire. Il ne
# vaut que s'il est à jour — un cahier qui décrit une tour d'il y a trois mois
# est pire qu'aucun cahier : il ment avec autorité. On le retrouve par ce
# mot-clé plutôt que par son identifiant, pour qu'il survive à un renommage.
CAHIER_MOT_CLE = "reproduction"

# Un brouillon d'article (catégorie « reseau_sociaux ») reste au stade de
# brouillon tant que son contenu est le texte de génération (« Brouillon
# généré … »). Ceux qui ne sont PAS enrichis par Patrick dans ce délai sont
# PURGÉS par le cron : un brouillon oublié qui s'accumule finit par mentir —
# des dizaines de « titres de travaux » jamais lus ne sont plus une veille,
# c'est du bruit. (Règle posée le 06/08 : purge auto avant publication.)
PURGE_BROUILLONS_JOURS = 3
PREFIXE_BROUILLON = "Brouillon généré"

CATEGORIES = [
    ("bienvenue", "Bienvenue — tutoriel tour"),
    ("astuce", "Astuce d'utilisation"),
    ("procedure", "Procédures pas à pas"),
    ("modules", "Modules de la tour"),
    ("concept", "Concepts de la tour"),
    ("architecture", "Architecture technique"),
    ("decision", "Décision et pourquoi"),
    ("piege", "Piège à ne pas refaire"),
    ("commercial", "Commercial et offres"),
    # ÉDUCATION : ce que Patrick apprend, et ce qu'il pourra montrer.
    #
    # Il l'a demandée le 27/07 (« dans la zone éducation de Patrick, décris
    # notre process ») et elle n'a jamais été créée : le guide sur le CI/CD
    # avait fini rangé dans « Astuce », avec les modes d'emploi. Une catégorie
    # qui n'existe pas, c'est du contenu qu'on ne retrouve pas — et ici il
    # s'agit de ce qui prépare une certification et un entretien.
    ("education", "Éducation — ce que j'apprends"),
    ("reseau_sociaux", "Réseaux sociaux — posts à publier"),
]


class TourGuide(models.Model):
    _name = "tour.guide"
    _description = "Guide / mémoire de la tour"
    _order = "create_date desc, id desc"

    name = fields.Char("Titre", required=True)
    categorie = fields.Selection(CATEGORIES, string="Type", required=True,
                                 default="astuce", index=True)
    resume = fields.Char("En une phrase",
                         help="Ce qu'on lit dans la liste avant d'ouvrir.")
    contenu = fields.Html("Contenu", sanitize=False)
    mots_cles = fields.Char(
        "Mots-clés",
        help="Termes qu'on taperait dans la recherche sans connaître le titre.")
    date_reference = fields.Date("Date de référence", default=fields.Date.context_today,
                                 help="Quand ça s'est passé / quand ça a été établi.")
    sequence = fields.Integer("Ordre", default=10)
    interne = fields.Boolean(
        "Réservé à l'admin", default=False,
        help="Coché : invisible pour les utilisateurs non administrateurs "
             "(architecture serveur, décisions commerciales…).")

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name

    @api.model
    def _search_display_name(self, operator, value):
        """La recherche du champ trouve aussi dans le résumé, le contenu et
        les mots-clés — on cherche rarement le titre exact d'une note."""
        if operator in ("ilike", "like", "=ilike", "=like") and value:
            return [
                "|", "|", "|",
                ("name", operator, value),
                ("resume", operator, value),
                ("mots_cles", operator, value),
                ("contenu", operator, value),
            ]
        return super()._search_display_name(operator, value)

    # ------------------------------------------------------------------
    # Le cahier de reproduction, et sa fraîcheur
    # ------------------------------------------------------------------
    @api.model
    def _empreinte_tour(self):
        """Ce à quoi ressemble la tour aujourd'hui, en une chaîne comparable.

        La liste des modules installés est un indicateur grossier mais
        honnête : on n'ajoute pas une capacité sans ajouter ou modifier un
        module. Grossier, parce qu'un module qui grossit ne change pas la
        liste — d'où le second déclencheur, l'âge.
        """
        modules = self.env["ir.module.module"].sudo().search([
            ("state", "=", "installed"),
            ("name", "like", "tour_"),
        ]).mapped("name")
        return ",".join(sorted(modules))

    def write(self, vals):
        """Écrire dans le cahier remet son compteur de fraîcheur à zéro.

        C'est ce qui fait tenir tout le dispositif : personne n'a à penser à
        marquer le cahier comme à jour. On le met à jour, il l'est.
        """
        res = super().write(vals)
        if "contenu" in vals:
            for rec in self:
                if CAHIER_MOT_CLE in (rec.mots_cles or ""):
                    self.env["ir.config_parameter"].sudo().set_param(
                        "tour_guides.cahier_empreinte", rec._empreinte_tour())
                    if "date_reference" not in vals:
                        super(TourGuide, rec).write(
                            {"date_reference": fields.Date.context_today(rec)})
        return res

    @api.model
    def _cron_verifier_cahier(self, age_max_jours=45):
        """Prévient quand le cahier a décroché de la tour qu'il décrit.

        Deux déclencheurs, parce qu'aucun ne suffit seul :
        - la liste des modules a changé (une capacité est apparue ou partie) ;
        - le cahier n'a pas été touché depuis trop longtemps (une capacité a
          grossi sans qu'un module apparaisse).

        Le rappel prend la forme d'une tâche dans le journal, pas d'un
        courriel : c'est là que le travail se prend, et une tâche déjà ouverte
        n'est pas dupliquée.
        """
        cahier = self.sudo().search(
            [("mots_cles", "ilike", CAHIER_MOT_CLE)], limit=1)
        if not cahier:
            return
        icp = self.env["ir.config_parameter"].sudo()
        empreinte = cahier._empreinte_tour()
        ancienne = icp.get_param("tour_guides.cahier_empreinte", "")
        if not ancienne:
            # Première exécution : on prend l'état actuel pour référence
            # plutôt que d'alerter sur un décalage qu'on n'a pas constaté.
            icp.set_param("tour_guides.cahier_empreinte", empreinte)
            return

        raisons = []
        if empreinte != ancienne:
            avant, apres = set(ancienne.split(",")), set(empreinte.split(","))
            arrives, partis = sorted(apres - avant), sorted(avant - apres)
            if arrives:
                raisons.append("modules apparus : %s" % ", ".join(arrives))
            if partis:
                raisons.append("modules disparus : %s" % ", ".join(partis))
        if cahier.date_reference:
            age = (fields.Date.context_today(cahier) - cahier.date_reference).days
            if age > age_max_jours:
                raisons.append("pas relu depuis %s jours" % age)
        if not raisons:
            return

        Task = self.env["project.task"].sudo()
        titre = "Mettre à jour le Cahier de reproduction"
        if Task.search_count([("name", "=", titre), ("state", "not in", ("1_done", "1_canceled"))]):
            return
        projet = self.env["project.project"].sudo().search(
            [("name", "ilike", "ODOO")], limit=1)
        Task.create({
            "name": titre,
            "project_id": projet.id or False,
            "description":
                "<p>Le guide « %s » a décroché de la tour qu'il décrit :</p>"
                "<ul>%s</ul>"
                "<p>Le cahier sert à ce qu'une autre intelligence puisse "
                "rebâtir la tour. Un cahier périmé ne rate pas une "
                "fonctionnalité : il en décrit une qui n'existe plus, ce qui "
                "coûte plus cher qu'un oubli.</p>"
                "<p><b>PROMPT CLAUDE CODE :</b> relis le guide « %s » de la "
                "tour (modèle <code>tour.guide</code>, mot-clé "
                "<code>reproduction</code>), compare-le aux modules réellement "
                "installés et au CLAUDE.md du dépôt, et mets-le à jour : "
                "ajoute les capacités nouvelles avec leur « point dur », "
                "retire celles qui n'existent plus, et complète la liste des "
                "pièges. Écris dans le champ <code>contenu</code> — ça remet "
                "seul le compteur de fraîcheur à zéro.</p>"
                % (cahier.name,
                   "".join("<li>%s</li>" % r for r in raisons),
                   cahier.name),
        })
        _logger.info("Cahier de reproduction : rappel créé (%s)", "; ".join(raisons))


    # ------------------------------------------------------------------
    # LA DÉTECTION D'ARTICLES (01/08) — à 23h, la tour parcourt ses travaux
    # du jour et crée des BROUILLONS d'articles pour ce qui mérite d'être
    # raconté. Jamais publié seul : Patrick relit et publie. Le brouillon
    # vit dans la catégorie « reseau_sociaux » (les posts à publier).
    # ------------------------------------------------------------------
    @api.model
    def _purger_brouillons_expires(self):
        """Supprime les brouillons d'articles non enrichis depuis trop longtemps.

        Un « brouillon généré » (contenu = PREFIXE_BROUILLON) qui a dormi plus
        de PURGE_BROUILLONS_JOURS jours n'a pas été retenu par le propriétaire :
        le purger, c'est garder la bibliothèque fidèle à ce qui est VRAIMENT à
        publier. Un article enrichi (contenu modifié) n'est jamais purgé.
        Retourne le nombre de brouillons supprimés.
        """
        from datetime import timedelta
        seuil = fields.Datetime.now() - timedelta(days=PURGE_BROUILLONS_JOURS)
        brouillons = self.sudo().search([
            ("categorie", "=", "reseau_sociaux"),
            ("contenu", "ilike", "%" + PREFIXE_BROUILLON + "%"),
            ("create_date", "<", fields.Datetime.to_string(seuil)),
        ])
        if not brouillons:
            return 0
        noms = brouillons.mapped("name")
        brouillons.unlink()
        _logger.info(
            "Articles : purge de %s brouillon(s) expiré(s) : %s",
            len(noms), ", ".join(noms[:5]))
        return len(noms)

    @api.model
    def _cron_detecter_articles(self):
        """Les travaux notables du jour deviennent des brouillons + notification.

        En entrée, on purge d'abord les brouillons oubliés (règle 06/08) :
        un brouillon jamais enrichi ne mérite pas de rester à vie.
        """
        from datetime import timedelta
        self._purger_brouillons_expires()
        Jour = fields.Date.context_today(self)
        fin = Jour + timedelta(days=1)
        cree = []

        def brouillon(nom, resume):
            if self.search([("name", "=", nom)], limit=1):
                return False
            self.create({
                "name": nom, "categorie": "reseau_sociaux",
                "resume": resume,
                "contenu": "<p>Brouillon généré le %s — à enrichir puis publier.</p>" % Jour})
            cree.append(nom)
            return True

        if "atelier.mission" in self.env:
            missions = self.env["atelier.mission"].sudo().search(
                [("create_date", ">=", Jour), ("create_date", "<", fin),
                 ("etat", "=", "terminee")], order="id desc", limit=10)
            for m in missions[:3]:
                brouillon("Article — %s" % (m.name or "mission"),
                          "Brouillon d'article sur le travail terminé : %s" % (m.name or ""))
        if "securite.constat" in self.env:
            constats = self.env["securite.constat"].sudo().search_count(
                [("create_date", ">=", Jour), ("create_date", "<", fin)])
            if constats:
                brouillon("Article — la sécurité : %s constats" % constats,
                          "Brouillon : %s constats de sécurité aujourd'hui." % constats)
        if "decision.fiche" in self.env:
            decisions = self.env["decision.fiche"].sudo().search_count(
                [("create_date", ">=", Jour), ("create_date", "<", fin)])
            if decisions:
                brouillon("Article — %s décisions prises" % decisions,
                          "Brouillon : %s décisions aujourd'hui." % decisions)
        if "circuit.modele" in self.env:
            circuits = self.env["circuit.modele"].sudo().search_count(
                [("create_date", ">=", Jour), ("create_date", "<", fin)])
            if circuits:
                brouillon("Article — %s circuits créés" % circuits,
                          "Brouillon : %s circuits aujourd'hui." % circuits)

        if cree and "tour.message" in self.env:
            self.env["tour.message"].sudo().create({
                "name": "%s article(s) en brouillon à publier" % len(cree),
                "categorie": "autre",
                "corps": "Des brouillons d'articles attendent ta relecture :\n- "
                         + "\n- ".join(cree),
                "pour_qui": "Patrick"})
        return bool(cree)


    # ------------------------------------------------------------------
    # LE CLASSIFICATEUR DE CONNAISSANCES (01/08) — Data.
    # Quand une connaissance arrive sans catégorie, on la range au bon
    # endroit par mots-clés : éducation, piège, architecture, commercial,
    # décision, réseaux sociaux. On propose, on ne décide pas (Patrick valide).
    # ------------------------------------------------------------------
    @api.model
    def _classifier(self, texte):
        t = (texte or "").lower()
        if any(m in t for m in ("voiture", "fusée", "propulsion", "science",
                                "éducation", "apprendre", "expliqué")):
            return "education"
        if any(m in t for m in ("piège", "erreur", "bug", "faux", "attention",
                                "secret de conception", "fuite")):
            return "piege"
        if any(m in t for m in ("circuit", "architecture", "module", "moteur",
                                "garde-fou", "déploiement")):
            return "architecture"
        if any(m in t for m in ("offre", "prix", "commercial", "abonnement",
                                "client", "business")):
            return "commercial"
        if any(m in t for m in ("décision", "choix", "tranché", "validé")):
            return "decision"
        if any(m in t for m in ("post", "linkedin", "réseaux", "youtube",
                                "commentaire", "publier")):
            return "reseau_sociaux"
        return False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("categorie"):
                cat = self._classifier(
                    (vals.get("name") or "") + " " + (vals.get("contenu") or ""))
                if cat:
                    vals["categorie"] = cat
        return super().create(vals_list)
