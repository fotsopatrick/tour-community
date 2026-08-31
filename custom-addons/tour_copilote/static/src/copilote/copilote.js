/** @odoo-module **/

import { Component, useState, useRef, onMounted, markup } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { rendreContenu, lierCopieurs } from "./code-render";

const STORAGE_KEY = "tour_copilote.history";
const OPEN_KEY = "tour_copilote.open";

/**
 * Le copilote : une bulle flottante presente sur toutes les pages du
 * backend, qui ouvre un panneau de chat branche sur Claude (cle API
 * configuree dans Parametres > Copilote IA). Masquable d'un clic,
 * historique conserve dans le navigateur.
 */
export class TourCopilote extends Component {
    static template = "tour_copilote.Copilote";
    static props = {};

    setup() {
        let history = [];
        try {
            history = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
        } catch {
            history = [];
        }
        this.state = useState({
            open: localStorage.getItem(OPEN_KEY) === "1",
            busy: false,
            input: "",
            messages: history,
            // La piece jointe en attente : lue dans le navigateur, envoyee
            // avec le prochain message, puis oubliee.
            piece: null,
        });
        this.scrollRef = useRef("scroll");
        this.refs = { fichier: useRef("fichier") };
        onMounted(() => {
            this.scrollDown();
            if (this.scrollRef.el) {
                lierCopieurs(this.scrollRef.el);
            }
        });
    }

    // Le code dans les réponses s'affiche proprement (design du code) : les
    // blocs ```…``` deviennent des blocs colorés copiables d'un clic.
    rendre(msg) {
        return markup(rendreContenu(msg && msg.content));
    }

    toggle() {
        this.state.open = !this.state.open;
        localStorage.setItem(OPEN_KEY, this.state.open ? "1" : "0");
        if (this.state.open) {
            setTimeout(() => this.scrollDown());
        }
    }

    clear() {
        this.state.messages = [];
        localStorage.removeItem(STORAGE_KEY);
    }

    refresh() {
        try {
            this.state.messages = JSON.parse(
                localStorage.getItem(STORAGE_KEY) || "[]"
            );
        } catch {
            this.state.messages = [];
        }
        this.state.busy = false;
        setTimeout(() => this.scrollDown());
    }

    persist() {
        localStorage.setItem(
            STORAGE_KEY,
            JSON.stringify(this.state.messages.slice(-30))
        );
    }

    scrollDown() {
        const el = this.scrollRef.el;
        if (el) {
            el.scrollTop = el.scrollHeight;
        }
    }

    onKeydown(ev) {
        if (ev.key === "Enter" && !ev.shiftKey) {
            ev.preventDefault();
            this.send();
        }
    }

    choisirPiece() {
        this.refs.fichier.el?.click();
    }

    retirerPiece() {
        this.state.piece = null;
    }

    // LA PIECE JOINTE PART EN BASE64 AVEC LE MESSAGE (04/08).
    // On lit le fichier ICI, dans le navigateur : rien n est televerse tant
    // que le message n est pas envoye. Le serveur revalide la taille et
    // l extension — ce qui est verifie cote navigateur ne l est jamais.
    async onFichier(ev) {
        const f = ev.target.files && ev.target.files[0];
        ev.target.value = "";
        if (!f) {
            return;
        }
        if (f.size > 8 * 1024 * 1024) {
            this.state.messages.push({
                role: "assistant",
                content: "Ce fichier fait plus de 8 Mo — je ne peux pas le garder.",
                isError: true,
            });
            return;
        }
        const donnees = await new Promise((ok) => {
            const l = new FileReader();
            l.onload = () => ok(String(l.result).split(",")[1] || "");
            l.readAsDataURL(f);
        });
        this.state.piece = { nom: f.name, donnees };
    }

    async send() {
        const text = this.state.input.trim();
        // Une capture seule est un message : « tiens, regarde ». On n exige
        // pas de texte quand un fichier attend.
        if ((!text && !this.state.piece) || this.state.busy) {
            return;
        }
        this.state.input = "";
        const piece = this.state.piece;
        this.state.piece = null;
        this.state.messages.push({
            role: "user",
            content: text || "(capture jointe)",
            piece: piece ? piece.nom : null,
        });
        this.state.busy = true;
        this.persist();
        setTimeout(() => this.scrollDown());
        try {
            const result = await rpc("/tour_copilote/chat", {
                messages: this.state.messages.map((m) => ({
                    role: m.role,
                    content: m.content,
                })),
                piece_jointe: piece,
            });
            if (result.error) {
                this.state.messages.push({
                    role: "assistant",
                    content: result.error,
                    isError: true,
                });
            } else if (result.async && result.jeton) {
                // MODE ASYNCHRONE (10/08, Merline) : le harnais peut mettre
                // plus d'une minute. On affiche l'attente, puis on relÃ¨ve
                // la vraie rÃ©ponse sur /tour_copilote/resultat.
                this.state.messages.push({
                    role: "assistant",
                    content: result.reply || "C'est parti, je m'en occupe.",
                });
                this.persist();
                await this._relever(result.jeton, this.state.messages);
            } else {
                this.state.messages.push({
                    role: "assistant",
                    content: result.reply,
                    actions: result.actions || [],
                });
            }
        } catch {
            this.state.messages.push({
                role: "assistant",
                content: "Erreur de communication avec le serveur.",
                isError: true,
            });
        }
        this.state.busy = false;
        this.persist();
        setTimeout(() => this.scrollDown());
    }

    async _relever(jeton, messages) {
        // Interroge /tour_copilote/resultat jusqu'a la reponse finale, puis
        // remplace le message d'attente (le dernier assistant) par la vraie
        // reponse. Meme principe que la bulle de l'accueil.
        let essais = 0;
        const maxi = 120; // ~6 minutes
        while (essais < maxi) {
            essais++;
            await new Promise((r) => setTimeout(r, 3000));
            try {
                const res = await rpc("/tour_copilote/resultat", {
                    jeton: jeton,
                    messages: messages.map((m) => ({
                        role: m.role,
                        content: m.content,
                    })),
                });
                if (res.etat === "termine") {
                    this._remplacerAttente(res.reply || "(reponse vide)",
                                           res.actions || []);
                    return;
                }
                if (res.etat === "echec") {
                    this._remplacerAttente(
                        res.erreur || "Chloe a rencontre un probleme", []);
                    return;
                }
            } catch {
                // pas encore pret : on reessaie
            }
        }
        this._remplacerAttente(
            "Toujours en cours... recharge la conversation pour voir "
            + "la reponse.", []);
    }

    _remplacerAttente(reponse, actions) {
        const attente = this.state.messages[this.state.messages.length - 1];
        if (attente && attente.role === "assistant" && !attente.actions
                && !attente.isError) {
            attente.content = reponse;
            attente.actions = actions || [];
        } else {
            this.state.messages.push({
                role: "assistant",
                content: reponse,
                actions: actions || [],
            });
        }
        this.persist();
        setTimeout(() => this.scrollDown());
    }
}

registry.category("main_components").add("TourCopilote", {
    Component: TourCopilote,
});
