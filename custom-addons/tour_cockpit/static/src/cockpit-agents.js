/* Cockpit AGENTS — lit /tour/cockpit/data-agents et remplit la page.
 * Même langage que cockpit.js (horloge, thème, bulle d'info). Aucune valeur
 * en dur : source absente -> case vide, jamais un chiffre inventé. */
(function () {
  "use strict";

  var tt = document.getElementById("tt");
  function showTT(html, x, y) { tt.innerHTML = html; tt.style.left = x + "px"; tt.style.top = y + "px"; tt.style.opacity = "1"; }
  function hideTT() { tt.style.opacity = "0"; }
  function esc(s) { return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }

  /* ---------- horloge ---------- */
  var DAYS = ["dimanche","lundi","mardi","mercredi","jeudi","vendredi","samedi"];
  var MO = ["janvier","février","mars","avril","mai","juin","juillet","août","septembre","octobre","novembre","décembre"];
  function pad(n){ return (n < 10 ? "0" : "") + n; }
  function tick(){
    var d = new Date();
    document.getElementById("clock").textContent = pad(d.getHours())+":"+pad(d.getMinutes())+":"+pad(d.getSeconds());
    document.getElementById("date").textContent = DAYS[d.getDay()]+" "+d.getDate()+" "+MO[d.getMonth()]+" "+d.getFullYear();
  }
  tick(); setInterval(tick, 1000);

  /* ---------- theme ---------- */
  /* Choix persistant (09/08, Patrick) : même clé localStorage que l'accueil. */
  (function () {
    var root = document.documentElement, key = "tour-theme";
    var saved = null; try { saved = localStorage.getItem(key); } catch (e) {}
    if (saved === "light" || saved === "dark") { root.setAttribute("data-theme", saved); } else { root.setAttribute("data-theme", "light"); }
    var b = document.getElementById("themebtn");
    if (b) {
      b.addEventListener("click", function () {
        var cur = root.getAttribute("data-theme");
        if (!cur) { cur = "light"; }
        var next = cur === "dark" ? "light" : "dark";
        root.setAttribute("data-theme", next);
        try { localStorage.setItem(key, next); } catch (e) {}
      });
    }
  })();

  /* ---------- donnees ---------- */
  /* La page disait « mise à jour automatique » et ne rechargeait JAMAIS :
     le fetch n'était appelé qu'une fois. Corrigé le 06/08 — on relit le
     robinet toutes les REFRESH secondes (valeur donnée par le service). */
  var REFRESH_MS = 8000, minuteur = null;

  function charger() {
    fetch("/tour/cockpit/data-agents", { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        document.getElementById("note").hidden = true;
        if (d && d.ref) { REFRESH_MS = Math.max(3000, d.ref * 1000); }
        render(d);
      })
      .catch(function () {
        var n = document.getElementById("note");
        n.hidden = false;
        n.textContent = "Le robinet ne répond pas (/tour/cockpit/data-agents). Rien n'est inventé : la page reste vide.";
      });
  }
  charger();
  minuteur = setInterval(charger, REFRESH_MS);
  /* onglet caché : on arrête de tirer sur le serveur pour rien. */
  document.addEventListener("visibilitychange", function () {
    if (document.hidden) { clearInterval(minuteur); }
    else { charger(); minuteur = setInterval(charger, REFRESH_MS); }
  });

  /* ---------- preuve sociale (H3, 09/08) : nos chiffres réels ---------- */
  var NOMS = {
    missions_terminees: "missions réussies",
    missions_echouees: "missions échouées",
    fiches_reponses: "fiches de réponse",
    decisions_prises: "décisions prises",
    etudes_braignak: "études de Braignak",
    gabarits_circuits: "gabarits de circuit",
    garde_fous: "garde-fous",
    membres_equipe: "membres de l'équipe"
  };
  function chargerPreuve() {
    fetch("/tour/cockpit/data", { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        var el = document.getElementById("preuve-sociale");
        if (!el) { return; }
        var ps = d && d.preuve_sociale;
        if (!ps) { el.innerHTML = '<span class="empty">Le robinet ne répond pas — rien n\'est inventé.</span>'; return; }
        var html = '<div style="display:grid;grid-template-columns:repeat(2,1fr);gap:8px">';
        Object.keys(NOMS).forEach(function (k) {
          var v = ps[k];
          if (v == null) { return; }
          html += '<div class="card"><div class="c-n" style="font-size:20px">' + esc(v) + '</div>' +
                  '<div class="c-c" style="color:var(--muted)">' + esc(NOMS[k]) + "</div></div>";
        });
        html += "</div>";
        el.innerHTML = html;
      })
      .catch(function () {
        var el = document.getElementById("preuve-sociale");
        if (el) { el.innerHTML = '<span class="empty">Le robinet ne répond pas.</span>'; }
      });
  }
  chargerPreuve();
  setInterval(chargerPreuve, 60000);


  /* ---- LE PANNEAU DE ROUTE (11/08, demande de Patrick) -------------------
     Un triangle de danger, comme au bord d une route : on le voit de loin,
     on clique, on lit ce qui bloque et quoi faire. */
  function panneauDeRoute(diag, enCoursCount) {
    var hote = document.getElementById("panneau-blocage");
    if (!hote) {
      var strips = document.getElementById("strips");
      if (!strips) return;
      hote = document.createElement("section");
      hote.id = "panneau-blocage";
      hote.style.cssText = "margin:14px 0 0";
      strips.parentNode.insertBefore(hote, strips.nextSibling);
    }
    if (!diag) { hote.innerHTML = ""; return; }
    var etat = diag.etat || "inconnu";
    var soucis = diag.soucis || [];
    if (etat === "vert" || (etat !== "rouge" && etat !== "jaune" && !soucis.length)) {
      /* Rien a signaler — sauf si personne ne travaille ET qu on ne sait pas. */
      if (etat === "inconnu" && !enCoursCount) {
        hote.innerHTML = bandeau("#94a3b8", "?",
          "Personne ne travaille, et le diagnostic n a pas tourne",
          diag.resume || "", []);
        return;
      }
      hote.innerHTML = "";
      return;
    }
    var coul = etat === "rouge" ? "#e8776d" : "#d7a13e";
    var titre = etat === "rouge"
      ? "Quelque chose bloque l atelier"
      : (enCoursCount ? "Un point a regarder" : "Personne ne travaille — voici pourquoi");
    hote.innerHTML = bandeau(coul, "!", titre, diag.resume || "", soucis);
    var b = document.getElementById("panneau-blocage-bouton");
    var d = document.getElementById("panneau-blocage-detail");
    if (b && d) {
      b.onclick = function () {
        var ouvert = d.style.display !== "none";
        d.style.display = ouvert ? "none" : "block";
        b.textContent = ouvert ? "voir ce qui bloque" : "replier";
      };
    }
  }

  function bandeau(coul, signe, titre, resume, soucis) {
    var lignes = soucis.map(function (s) {
      return '<div style="margin:12px 0 0;padding:10px 12px;background:rgba(255,255,255,.03);' +
        'border-left:3px solid ' + (s.gravite === "rouge" ? "#e8776d" : "#d7a13e") + ';border-radius:6px">' +
        '<div style="font-weight:700;color:#fff;margin-bottom:4px">' + esc(s.quoi) + "</div>" +
        '<div style="color:#c9d6e2;line-height:1.6"><b style="color:#8ba1b5">pourquoi&#160;:</b> ' + esc(s.pourquoi) + "</div>" +
        '<div style="color:#c9d6e2;line-height:1.6"><b style="color:#8ba1b5">quoi faire&#160;:</b> ' + esc(s.quoi_faire) + "</div>" +
        "</div>";
    }).join("");
    return '<div style="display:flex;gap:14px;align-items:flex-start;background:' + coul +
      '14;border:1px solid ' + coul + '55;border-radius:12px;padding:14px 16px">' +
      '<div style="width:34px;height:30px;flex:0 0 auto;position:relative">' +
        '<div style="width:0;height:0;border-left:17px solid transparent;border-right:17px solid transparent;' +
        'border-bottom:30px solid ' + coul + '"></div>' +
        '<div style="position:absolute;left:0;top:9px;width:34px;text-align:center;font:700 15px ui-sans-serif,system-ui;color:#1a1200">' +
        signe + "</div></div>" +
      '<div style="flex:1;min-width:0">' +
        '<div style="font:700 15px ui-sans-serif,system-ui;color:#fff">' + esc(titre) + "</div>" +
        '<div style="color:#c9d6e2;margin-top:2px">' + esc(resume) + "</div>" +
        (soucis.length
          ? '<button id="panneau-blocage-bouton" style="margin-top:10px;background:none;border:1px solid ' +
            coul + '77;color:' + coul + ';border-radius:999px;padding:5px 14px;cursor:pointer;' +
            'font:600 12px ui-sans-serif,system-ui">voir ce qui bloque</button>' +
            '<div id="panneau-blocage-detail" style="display:none">' + lignes + "</div>"
          : "") +
      "</div></div>";
  }

  function dur(s) {
    if (s == null) { return ""; }
    s = Math.max(0, Math.round(s));
    if (s < 60) { return s + "s"; }
    var m = Math.floor(s / 60);
    return m + "m" + pad(s % 60);
  }

  function il_y_a(ts) {
    if (!ts) { return ""; }
    var delta = Math.max(0, Math.floor(Date.now() / 1000) - ts);
    if (delta < 60) { return "il y a " + delta + "s"; }
    if (delta < 3600) { return "il y a " + Math.floor(delta / 60) + "min"; }
    return "il y a " + Math.floor(delta / 3600) + "h" + pad(Math.floor((delta % 3600) / 60));
  }

  function render(d) {
    if (d && d.error) {
      var n = document.getElementById("note");
      n.hidden = false;
      n.textContent = d.error;
      return;
    }
    var enCours = d.en_cours || [], attente = d.attente || [], recentes = d.recentes || [];
    var pouls = d.pouls || {}, finis = d.vient_de_finir || [];
    var procs = d.processus_agents || [], pilotage = d.pilotage || [];
    var git = d.git || [], sante = d.sante || {}, fils = d.fils || [];
    var ram = d.ram_agents_mo || 0;

    /* sous-titre */
    document.getElementById("soustitre").textContent =
      enCours.length + " mission(s) à l'instant · " +
      (pouls.missions_10min || 0) + " sur les 10 dernières minutes · " +
      attente.length + " en attente · " + Math.round(ram) + " Mo d'agents";

    /* ---------- bandes de vol ---------- */
    var strips = document.getElementById("strips");
    function strip(cls, lbl, val, pill, pillCls) {
      if (val === null || val === undefined) { return ""; }
      return '<div class="strip ' + cls + '"><div class="lbl">' + lbl + '</div><div class="val">' + val + "</div>" +
        (pill ? '<span class="pill ' + pillCls + '">' + pill + "</span>" : "") + "</div>";
    }
    strips.innerHTML =
      strip("ok", "En cours", enCours.length,
        enCours.length ? enCours.length + " mission(s) à l'instant"
          : (pouls.vivant ? "l'atelier tourne — creux entre deux missions"
                          : "l'atelier ne produit plus"),
        enCours.length || pouls.vivant ? "up" : "down") +
      strip(pouls.vivant ? "ok" : "crit", "Pouls",
        (pouls.missions_10min == null ? "" : pouls.missions_10min) + ' <small>/ 10 min</small>',
        pouls.derniere_fin_il_y_a == null ? "aucune mission finie"
          : "dernière finie " + dur(pouls.derniere_fin_il_y_a) + " avant",
        pouls.vivant ? "up" : "down") +
      strip("blue", "En attente", attente.length, attente.length ? "à ramasser" : "", attente.length ? "flat" : "flat") +
      strip("", "RAM agents", Math.round(ram) + ' <small>Mo</small>', "processus mesurés", "flat") +
      strip("", "Pilotage", pilotage.length, pilotage.length ? "session(s) ouverte(s)" : "", pilotage.length ? "up" : "flat");

    panneauDeRoute(d.diagnostic, enCours.length);

    /* ---------- en cours ---------- */
    var enc = document.getElementById("encours");
    enc.innerHTML = "";
    enc.dataset.agents = JSON.stringify(enCours.map(function (m) {
      return { agent: m.agent || m.id, id: m.id, moteur: m.moteur,
               consigne: m.consigne || "", ecoule: m.ecoule, debut: m.debut,
               resume: m.resume || "" };
    }));
    if (typeof window.dessinerSalle === "function") window.dessinerSalle();
    if (!enCours.length) {
      /* Ne JAMAIS écrire « personne ne travaille » quand l'atelier vient de
         produire : ce serait la mesure qui ment, pas la tour qui dort. */
      enc.innerHTML = '<div class="empty">' + (
        pouls.vivant
          ? "Aucune mission à cette seconde précise — l'atelier tourne chaque minute et " +
            (pouls.derniere_fin_il_y_a == null ? "vient de produire"
              : "a rendu il y a " + dur(pouls.derniere_fin_il_y_a)) + "."
          : "L'atelier ne produit plus" +
            (pouls.derniere_fin_il_y_a == null ? "."
              : " — rien depuis " + dur(pouls.derniere_fin_il_y_a) + ".")
      ) + "</div>";
    }
    enCours.forEach(function (m) {
      var div = document.createElement("div");
      div.className = "card";
      div.innerHTML =
        '<div class="c-h"><span class="c-n">' + esc(m.agent || m.id) + '</span>' +
        '<span class="tag ok">' + esc(m.moteur) + "</span></div>" +
        (m.consigne ? '<div class="c-c">' + esc(m.consigne) + "</div>" : "") +
        '<div class="c-s">' + esc(m.id) + " · depuis " + dur(m.ecoule) +
        " · " + il_y_a(m.debut) + "</div>";
      enc.appendChild(div);
    });

    /* ---------- viennent de finir : la fin d'un span reste lisible ---------- */
    finis.forEach(function (m) {
      var div = document.createElement("div");
      div.className = "card fini";
      div.style.opacity = "0.72";
      div.innerHTML =
        '<div class="c-h"><span class="c-n">' + esc(m.agent || m.id) + '</span>' +
        '<span class="tag ' + (m.code ? "bad" : "flat") + '">' + esc(m.moteur) + "</span>" +
        '<span class="tag flat">terminée</span></div>' +
        (m.consigne ? '<div class="c-c">' + esc(m.consigne) + "</div>" : "") +
        '<div class="c-s">' + esc(m.id) + " · finie il y a " + dur(m.fini_il_y_a) +
        (m.duree == null ? "" : " · a duré " + dur(m.duree)) +
        (m.code == null ? "" : " · code " + esc(m.code)) + "</div>";
      enc.appendChild(div);
    });

    /* ---------- en attente ---------- */
    var att = document.getElementById("attente");
    att.innerHTML = "";
    if (!attente.length) {
      att.innerHTML = '<li class="empty">Rien en attente.</li>';
    }
    attente.forEach(function (m) {
      var li = document.createElement("li");
      li.innerHTML = '<span class="tag flat">' + esc(m.moteur) + "</span> " +
        '<b>' + esc(m.agent || "?") + "</b>" +
        (m.id ? ' <span class="mono">' + esc(m.id) + "</span>" : "") +
        ' — ' + (m.consigne ? esc(m.consigne).slice(0, 90) : "en attente") +
        ' <span class="mono">' + il_y_a(m.depose) + "</span>";
      att.appendChild(li);
    });

    /* ---------- dernieres missions ---------- */
    var rec = document.getElementById("recentes");
    rec.innerHTML = "";
    if (!recentes.length) { rec.innerHTML = '<tr><td colspan="5" class="empty">Rien.</td></tr>'; }
    recentes.forEach(function (r) {
      var ok = r.code === 0;
      var tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" + esc(r.heure) + "</td>" +
        "<td>" + esc(r.id) + "</td>" +
        "<td>" + esc(r.moteur) + "</td>" +
        "<td>" + esc(r.duree != null ? r.duree + "s" : "?") + "</td>" +
        '<td><span class="tag ' + (ok ? "ok" : "bad") + '">' + esc(ok ? "OK" : r.code) + "</span></td>";
      rec.appendChild(tr);
    });

    /* ---------- processus ---------- */
    var pro = document.getElementById("processus");
    pro.innerHTML = "";
    if (!procs.length) { pro.innerHTML = '<li class="empty">Aucun moteur actif.</li>'; }
    procs.forEach(function (p) {
      var li = document.createElement("li");
      li.className = "mono";
      li.textContent = p;
      pro.appendChild(li);
    });

    /* ---------- pilotage ---------- */
    var pil = document.getElementById("pilotage");
    pil.innerHTML = "";
    if (!pilotage.length) { pil.innerHTML = '<li class="empty">Aucune session de pilotage ouverte.</li>'; }
    pilotage.forEach(function (p) {
      var li = document.createElement("li");
      li.className = "mono";
      li.textContent = p;
      pil.appendChild(li);
    });

    /* ---------- git ---------- */
    var gitEl = document.getElementById("git");
    gitEl.innerHTML = "";
    if (!git.length) { gitEl.innerHTML = '<div class="empty">Rien.</div>'; }
    git.forEach(function (bloc) {
      var commits = (bloc.commits || []).slice(0, 5)
        .map(function (c) { return "<li class='mono'>" + esc(c) + "</li>"; }).join("");
      var dirty = bloc.modifies ? '<span class="dirty"> — ' + bloc.modifies + " fichier(s) non committés</span>" : "";
      var div = document.createElement("div");
      div.className = "card";
      div.innerHTML = '<div class="c-h"><span class="c-n">' + esc(bloc.nom) + '</span>' +
        '<span class="tag flat">' + esc(bloc.branche) + "</span>" + dirty + "</div>" +
        '<ul class="plat" style="margin-top:6px">' + commits + "</ul>";
      gitEl.appendChild(div);
    });

    /* ---------- sante ---------- */
    var san = document.getElementById("sante");
    san.innerHTML = "";
    Object.keys(sante).forEach(function (k) {
      var tr = document.createElement("tr");
      var v = sante[k];
      var ok = v === "ok" || (k === "sante-agents" && v === "filet");
      tr.innerHTML = "<td>" + esc(k) + "</td><td><span class='tag " + (ok ? "ok" : v === "(rien)" || !v ? "flat" : "bad") + "'>" + esc(v || "(rien)") + "</span></td>";
      san.appendChild(tr);
    });

    /* ---------- conversations ---------- */
    var fls = document.getElementById("fils");
    fls.innerHTML = "";
    if (!fils.length) { fls.innerHTML = '<li class="empty">Aucune conversation.</li>'; }
    fils.forEach(function (c) {
      var li = document.createElement("li");
      li.innerHTML = esc(c.slug) + ' <span class="mono" style="color:var(--muted)">' + il_y_a(c.mtime) + "</span>";
      fls.appendChild(li);
    });
  }
})();
