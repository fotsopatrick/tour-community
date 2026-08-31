/** @odoo-module **/

import {WebClient} from "@web/webclient/webclient";
import {browser} from "@web/core/browser/browser";
import {cookie} from "@web/core/browser/cookie";
import {patch} from "@web/core/utils/patch";
import {registry} from "@web/core/registry";

// Mode sombre par défaut dès la première visite (web_dark_mode se base sinon
// sur la préférence système). Garde anti-boucle si les cookies sont bloqués.
if (!cookie.get("color_scheme")) {
    cookie.set("color_scheme", "dark");
    if (cookie.get("color_scheme") === "dark") {
        browser.location.reload();
    }
}

// Si le serveur vient de basculer le cookie (préférence utilisateur) mais que
// la page a été rendue avec l'autre bundle, on recharge une fois pour aligner.
const darkBundleLoaded = !!document.querySelector('link[href*="assets_web_dark"]');
if (cookie.get("color_scheme") === "dark" && !darkBundleLoaded) {
    browser.location.reload();
}

// Titre de l'onglet : "Tour de contrôle" au lieu de "Odoo"
patch(WebClient.prototype, {
    setup() {
        super.setup();
        this.title.setParts({zopenerp: "Tour de contrôle"});
    },
});

// Boîtes de dialogue d'erreur : "Odoo Server Error" -> "Erreur serveur", etc.
import {
    ClientErrorDialog,
    ErrorDialog,
    NetworkErrorDialog,
    RPCErrorDialog,
    WarningDialog,
} from "@web/core/errors/error_dialogs";

const stripOdoo = (title) =>
    typeof title === "string" ? title.replace(/^Odoo\s+/, "").replace(/^Odoo$/, "Erreur") : title;

ErrorDialog.title = "Erreur";
ClientErrorDialog.title = "Erreur client";
NetworkErrorDialog.title = "Erreur réseau";

patch(RPCErrorDialog.prototype, {
    setup() {
        super.setup();
        this.title = stripOdoo(this.title);
    },
});

patch(WarningDialog.prototype, {
    setup() {
        super.setup();
        this.title = stripOdoo(this.title);
    },
});

// Retire les entrées odoo.com du menu utilisateur
const debrandService = {
    start() {
        const menu = registry.category("user_menuitems");
        for (const item of ["documentation", "support", "odoo_account"]) {
            if (menu.contains(item)) {
                menu.remove(item);
            }
        }
    },
};
registry.category("services").add("tdc_debrand", debrandService);

// SECRET DE CONCEPTION (01/08) : masquer le fait qu'on utilise Odoo.
// Le client web garde des traces : le « Powered by Odoo » du dialogue
// « À propos », et le logo Odoo. On les retire à la volée (MutationObserver)
// pour que rien ne trahisse la technologie, sur TOUS les environnements.
const masquerOdoo = () => {
    if (!document.body) {
        return;  // pas encore de <body> : on retentera via l'observer au prochain changement
    }
    const texte = (node) =>
        node.nodeType === Node.TEXT_NODE ? node.textContent : "";
    const marche = document.createTreeWalker(
        document.body, NodeFilter.SHOW_TEXT);
    let noeud;
    while ((noeud = marche.nextNode())) {
        const t = noeud.textContent || "";
        if (/powered\s+by\s+odoo/i.test(t) ||
            (t.trim() === "Odoo" && noeud.parentElement &&
             noeud.parentElement.closest(".o_about_content"))) {
            noeud.textContent = t.replace(/powered\s+by\s+odoo/gi, "");
        }
    }
    // Le logo Odoo du dialogue « À propos » (img/svg portant la marque)
    document.querySelectorAll(".o_about_logo, .o_about_content img, .o_about_content svg")
        .forEach((el) => el.remove());
};
if (typeof MutationObserver !== "undefined" && document.body) {
    new MutationObserver(masquerOdoo).observe(
        document.body, { childList: true, subtree: true });
}
masquerOdoo();
