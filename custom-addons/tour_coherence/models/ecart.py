# -*- coding: utf-8 -*-
"""Emil — l'écart entre ce qu'on AFFICHE et ce qu'on EST.

La panne qui l'a rendu nécessaire, le 27/07 : la page « équipe » du site public
annonçait quatre agents alors qu'il y en avait six. Ce n'était pas un oubli
isolé — **personne ne comparait jamais ce qu'on montre à ce qu'on a**. Un
cahier qui promet trente capacités, une vitrine qui vend un module désinstallé,
un guide qui cite un menu renommé : chacun ment tout seul, et rien ne le dit.

Le métier d'Emil tient en une phrase : **il ne juge ni le fond ni la forme, il
constate un écart entre deux sources qui devraient dire la même chose.**

Trois refus, hérités du socle commun et resserrés pour lui :

- **Zéro intelligence artificielle.** Ses contrôles sont des comparaisons de
  nombres et de listes. Un contrôle doit rendre le même verdict deux fois de
  suite, sinon on ne peut pas savoir si c'est la tour qui a changé ou lui.
- **Il ne corrige jamais le contenu public.** Publier est une action à accord :
  un agent qui réécrit la vitrine tout seul peut y écrire une bêtise que
  personne n'a relue. Il signale, l'humain tranche.
- **Un écart refusé ne revient pas.** Comme chez Victor : ce qu'on a décidé
  d'assumer ne se repropose pas chaque semaine.

Pourquoi Emil : Emil Hamilton est celui qui mesure et vérifie. Et une carte de
la feuille de route lui donnait déjà ce rôle — mesurer si la qualité dérive.
La cohérence est le même métier : mesurer un écart.
"""

import logging
import re
import urllib.request

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

# On lit la vitrine par son ADRESSE, pas par son fichier.
#
# Le fichier n est pas monte dans le conteneur d Odoo — Emil rendait donc
# << pas mesurable >> a chaque passage. Et l adresse est de toute facon la
# bonne source : elle donne ce que le VISITEUR recoit, pas ce qui traine sur
# un disque. C est la meme regle que pour un deploiement — ne jamais dire
# << c est en ligne >> sans avoir regarde ce qui arrive chez l utilisateur.
VITRINE_URL = "https://matourdecontrole.fr/"


class CoherenceEcart(models.Model):
    _name = "coherence.ecart"
    _description = "Écart entre ce qu'on affiche et ce qu'on est"
    _inherit = ["mail.thread"]
    _order = "gravite_poids, id desc"

    name = fields.Char("Écart", required=True, tracking=True)
    code = fields.Char("Contrôle", required=True, index=True,
                       help="Identifiant stable du contrôle qui a produit cet écart.")
    gravite = fields.Selection(
        [("grave", "Grave — on promet ce qu'on n'a pas"),
         ("moyen", "Moyen — une information est périmée"),
         ("info", "À savoir")],
        "Gravité", required=True, default="moyen", tracking=True)
    gravite_poids = fields.Integer(compute="_compute_poids", store=True)

    affiche = fields.Char("Ce qu'on affiche", readonly=True)
    reel = fields.Char("Ce qui est vrai", readonly=True)
    ou = fields.Char("Où le corriger", readonly=True)
    constat = fields.Html("Le détail", readonly=True)

    etat = fields.Selection(
        [("ouvert", "À corriger"),
         ("assume", "Assumé — ne plus le signaler"),
         ("corrige", "Corrigé")],
        "État", default="ouvert", required=True, tracking=True)
    vu_le = fields.Datetime("Dernière vérification", readonly=True)

    _sql_constraints = [
        ("code_unique", "unique(code)",
         "Un écart existe déjà pour ce contrôle : on le met à jour, on n'en "
         "crée pas un second."),
    ]

    @api.depends("gravite")
    def _compute_poids(self):
        poids = {"grave": 1, "moyen": 2, "info": 3}
        for rec in self:
            rec.gravite_poids = poids.get(rec.gravite, 9)

    def action_assumer(self):
        """« Je sais, et c'est voulu. » Ne se repropose plus."""
        for rec in self:
            rec.write({"etat": "assume"})
            rec.message_post(body=_("Écart assumé par %s.") % self.env.user.name)

    def action_rouvrir(self):
        for rec in self:
            rec.write({"etat": "ouvert"})


class CoherenceAgent(models.AbstractModel):
    """Emil : les contrôles, et rien d'autre."""

    _name = "coherence.agent"
    _description = "Emil — la cohérence"

    # ------------------------------------------------------------------
    # Les contrôles. Chacun rend (ok, affiche, reel, ou, detail_html) ou
    # None quand il ne s'applique pas — ne pas confondre « cohérent » et
    # « pas mesurable ici » : le second ne doit rassurer personne.
    # ------------------------------------------------------------------
    def _c_vitrine_agents(self):
        """La page publique annonce-t-elle le bon nombre d'agents ?

        C'est le contrôle qui a fait naître Emil. On compte les fiches de la
        section équipe du fichier servi, et on compare aux agents CONSTRUITS —
        pas aux recrutés : afficher sur une vitrine ceux qu'on n'a pas encore
        serait exactement la dérive qu'on traque.
        """
        url = self.env["ir.config_parameter"].sudo().get_param(
            "tour_coherence.vitrine_url", VITRINE_URL)
        try:
            requete = urllib.request.Request(
                url, headers={"User-Agent": "tour-de-controle/1.0 (Emil)"})
            with urllib.request.urlopen(requete, timeout=15) as rep:
                page = rep.read().decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            # Site injoignable : on ne dit PAS que tout va bien. Ne pas
            # confondre << coherent >> et << pas mesurable >>.
            return None, None, None, None, None
        bloc = page.split('id="equipe"', 1)
        if len(bloc) < 2:
            return None, None, None, None, None
        section = bloc[1].split("</section>", 1)[0]
        affiches = re.findall(r"<h3>([^<]+)</h3>", section)
        # Le nombre annoncé en toutes lettres dans le texte d'introduction.
        chiffres = {"Deux": 2, "Trois": 3, "Quatre": 4, "Cinq": 5, "Six": 6,
                    "Sept": 7, "Huit": 8, "Neuf": 9, "Dix": 10}
        annonce = None
        m = re.search(r"(Deux|Trois|Quatre|Cinq|Six|Sept|Huit|Neuf|Dix)\s+agents",
                      section)
        if m:
            annonce = chiffres.get(m.group(1))

        # Piege paye ici : un recordset VIDE est falsy. Ecrire
        # << Membre = self.env[...] ; if not Membre >> renvoyait toujours
        # << pas mesurable >>, parce qu un modele sans aucun enregistrement
        # se teste comme False. On teste la PRESENCE du modele, pas sa
        # verite — ce sont deux questions differentes.
        if "equipe.membre" not in self.env:
            return None, None, None, None, None
        Membre = self.env["equipe.membre"]
        # Un agent est CONSTRUIT s'il a produit quelque chose, ou s'il a un
        # moteur. Perry et Tess sont recrutés : ils n'ont ni l'un ni l'autre.
        construits = Membre.sudo().search([]).filtered(
            lambda m_: m_.moteur or any(c.valeur for c in m_.competence_ids))
        n_reel = len(construits)
        souci = []
        if annonce is not None and annonce != len(affiches):
            souci.append("La page annonce « %s agents » et en présente %s."
                         % (annonce, len(affiches)))
        # Deux comparaisons DIFFERENTES, et c'est voulu (28/07) :
        # - un agent construit doit etre montre -> manquants vs CONSTRUITS ;
        # - un nom montre doit exister dans l'equipe -> en_trop vs TOUS les
        #   membres. Patrick et Claude sont sur la vitrine et dans l'equipe
        #   sans moteur : des humains, pas des agents a verifier. Les comparer
        #   aux seuls construits les declarait mensongers a tort.
        tous_noms = set(Membre.sudo().search([]).mapped("name"))
        if len(affiches) != n_reel or not set(affiches) <= tous_noms:
            manquants = sorted(set(construits.mapped("name")) - set(affiches))
            en_trop = sorted(set(affiches) - tous_noms)
            if manquants:
                souci.append("Absents de la vitrine : <b>%s</b>."
                             % ", ".join(manquants))
            if en_trop:
                souci.append("Présentés mais pas construits : <b>%s</b>."
                             % ", ".join(en_trop))
        if not souci:
            return True, None, None, None, None
        return (False,
                "%s agent(s) sur la vitrine" % len(affiches),
                "%s agent(s) construits" % n_reel,
                "deploy/vitrine/index.html",
                "<p>%s</p>" % "</p><p>".join(souci))

    def _c_cahier_capacites(self):
        """Le cahier de reproduction annonce-t-il le bon nombre de capacités ?"""
        if "tour.guide" not in self.env:
            return None, None, None, None, None
        cahier = self.env["tour.guide"].sudo().search([("mots_cles", "ilike", "reproduction")], limit=1)
        if not cahier:
            return None, None, None, None, None
        contenu = str(cahier.contenu or "")
        # Le point doit etre suivi d un ESPACE : sans ca, << 3.1 Projets >>
        # (une sous-section) etait compte comme la capacite numero 3, et le
        # controle mesurait n importe quoi avec aplomb.
        numeros = [int(n) for n in re.findall(r"<h3>\s*(\d+)\.\s", contenu)]
        if not numeros:
            return None, None, None, None, None
        dernier = max(numeros)
        # Les modules tour_* réellement installés : le cahier décrit ce que la
        # tour SAIT FAIRE, donc il grandit avec eux.
        modules = self.env["ir.module.module"].sudo().search_count(
            [("name", "like", "tour\\_%"), ("state", "=", "installed")])
        # Tolérance : toutes les capacités ne viennent pas d'un module, et tous
        # les modules ne sont pas une capacité. On ne signale qu'un décrochage
        # net — sinon on crie à chaque installation.
        if abs(dernier - modules) <= 6:
            return True, None, None, None, None
        return (False,
                "%s capacités décrites" % dernier,
                "%s modules tour_* installés" % modules,
                "Guides > Cahier de reproduction",
                "<p>Le cahier décrit %s capacités alors que %s modules sont "
                "installés. L'écart est trop grand pour être du hasard : soit "
                "des capacités livrées n'y sont pas, soit il en décrit qui "
                "n'existent plus.</p><p>Un cahier périmé ne rate pas une "
                "fonction, il en décrit une qui n'existe pas — et celui qui "
                "s'y fie construit du vide avec confiance.</p>"
                % (dernier, modules))

    def _c_agents_muets(self):
        """Un agent construit qui n'a jamais rien produit."""
        if "equipe.membre" not in self.env:
            return None, None, None, None, None
        membres = self.env["equipe.membre"].sudo().search([])
        muets = membres.filtered(
            lambda m_: m_.moteur and not any(c.valeur for c in m_.competence_ids))
        if not muets:
            return True, None, None, None, None
        noms = ", ".join(muets.mapped("name"))
        return (False,
                "%s agent(s) présentés comme actifs" % len(muets),
                "0 travail produit",
                "Pilotage > L'équipe",
                "<p><b>%s</b> a un moteur — donc il est présenté comme "
                "utilisable — mais n'a jamais rien produit.</p><p>Soit on ne "
                "s'en sert pas et il faut le dire, soit il est cassé et "
                "personne ne l'a vu.</p>" % noms)

    CONTROLES = [
        ("vitrine_agents", "La vitrine annonce le bon nombre d'agents", "grave"),
        ("cahier_capacites", "Le cahier décrit ce que la tour sait faire", "moyen"),
        ("agents_muets", "Aucun agent présenté comme actif n'est muet", "moyen"),
    ]

    @api.model
    def _cron_verifier(self):
        """Passe tous les contrôles. Ne lève jamais : un cron qui plante s'éteint."""
        Ecart = self.env["coherence.ecart"].sudo()
        nouveaux = Ecart.browse()
        for code, intitule, gravite in self.CONTROLES:
            try:
                ok, affiche, reel, ou, detail = getattr(self, "_c_%s" % code)()
            except Exception as exc:  # noqa: BLE001
                _logger.warning("Emil : le controle %s a echoue (%s)", code, exc)
                continue
            if ok is None:
                continue  # pas mesurable ici — ne rassure personne
            existant = Ecart.search([("code", "=", code)], limit=1)
            if ok:
                if existant and existant.etat != "corrige":
                    existant.write({"etat": "corrige", "vu_le": fields.Datetime.now()})
                    existant.message_post(body=_("Réglé : les deux sources disent "
                                                 "la même chose."))
                continue
            vals = {"name": intitule, "gravite": gravite, "affiche": affiche,
                    "reel": reel, "ou": ou, "constat": detail,
                    "vu_le": fields.Datetime.now()}
            if existant:
                if existant.etat == "assume":
                    existant.vu_le = fields.Datetime.now()
                    continue
                existant.write(vals)
                if existant.etat == "corrige":
                    existant.write({"etat": "ouvert"})
                    nouveaux |= existant
                continue
            nouveaux |= Ecart.create(dict(vals, code=code))

        if nouveaux:
            self._prevenir(nouveaux)
        return True

    def _prevenir(self, ecarts):
        """Un seul signal, avec ce qu'on affiche et ce qui est vrai côte à côte."""
        if "tour.signal" not in self.env:
            return
        lignes = []
        for e in ecarts.sorted(lambda r: r.gravite_poids):
            lignes.append(
                "<li><b>%s</b><br/>On affiche : %s<br/>En vrai : %s<br/>"
                "<span style='color:#64748b'>À corriger dans : %s</span></li>"
                % (e.name, e.affiche or "?", e.reel or "?", e.ou or "?"))
        self.env["tour.signal"]._signaler(
            agent="Emil",
            titre=_("%s écart(s) entre ce qu'on affiche et ce qu'on est",
                    len(ecarts)),
            corps_html="<ul>%s</ul><p><i>Je constate l'écart, je ne corrige "
                       "rien : réécrire une page publique tout seul, c'est "
                       "pouvoir y mettre une bêtise que personne n'a "
                       "relue.</i></p>" % "".join(lignes),
            ton="attention")

    # ------------------------------------------------------------------
    # Le contrôle des promesses — hebdomadaire, avec son témoin à 21 jours
    # ------------------------------------------------------------------

    @api.model
    def _cron_promesses_hebdo(self):
        """Chaque semaine, une tâche : relire ce que les sites PROMETTENT.

        Demande de Patrick (29/07) : « en matière de sécurité, faut faire
        gaffe aux promesses — si on ne peut pas tout promettre, mieux vaut
        dire ce qu'on peut promettre aujourd'hui ». Un contrôle de sens,
        pas de code : aucun grep ne sait juger une promesse. La machine
        pose donc la tâche, un humain (ou une session Claude) la déroule.
        """
        T = self.env["project.task"].sudo()
        annee, semaine, _jour = fields.Date.today().isocalendar()
        titre = ("[VÉRIF] Semaine %s-%02d : les sites promettent-ils plus "
                 "qu'on offre ? (sécurité d'abord)" % (annee, semaine))
        if T.with_context(active_test=False).search_count([("name", "=", titre)]):
            return
        T.create({
            "name": titre,
            "project_id": 1,
            "description": (
                "<p>Relire les pages publiques et comparer chaque promesse "
                "à la réalité. Une promesse qu'on ne tient pas se corrige "
                "ou se remplace par « voici ce qu'on sait faire "
                "aujourd'hui, le reste arrive ».</p>"
                "<p><b>PROMPT CLAUDE CODE :</b> Sur le clone de la tour, "
                "relever les promesses de deploy/vitrine/*.html (grep "
                "sécurité, sauvegarde, chiffr, RGPD, données, jours, "
                "garanti) puis vérifier CHACUNE contre les faits : CGV vs "
                "constantes du code (ex. JOURS_APRES_RESILIATION), clé du "
                "Coffre hors base (env ODOO_VAULT_KEY du conteneur), "
                "unattended-upgrades sur le VPS, sauvegardes vérifiées, "
                "sortie des données vers les API d'IA. Corriger le code "
                "quand il contredit le contrat ; proposer les textes de "
                "vitrine via le circuit d'essai (deploy/vitrine.sh) — "
                "jamais publier seul. Consigner le relevé dans cette tâche "
                "et la fermer.</p>"),
        })

    @api.model
    def _cron_promesses_temoin(self):
        """Tous les 21 jours : le témoin — le contrôle hebdo tourne-t-il ?

        Le témoignage de Patrick (29/07), à rendre vrai : « je peux me
        faire des rappels pour moi dans le futur ». Si dans trois semaines
        personne n'a vu passer les tâches hebdomadaires, c'est que le
        circuit est mort — et ce témoin est là pour qu'on le voie.
        """
        T = self.env["project.task"].sudo()
        il_y_a_21j = fields.Datetime.subtract(fields.Datetime.now(), days=21)
        passees = T.with_context(active_test=False).search_count([
            ("name", "like", "[VÉRIF] Semaine %"),
            ("create_date", ">=", il_y_a_21j)])
        titre = ("[TÉMOIN] %s : le contrôle des promesses a-t-il tourné "
                 "3 fois ces 3 semaines ? (%d relevée(s))"
                 % (fields.Date.today(), passees))
        if T.with_context(active_test=False).search_count([("name", "=", titre)]):
            return
        T.create({
            "name": titre,
            "project_id": 1,
            "description": (
                "<p>Témoignage de Patrick (29/07), à rendre vrai : « au "
                "moins je peux me faire des rappels pour moi dans le futur "
                "— témoigner dans le futur ». Trois tâches hebdomadaires "
                "étaient attendues sur 21 jours ; il y en a eu <b>%d</b>. "
                "Moins de 3 = le circuit s'est arrêté, le réparer AVANT de "
                "fermer cette tâche. 3 ou plus = fermer en notant que la "
                "promesse est tenue.</p>" % passees),
        })
