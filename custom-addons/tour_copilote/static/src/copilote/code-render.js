/** @odoo-module **/

/**
 * DESIGN DU CODE (01/08) — la compétence par laquelle les réponses des
 * agents passent : le code (markdown, yaml, json, python…) s'affiche dans un
 * bloc propre avec son langage et un bouton « Copier », au lieu d'un texte
 * brut. Sans dépendance : un renderer maison, léger, auto-hébergé (aucun CDN).
 *
 * SÉCURITÉ : tout le contenu est échappé AVANT d'être assemblé ; la
 * coloration travaille sur le texte déjà échappé. Aucun morceau du contenu ne
 * devient du HTML exécutable.
 */

// ---------------------------------------------------------------------------
// Coloration minimale (sur le texte ÉCHAPPÉ). Volontairement modeste : de la
// couleur, pas un compilateur. Chaque langage colore strings, commentaires,
// et un ou deux mots-clés.
// ---------------------------------------------------------------------------
function echapper(s) {
    return String(s == null ? "" : s)
        .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function coloriser(code, lang) {
    let c = code;
    // Chaînes (guillemets droits déjà échappés en &quot;)
    c = c.replace(/(&quot;.*?&quot;|'[^'\n]*')/g, '<span class="tc-str">$1</span>');
    // Commentaires (# ...) — python, bash, yaml
    c = c.replace(/(^|\n)(\s*)(#[^\n]*)/g, '$1$2<span class="tc-cmt">$3</span>');
    if (lang === "yaml") {
        c = c.replace(/(^\s*)([\w.\-]+)(\s*:)/gm,
                      '$1<span class="tc-key">$2</span>$3');
    }
    if (lang === "json") {
        c = c.replace(/("(?:true|false|null)")/g, '<span class="tc-kw">$1</span>');
    }
    return c;
}

// ---------------------------------------------------------------------------
// Le cœur : texte -> HTML sûr, blocs de code transformés.
// ---------------------------------------------------------------------------
export function rendreContenu(texte) {
    const raw = String(texte == null ? "" : texte);
    const reBloc = /```([a-zA-Z0-9_+-]*)\n?([\s\S]*?)```/g;

    const blocCode = (lang, code) =>
        '<div class="tc-block">'
        + '<div class="tc-head"><span class="tc-lang">' + echapper(lang || "code")
        + '</span><button type="button" class="tc-copy" title="Copier le code">Copier</button></div>'
        + '<pre><code>' + coloriser(echapper(code), (lang || "").toLowerCase())
        + '</code></pre></div>';

    const paragraphe = (s) =>
        '<p class="tc-txt">' + (s ? echapper(s).replace(/\n/g, "<br/>") : "") + "</p>";

    let html = "";
    let dernier = 0;
    let m;
    while ((m = reBloc.exec(raw)) !== null) {
        if (m.index > dernier) {
            html += paragraphe(raw.slice(dernier, m.index));
        }
        html += blocCode(m[1], m[2]);
        dernier = m.index + m[0].length;
    }
    if (dernier < raw.length) {
        html += paragraphe(raw.slice(dernier));
    }
    return html || paragraphe(raw);
}

// ---------------------------------------------------------------------------
// Copier en un clic : délégation d'événement sur un conteneur. Le bouton
// lit le <code> voisin (pas d'attribut data — aucun contenu dans le HTML).
// ---------------------------------------------------------------------------
export function lierCopieurs(root) {
    if (!root) { return; }
    root.addEventListener("click", (ev) => {
        const bouton = ev.target.closest(".tc-copy");
        if (!bouton) {
            return;
        }
        const bloc = bouton.closest(".tc-block");
        const code = bloc && bloc.querySelector("code");
        const texte = code ? code.textContent : "";
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(texte).then(() => {
                bouton.textContent = "Copié ✓";
                setTimeout(() => {
                    bouton.textContent = "Copier";
                }, 1500);
            }).catch(() => {});
        } else {
            bouton.textContent = "Copier (Ctrl+C)";
        }
    });
}
