# -*- coding: utf-8 -*-
"""Le cloisonnement de la tour, en un seul endroit.

POURQUOI UN MODULE A PART, ET PAS UNE REGLE DANS CHAQUE MODULE.
Les 41 modeles concernes vivent dans 27 modules. Poser les regles chez eux
voudrait dire 27 fichiers, 27 manifestes et 27 mises a jour — et on a vu ce
matin qu'une mise a jour peut echouer et bloquer les 26 autres. Ici : un
module, une mise a jour, un endroit ou lire ce qui est ferme et pourquoi.

POURQUOI EN PYTHON ET PAS EN XML.
Une regle XML utilise `ref('model_xxx')`, ce qui oblige a declarer les 27
modules en dependance : si l'un est desinstalle, tout casse. Le code, lui,
cherche le modele et passe s'il n'existe pas. C'est aussi ce qui rend le
travail rejouable : relancer la mise a jour repose les regles manquantes sans
toucher a celles qui sont la.

CE QUI EST FERME, ET CE QUI NE L'EST PAS.
Trois formes, choisies modele par modele apres avoir regarde ses champs :

  « a moi »   — le modele designe une personne (user_id, demandeur_id). On
                cloisonne : chacun les siens, l'admin tout.
  « au parent » — le modele est une piece d'un autre (une etape appartient a
                sa mission). Il suit son parent, sinon on ferme la porte et
                on laisse la fenetre : c'etait le cas des 2012 etapes de
                missions pourtant fermees.
  « interne » — le modele n'appartient a personne d'autre qu'a la tour.
                Ferme aux comptes sans droits.

CE QU'ON NE FERME PAS : la vitrine. `equipe.membre`, `tour.nouveaute`,
`actus.article`, `roadmap.*` restent communs — c'est ce qu'on montre. Verifie
avant : aucune page publique ne lit les modeles fermes sans `sudo()`.

TOUJOURS DEUX REGLES DE GROUPE, JAMAIS UNE GLOBALE. Une regle sans `groups`
s'applique a tout le monde, administrateur compris, et enferme tout le monde
dehors. C'est la « lecon de Clark » sur tour_reponses, deja payee une fois.
"""
import logging

_logger = logging.getLogger(__name__)

# modele -> (forme, domaine pour les comptes sans droits, pourquoi)
CLOISONS = {
    # ---- 1. les donnees personnelles de Patrick -----------------------
    "cv.profil": ("interne", "[(0, '=', 1)]", "le CV de Patrick"),
    "cv.experience": ("interne", "[(0, '=', 1)]", "le CV de Patrick"),
    "cv.formation": ("interne", "[(0, '=', 1)]", "le CV de Patrick"),
    "cv.competence": ("interne", "[(0, '=', 1)]", "le CV de Patrick"),
    "cv.realisation": ("interne", "[(0, '=', 1)]", "le CV de Patrick"),
    "cv.bloc": ("interne", "[(0, '=', 1)]", "le CV de Patrick"),
    "clone.feedback": ("interne", "[(0, '=', 1)]",
                       "les corrections de Patrick sur son Clone"),
    "chrono.temps": ("a moi", "[('user_id', '=', user.id)]",
                     "les pointages : chacun les siens"),
    "entretien.fiche": ("interne", "[(0, '=', 1)]",
                        "les entretiens d'embauche de Patrick"),

    # ---- 2. le travail interne ---------------------------------------
    "atelier.mission.etape": (
        "au parent", "[('mission_id.create_uid', '=', user.id)]",
        "une etape suit sa mission — 2012 etaient lisibles alors que les "
        "1466 missions etaient fermees"),
    "condense.resume": ("interne", "[(0, '=', 1)]", "les condenses du travail"),
    "condense.cible": ("interne", "[(0, '=', 1)]", "les cibles de condense"),
    "agent.evenement": ("interne", "[(0, '=', 1)]", "l'activite des agents"),
    "agent.epreuve": ("interne", "[(0, '=', 1)]", "les epreuves des agents"),
    "agent.passage": ("interne", "[(0, '=', 1)]", "les passages d'epreuves"),
    "braignak.etude": ("a moi", "[('demandeur_id', '=', user.id)]",
                       "chacun ses etudes"),
    "braignak.journal": ("au parent",
                         "[('etude_id.demandeur_id', '=', user.id)]",
                         "le journal suit son etude"),
    "braignak.jeu.edition": ("interne", "[(0, '=', 1)]",
                             "les editions du jeu de Braignak"),
    "apprentissage.lecon": ("interne", "[(0, '=', 1)]",
                            "ce que les agents ont appris"),
    "apprentissage.source": ("interne", "[(0, '=', 1)]",
                             "les sources d'apprentissage"),
    "depot.note": ("interne", "[(0, '=', 1)]", "les notes du depot"),
    "echange.agent": ("interne", "[(0, '=', 1)]", "les echanges entre agents"),
    "coherence.ecart": ("interne", "[(0, '=', 1)]", "les ecarts de coherence"),
    "theorie.fiche": ("interne", "[(0, '=', 1)]", "les theories de la tour"),
    "equipe.competence": ("interne", "[(0, '=', 1)]",
                          "les competences des agents"),
    "equipe.livraison": ("interne", "[(0, '=', 1)]",
                         "ce que les agents ont livre"),

    # ---- 4. la gamification -------------------------------------------
    # Les PAGES sont deja reservees a l'admin (regle de Patrick du 01/08) ;
    # les DONNEES ne l'etaient pas. On aligne.
    "quete.fiche": ("interne", "[(0, '=', 1)]", "les quetes de Patrick"),
    "quete.domaine": ("interne", "[(0, '=', 1)]", "les domaines de quete"),
    "quete.guilde": ("interne", "[(0, '=', 1)]", "les guildes"),
    "quete.offre": ("interne", "[(0, '=', 1)]", "les offres de quete"),
    "jeu.carte": ("a moi", "[('user_id', '=', user.id)]",
                  "chacun ses cartes"),
    "braignak.jeu.participation": ("a moi", "[('user_id', '=', user.id)]",
                                   "chacun sa participation"),
    # PAS `app.apporteur` : suivi_apps lui pose deja ses deux regles. Un
    # apporteur doit voir SA fiche — c'est sa logique metier, pas la notre.
    # Le toucher d'ici casserait une regle qu'on ne connait pas.

    # ---- 5. la technique ----------------------------------------------
    "tour.module": ("interne", "[(0, '=', 1)]", "l'inventaire des modules"),
    "tour.actions.config": ("interne", "[(0, '=', 1)]",
                            "le reglage du menu Actions ; le menu le lit en "
                            "sudo(), donc rien ne casse"),
    "tour.jalon": ("interne", "[(0, '=', 1)]", "les jalons de progression"),
    "tour.environnement": ("interne", "[(0, '=', 1)]",
                           "prod / demo / test"),
    "tour.cap": ("interne", "[(0, '=', 1)]", "le cap de la tour"),
    "site.genere": ("interne", "[(0, '=', 1)]", "les sites generes"),
    "app.suivi": ("interne", "[(0, '=', 1)]", "le suivi des apps de Patrick"),
    "app.offre": ("interne", "[(0, '=', 1)]", "les offres commerciales"),
    "app.capture": ("interne", "[(0, '=', 1)]", "les captures d'apps"),
    "abonnement.actif": ("interne", "[(0, '=', 1)]",
                         "les abonnements de Patrick"),
}


def poser_les_cloisons(env):
    """Pose (ou repose) les deux regles de chaque modele cloisonne.

    Idempotent : on cherche par identifiant XML, on met a jour si la regle
    existe deja. Relancer la mise a jour ne cree pas de doublon et repare ce
    qui aurait ete supprime a la main.
    """
    IM = env["ir.model"].sudo()
    IR = env["ir.rule"].sudo()
    IMD = env["ir.model.data"].sudo()
    groupe_user = env.ref("base.group_user")
    groupe_admin = env.ref("base.group_system")

    poses, absents = 0, []
    for modele, (forme, domaine, pourquoi) in sorted(CLOISONS.items()):
        m = IM.search([("model", "=", modele)], limit=1)
        if not m:
            absents.append(modele)
            continue

        technique = modele.replace(".", "_")
        for suffixe, dom, groupe, libelle in (
            ("proprietaire", domaine, groupe_user,
             "%s : %s" % (modele, pourquoi)),
            ("admin", "[(1, '=', 1)]", groupe_admin,
             "%s : l'administrateur voit tout" % modele),
        ):
            xid = "regle_%s_%s" % (technique, suffixe)
            donnee = IMD.search([("module", "=", "tour_cloisonnement"),
                                 ("name", "=", xid)], limit=1)
            vals = {
                "name": libelle[:120],
                "model_id": m.id,
                "domain_force": dom,
                "groups": [(6, 0, [groupe.id])],
                "perm_read": True, "perm_write": True,
                "perm_create": True, "perm_unlink": True,
                "active": True,
            }
            if donnee and donnee.res_id:
                regle = IR.browse(donnee.res_id)
                if regle.exists():
                    regle.write(vals)
                    poses += 1
                    continue
                donnee.unlink()
            regle = IR.create(vals)
            IMD.create({
                "module": "tour_cloisonnement", "name": xid,
                "model": "ir.rule", "res_id": regle.id,
                # `noupdate` EST INDISPENSABLE, et la lecon a ete payee deux
                # fois le meme jour. Un enregistrement qui porte l'identifiant
                # d'un module sans etre declare dans ses FICHIERS est vu comme
                # un orphelin : Odoo le supprime a la fin du chargement. C'est
                # ce qui a failli effacer quatre membres de l'equipe ce matin,
                # et c'est ce qui a efface ces regles au premier essai — le
                # hook les creait, le menage les reprenait aussitot.
                "noupdate": True,
            })
            poses += 1

    _logger.info("tour_cloisonnement : %d regles posees, %d modeles absents %s",
                 poses, len(absents), absents or "")
    return poses, absents


def post_init_hook(env):
    poser_les_cloisons(env)


# Charge le modele qui repose les cloisons a chaque demarrage. L'import est
# EN FIN DE FICHIER : models.py importe CLOISONS et poser_les_cloisons d'ici,
# donc ils doivent exister avant.
from . import models  # noqa: E402
