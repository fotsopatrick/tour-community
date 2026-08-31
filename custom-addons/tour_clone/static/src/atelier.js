/* L'atelier du clone — le débat, côté écran.
 *
 * Rien d'astucieux ici : on tire un sujet, on parle, il répond. La seule
 * subtilité est le désaccord, qu'on marque visuellement — parce que c'est le
 * moment qui compte. Un débat sans désaccord n'a rien appris à personne. */
(function () {
  var debatId = null, occupe = false;
  var fil = document.getElementById("cl-fil");
  var sujet = document.getElementById("cl-sujet");
  var texte = document.getElementById("cl-texte");
  var bEnvoyer = document.getElementById("cl-envoyer");
  var bNouveau = document.getElementById("cl-nouveau");
  var bClore = document.getElementById("cl-clore");
  var theme = document.getElementById("cl-theme");

  function jsonrpc(url, params) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ jsonrpc: "2.0", method: "call", params: params || {} }),
    }).then(function (r) { return r.json(); })
      .then(function (j) {
        if (j.error) throw new Error(j.error.data ? j.error.data.message : "erreur");
        return j.result || {};
      });
  }

  function ligne(qui, contenu, desaccord) {
    var d = document.createElement("div");
    d.className = "cl-ligne " + (qui === "moi" ? "cl-moi" : "cl-lui")
                + (desaccord ? " cl-desaccord" : "");
    var n = document.createElement("span");
    n.className = "cl-nom";
    n.textContent = qui === "moi" ? "toi >" : "clone >";
    d.appendChild(n);
    d.appendChild(document.createTextNode(contenu));
    fil.appendChild(d);
    fil.scrollTop = fil.scrollHeight;
    return d;
  }

  function attente() {
    var d = document.createElement("div");
    d.className = "cl-ligne cl-lui cl-curseur";
    d.innerHTML = "<span class='cl-nom'>clone &gt;</span>";
    fil.appendChild(d);
    fil.scrollTop = fil.scrollHeight;
    return d;
  }

  bNouveau.addEventListener("click", function () {
    if (occupe) return;
    occupe = true;
    fil.innerHTML = "";
    sujet.style.display = "none";
    var att = attente();
    jsonrpc("/tour/clone/sujet", { theme: theme.value || null })
      .then(function (r) {
        att.remove();
        occupe = false;
        if (r.erreur) { ligne("lui", r.erreur); return; }
        debatId = r.debat_id;
        bClore.disabled = false;
        sujet.style.display = "";
        sujet.innerHTML =
          "<div style='color:#a8ffb4'>" + (r.titre || "").replace(/</g, "&lt;") + "</div>" +
          "<div style='color:#5d8a63;font-size:.85rem;margin-top:.3rem'>" +
          (r.resume || "").replace(/</g, "&lt;") + "</div>" +
          (r.lien ? "<div style='margin-top:.4rem'><a href='" + r.lien +
                    "' target='_blank' rel='noopener'>" +
                    (r.source || "la source") + " ↗</a></div>" : "");
        // Il parle en premier : il donne son avis avant qu'on lui demande.
        envoyer("");
      })
      .catch(function (e) { att.remove(); occupe = false; ligne("lui", "✗ " + e.message); });
  });

  function envoyer(msg) {
    if (!debatId || occupe) return;
    occupe = true;
    bEnvoyer.disabled = true;
    var att = attente();
    jsonrpc("/tour/clone/parler", { debat_id: debatId, message: msg })
      .then(function (r) {
        att.remove();
        occupe = false;
        bEnvoyer.disabled = false;
        if (r.erreur) { ligne("lui", "✗ " + r.erreur); return; }
        ligne("lui", r.reponse, r.desaccord);
      })
      .catch(function (e) {
        att.remove(); occupe = false; bEnvoyer.disabled = false;
        ligne("lui", "✗ " + e.message);
      });
  }

  function envoyerSaisie() {
    var m = texte.value.trim();
    if (!m || !debatId) return;
    texte.value = "";
    ligne("moi", m);
    envoyer(m);
  }

  bEnvoyer.addEventListener("click", envoyerSaisie);
  texte.addEventListener("keydown", function (ev) {
    if (ev.key === "Enter" && !ev.shiftKey) { ev.preventDefault(); envoyerSaisie(); }
  });

  bClore.addEventListener("click", function () {
    if (!debatId || occupe) return;
    occupe = true;
    var att = attente();
    jsonrpc("/tour/clone/clore", { debat_id: debatId })
      .then(function (r) {
        att.remove();
        occupe = false;
        bClore.disabled = true;
        var d = document.createElement("div");
        d.className = "cl-ligne";
        d.style.cssText = "border:1px dashed #3d6b45;padding:.7rem .9rem;" +
          "margin-top:1rem;color:#a8ffb4;background:rgba(0,60,20,.2)";
        d.textContent = "▪ Ce que le clone en retient : " +
          (r.lecon || "(rien de retenu)");
        fil.appendChild(d);
        fil.scrollTop = fil.scrollHeight;
        debatId = null;
      })
      .catch(function (e) { att.remove(); occupe = false; ligne("lui", "✗ " + e.message); });
  });
})();
