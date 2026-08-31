/** @odoo-module **/

import {NavBar} from "@web/webclient/navbar/navbar";
import {patch} from "@web/core/utils/patch";

patch(NavBar.prototype, {
    /**
     * La sidebar est verticale : la largeur disponible ne veut plus rien dire,
     * on ne replie donc jamais les sections dans le menu "Plus".
     * @override
     */
    async adapt() {
        if (!this.root.el) {
            return;
        }
        const sectionsMenu = this.appSubMenus.el;
        if (!sectionsMenu) {
            return;
        }
        const sections = [
            ...sectionsMenu.querySelectorAll(":scope > *:not(.o_menu_sections_more)"),
        ];
        for (const section of sections) {
            section.classList.remove("d-none");
        }
        if (this.currentAppSectionsExtra.length) {
            this.currentAppSectionsExtra = [];
            return this.render();
        }
    },
});
