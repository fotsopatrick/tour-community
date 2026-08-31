/* Cockpit — lit /tour/cockpit/data et remplit la page. Aucune valeur en dur. */
(function () {
  "use strict";

  var tt = document.getElementById("tt");
  function showTT(html, x, y) { tt.innerHTML = html; tt.style.left = x + "px"; tt.style.top = y + "px"; tt.style.opacity = "1"; }
  function hideTT() { tt.style.opacity = "0"; }
  function esc(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }

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
  /* Choix persistant (09/08, Patrick) : même clé localStorage que l'accueil
     et les autres cockpits — le thème choisi vaut partout. */
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
  fetch("/tour/cockpit/data", { credentials: "same-origin" })
    .then(function (r) { return r.json(); })
    .then(render)
    .catch(function () {
      var n = document.getElementById("note");
      n.hidden = false;
      n.textContent = "Le robinet de chiffres ne répond pas (/tour/cockpit/data). Rien n'est inventé : la page reste vide.";
    });

  function render(d) {
    var etats = d.etats, projets = d.projets, parProjet = d.par_projet, total = d.total_taches;

    /* sous-titre + titre camembert */
    if (projets && total !== null) {
      document.getElementById("soustitre").textContent = projets.total + " projets · " + total + " tâches · en direct";
      document.getElementById("donut-titre").textContent = "État des " + total + " tâches";
    } else {
      document.getElementById("soustitre").textContent = "en direct";
    }

    /* ---------- bandes de vol ---------- */
    var strips = document.getElementById("strips");
    function strip(cls, lbl, val, pill, pillCls) {
      if (val === null || val === undefined) { return ""; } /* source absente -> case absente */
      return '<div class="strip ' + cls + '"><div class="lbl">' + lbl + '</div><div class="val">' + val + "</div>" +
        (pill ? '<span class="pill ' + pillCls + '">' + pill + "</span>" : "") + "</div>";
    }
    var pctAF = (etats && total) ? Math.round(etats.a_faire * 100 / total) + " % des " + total : "";
    strips.innerHTML =
      strip("blue", "Projets", projets ? projets.total : null,
        projets && projets.actifs !== null ? projets.actifs + " en activité · " + (projets.total - projets.actifs) + " en sommeil" : "", "flat") +
      strip("", "Tâches à faire", etats ? etats.a_faire : null, pctAF, "flat") +
      strip("ok", "En cours", etats ? etats.en_cours : null, "en ce moment", "up") +
      strip("crit", "Bloqué", etats ? etats.bloque : null, "à débloquer", "down");

    /* ---------- barres par projet ---------- */
    if (parProjet && parProjet.length) {
      var shown = parProjet.slice(0, 8);
      var svg = document.getElementById("bars");
      var W = 640, rowH = 34, top = 6, labelW = 170, R = 50;
      var H = top + shown.length * rowH + 6;
      svg.setAttribute("viewBox", "0 0 " + W + " " + H);
      var max = shown[0].n || 1, x0 = labelW, x1 = W - R, out = "";
      shown.forEach(function (p, i) {
        var y = top + i * rowH;
        var bw = Math.max(2, (p.n / max) * (x1 - x0));
        var col = i === 0 ? "var(--accent)" : "var(--c1)";
        var nom = p.nom.length > 24 ? p.nom.slice(0, 23) + "…" : p.nom;
        out += '<text class="axlabel" x="' + (labelW - 10) + '" y="' + (y + rowH / 2 + 3.5) + '" text-anchor="end" style="font-size:12px;fill:var(--ink)">' + esc(nom) + "</text>";
        out += '<rect x="' + x0 + '" y="' + (y + 6) + '" width="' + bw.toFixed(1) + '" height="' + (rowH - 14) + '" rx="4" fill="' + col + '" class="barrect" data-tip="' + esc(p.nom) + ' · <b>' + p.n + ' tâches</b>"/>';
        out += '<text class="axlabel" x="' + (x0 + bw + 7) + '" y="' + (y + rowH / 2 + 3.5) + '" style="font-size:12px;fill:var(--muted);font-family:var(--mono)">' + p.n + "</text>";
      });
      svg.innerHTML = out;
      hover(svg, ".barrect");
      if (parProjet.length > shown.length) {
        var note = document.getElementById("note");
        note.hidden = false;
        note.textContent = (parProjet.length - shown.length) + " autres projets avec des tâches ne sont pas dessinés (les 8 plus chargés le sont).";
      }
    }

    /* ---------- camembert d'etat ---------- */
    if (etats && total) {
      var segs = [
        { label: "À faire", n: etats.a_faire, col: "var(--c1)" },
        { label: "Fait", n: etats.fait, col: "var(--c2)" },
        { label: "Sans état", n: etats.sans_etat, col: "var(--neutral)" },
        { label: "En cours", n: etats.en_cours, col: "var(--c3)" },
        { label: "Bloqué", n: etats.bloque, col: "var(--c4)" }
      ].filter(function (s) { return s.n > 0; });
      var dsvg = document.getElementById("donut");
      var cx = 120, cy = 100, r = 74, sw = 26, a = -Math.PI / 2, dout = "";
      function pt(ang) { return [cx + r * Math.cos(ang), cy + r * Math.sin(ang)]; }
      segs.forEach(function (s) {
        var frac = s.n / total, a2 = a + frac * Math.PI * 2;
        var p1 = pt(a), p2 = pt(Math.min(a2, a + Math.PI * 2 - 0.0001));
        var large = frac > 0.5 ? 1 : 0;
        dout += '<path d="M' + p1[0].toFixed(1) + " " + p1[1].toFixed(1) + " A" + r + " " + r + " 0 " + large + " 1 " + p2[0].toFixed(1) + " " + p2[1].toFixed(1) +
          '" fill="none" stroke="' + s.col + '" stroke-width="' + sw + '" class="seg" data-tip="' + esc(s.label) + " · <b>" + s.n + "</b> (" + Math.round(frac * 100) + ' %)"/>';
        a = a2;
      });
      dout += '<text x="' + cx + '" y="' + (cy - 4) + '" text-anchor="middle" style="font-family:var(--mono);font-size:30px;font-weight:600;fill:var(--ink)">' + total + "</text>";
      dout += '<text x="' + cx + '" y="' + (cy + 16) + '" text-anchor="middle" class="axlabel" style="font-size:11px">tâches</text>';
      dsvg.innerHTML = dout;
      dsvg.querySelectorAll(".seg").forEach(function (p) {
        p.style.cursor = "pointer"; p.style.transition = "stroke-width .1s";
        p.addEventListener("mousemove", function (e) { p.setAttribute("stroke-width", sw + 5); showTT(p.getAttribute("data-tip"), e.clientX, e.clientY); });
        p.addEventListener("mouseleave", function () { p.setAttribute("stroke-width", sw); hideTT(); });
      });
      var list = document.getElementById("tasklist");
      list.innerHTML = "";
      segs.forEach(function (s) {
        var row = document.createElement("div"); row.className = "task";
        row.innerHTML = '<span class="tag" style="background:' + s.col + '"></span>' + esc(s.label) + '<span class="n">' + s.n + "</span>";
        list.appendChild(row);
      });
    }
  }

  function hover(svg, sel) {
    svg.querySelectorAll(sel).forEach(function (r) {
      r.style.cursor = "pointer";
      r.addEventListener("mousemove", function (e) { r.setAttribute("opacity", "0.82"); showTT(r.getAttribute("data-tip"), e.clientX, e.clientY); });
      r.addEventListener("mouseleave", function () { r.removeAttribute("opacity"); hideTT(); });
    });
  }
})();
