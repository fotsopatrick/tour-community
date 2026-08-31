/** @odoo-module **/
/*
 * Les applications, rangées par groupe — et en deux affichages.
 *
 * Avant : vingt-sept tuiles à la suite, sans ordre ni titre. Avec autant
 * d'applications on ne cherche plus, on balaye. Une icône reconnaissable ne
 * sert à rien si elle est noyée dans une grille sans structure.
 *
 * Le regroupement seul n'a pas suffi : de grandes tuiles rangées restent de
 * grandes tuiles, et la page en devient plus haute qu'avant. D'où deux
 * affichages, le même contenu :
 *
 *   - « liste » (par défaut) : une ligne fine par application, icône réduite,
 *     nom à côté. C'est un menu — on le parcourt de haut en bas.
 *   - « grille » : les grandes tuiles. C'est une vitrine — on la regarde.
 *
 * Le choix est retenu dans le navigateur : rebasculer à chaque ouverture
 * serait pire que de n'avoir qu'un seul affichage.
 *
 * Le rattachement d'une application à un groupe se fait sur son module
 * d'origine (le préfixe de l'identifiant XML du menu), pas sur son intitulé :
 * un menu renommé reste dans son groupe.
 *
 * 05/08/2026 — pourquoi cette table a doublé de taille. Les huit groupes
 * d'origine couvraient 28 des 64 applications installées : les 36 autres
 * tombaient dans « Le reste », qui était devenu le plus gros tas de la page.
 * Un fourre-tout qui contient la majorité des applications ne range rien, il
 * déplace le problème. La table couvre maintenant TOUS les modules installés,
 * y compris ceux qui n'ont pas encore de tuile — pour qu'ils naissent rangés
 * le jour où ils en gagnent une. Le contrôle qui le vérifie :
 * deploy/controles/controle-rangement-apps.py — il échoue si une application
 * installée n'est nommée dans aucun groupe.
 */
import {NavBar} from "@web/webclient/navbar/navbar";
import {browser} from "@web/core/browser/browser";
import {patch} from "@web/core/utils/patch";
import {useState} from "@odoo/owl";

const MEMOIRE = "tdc_apps_vue";

const GROUPES = [
    {
        titre: "Piloter",
        modules: [
            "tour_dashboard", "tour_projets", "tour_cockpit", "tour_circuits", "tour_decisions",
            "tour_roadmap", "tour_nouveautes", "tour_webapps", "project", "spreadsheet_dashboard",
        ],
    },
    {
        titre: "L'équipe",
        modules: [
            "tour_equipage", "tour_discussion", "tour_braignak", "tour_agent",
            "tour_copilote", "tour_bus", "tour_flux", "tour_echange_agent",
            "tour_echanges", "tour_apprentissage", "tour_debat", "tour_clone",
            "tour_epreuves", "tour_capacites", "tour_sanctions", "tour_tess",
        ],
    },
    {
        titre: "Fabriquer",
        modules: [
            "tour_atelier", "tour_generateur", "tour_dev", "tour_deploiement",
            "tour_promotion", "tour_environnements", "tour_inventaire",
            "tour_modeles", "tour_condense", "tour_condense_community",
            "tour_extension", "tour_mvp", "tour_outils",
        ],
    },
    {
        titre: "Contrôler",
        modules: [
            "tour_recette", "tour_garde_fous", "tour_coherence", "tour_retours",
            "tour_theories",
        ],
    },
    {
        titre: "Protéger",
        modules: [
            "tour_vault", "tour_sauvegardes", "tour_securite",
            "tour_licence_securite", "tour_consoles", "tour_conteneurs",
        ],
    },
    {
        titre: "Savoir",
        modules: [
            "tour_guides", "tour_memoire", "tour_reponses", "tour_actus",
            "tour_recherche", "tour_messages", "tour_depot", "dms",
        ],
    },
    {
        titre: "Moi",
        modules: [
            "tour_cv", "tour_candidatures", "tour_entretiens", "tour_temoignage", "tour_progression",
            "tour_chrono", "tour_rappels", "suivi_apps",
        ],
    },
    {
        titre: "Jouer",
        modules: ["tour_jeu", "tour_jeu_braignak", "tour_quetes", "tour_niveaux"],
    },
    {
        titre: "L'argent",
        modules: [
            "account", "account_accountant", "sale", "sale_management", "purchase",
            "stock", "point_of_sale", "base_accounting_kit", "base_account_budget",
            "l10n_fr", "tour_couts", "tour_abonnements", "tour_rappels_abonnements",
        ],
    },
    {
        titre: "Les gens",
        modules: ["contacts", "hr", "mail", "calendar", "note", "project_todo", "utm"],
    },
    {
        titre: "Réglages",
        modules: [
            "base", "base_setup", "web", "tour_de_controle",
            "tour_de_controle_theme", "tour_appels", "tour_alexa", "tour_bienvenue",
        ],
    },
];

patch(NavBar.prototype, {
    setup() {
        super.setup();
        // On lit une seule fois : `useState` re-rend le composant quand `mode`
        // change, donc la bascule est immédiate sans rien recharger.
        this.tdcVue = useState({
            mode: browser.localStorage.getItem(MEMOIRE) === "grille" ? "grille" : "liste",
        });
    },

    tdcBasculerVue() {
        this.tdcVue.mode = this.tdcVue.mode === "liste" ? "grille" : "liste";
        browser.localStorage.setItem(MEMOIRE, this.tdcVue.mode);
    },

    /**
     * Les applications rangées par groupe, dans l'ordre défini plus haut. Un
     * groupe vide n'est pas rendu : un titre sans rien dessous fait croire à
     * un chargement raté.
     */
    get appsGroupes() {
        const apps = this.apps || [];
        const place = new Set();
        const groupes = [];

        for (const g of GROUPES) {
            const items = apps.filter((app) => {
                const module = (app.xmlid || "").split(".")[0];
                return g.modules.includes(module);
            });
            if (items.length) {
                items.forEach((a) => place.add(a.id));
                groupes.push({titre: g.titre, apps: items});
            }
        }

        // Tout ce qui n'a pas trouvé de groupe reste visible : une application
        // installée qu'on ne voit plus est pire qu'une application mal rangée.
        // Ce groupe doit rester VIDE — s'il se remplit, c'est qu'un module est
        // arrivé sans être nommé dans GROUPES, et le contrôle le dira.
        const reste = apps.filter((a) => !place.has(a.id));
        if (reste.length) {
            groupes.push({titre: "Le reste", apps: reste});
        }
        return groupes;
    },
});
