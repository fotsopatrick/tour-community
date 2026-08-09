/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

/**
 * Le fil d'actus : onglets par centre d'intérêt, cartes cliquables.
 * Les sources se gèrent dans Actus > Sources (activer/désactiver, ajouter un RSS).
 */
export class ActusFil extends Component {
    static template = "tour_actus.Fil";
    static props = ["*"];

    setup() {
        this.state = useState({
            categories: [],
            active: "",
            busy: false,
        });
        onWillStart(async () => {
            await this.charger();
            // Premier chargement d'une base neuve : le fil est vide, on relève.
            if (!this.state.categories.length) {
                await this.rafraichir();
            }
        });
    }

    async charger() {
        const data = await rpc("/tour_actus/fil", {});
        this.appliquer(data);
    }

    async rafraichir() {
        this.state.busy = true;
        try {
            const data = await rpc("/tour_actus/rafraichir", {});
            this.appliquer(data);
        } finally {
            this.state.busy = false;
        }
    }

    appliquer(data) {
        this.state.categories = data.categories;
        const noms = data.categories.map((c) => c.nom);
        if (!noms.includes(this.state.active)) {
            this.state.active = noms[0] || "";
        }
    }

    get articlesActifs() {
        const cat = this.state.categories.find((c) => c.nom === this.state.active);
        return cat ? cat.articles : [];
    }

    ilYA(iso) {
        if (!iso) {
            return "";
        }
        const min = Math.max(0, Math.round((Date.now() - new Date(iso + "Z")) / 60000));
        if (min < 60) {
            return `il y a ${min} min`;
        }
        const h = Math.round(min / 60);
        return h < 24 ? `il y a ${h} h` : `il y a ${Math.round(h / 24)} j`;
    }
}

registry.category("actions").add("tour_actus.fil", ActusFil);
