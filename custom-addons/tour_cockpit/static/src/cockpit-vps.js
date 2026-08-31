/* Cockpit VPS — lit /tour/cockpit/data-vps (service hôte etat-agents, 3211)
 * et remplit la page « le serveur respire encore ? » : RAM, disque, charge,
 * uptime, conteneurs. Même langage que cockpit.js/cockpit-agents.js.
 * Aucune valeur en dur : source absente -> case vide, jamais un chiffre
 * inventé. Recharge toutes les REFRESH secondes. */
(function () {
  "use strict";

  var REFRESH = 15; /* secondes entre deux relevés */

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
    var c = document.getElementById("clock");
    if (c) { c.textContent = pad(d.getHours())+":"+pad(d.getMinutes())+":"+pad(d.getSeconds()); }
    var dt = document.getElementById("date");
    if (dt) { dt.textContent = DAYS[d.getDay()]+" "+d.getDate()+" "+MO[d.getMonth()]+" "+d.getFullYear(); }
  }
  tick(); setInterval(tick, 1000);

  /* ---------- theme ---------- */
  /* Choix persistant (09/08, Patrick) : même clé localStorage que l'accueil. */
  var rootEl = document.documentElement, tKey = "tour-theme";
  var tSaved = null; try { tSaved = localStorage.getItem(tKey); } catch (e) {}
  if (tSaved === "light" || tSaved === "dark") { rootEl.setAttribute("data-theme", tSaved); }
  var btn = document.getElementById("themebtn");
  if (btn) {
    btn.addEventListener("click", function () {
      var cur = rootEl.getAttribute("data-theme");
      if (!cur) { cur = "light"; }
      var next = cur === "dark" ? "light" : "dark";
      rootEl.setAttribute("data-theme", next);
      try { localStorage.setItem(tKey, next); } catch (e) {}
    });
  }

  /* ---------- aides ---------- */
  function octets(v, dec) {
    if (v == null || isNaN(v)) { return ""; }
    var e = dec || 0;
    if (v >= 1024*1024*1024) { return (v / (1024*1024*1024)).toFixed(e) + " Go"; }
    if (v >= 1024*1024) { return (v / (1024*1024)).toFixed(e) + " Mo"; }
    if (v >= 1024) { return (v / 1024).toFixed(e) + " Ko"; }
    return Math.round(v) + " o";
  }
  function pct(part, total) {
    if (total == null || total <= 0) { return null; }
    return Math.min(100, Math.max(0, part / total * 100));
  }
  function uptime(s) {
    if (s == null || isNaN(s)) { return ""; }
    s = Math.floor(s);
    var j = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600),
        m = Math.floor((s % 3600) / 60), sec = s % 60;
    return j + " j " + pad(h) + ":" + pad(m) + ":" + pad(sec);
  }
  function classe(p) {
    if (p == null) { return ""; }
    if (p >= 90) { return " crit"; }
    if (p >= 70) { return " warn"; }
    return "";
  }
  function jauge(part, total, el) {
    if (!el) { return; }
    var p = pct(part, total);
    el.innerHTML = p == null
      ? '<div class="empty">(source absente)</div>'
      : '<div class="j-l"><span>' + esc(octets(part)) + " / " + esc(octets(total)) +
        '</span><span>' + p.toFixed(1) + " %</span></div>" +
        '<div class="j-b"><div class="j-f' + classe(p) + '" style="width:' + p.toFixed(1) + '%"></div></div>';
  }

  function alerte(texte) {
    var n = document.getElementById("note");
    if (!n) { return; }
    n.hidden = !texte;
    n.textContent = texte || "";
  }

  /* ---------- remplissage ---------- */
  var PERIODE = "jour"; /* jour | semaine | mois */
  var usage = [];
  var btns = document.querySelectorAll(".periodes-btn");
  if (btns.length) {
    btns.forEach(function (b) {
      b.addEventListener("click", function () {
        btns.forEach(function (x) { x.classList.remove("actif"); });
        b.classList.add("actif");
        PERIODE = b.getAttribute("data-per");
        renderUsage();
      });
    });
  }

  function groupe(unit) {
    var out = {};
    usage.forEach(function (u) {
      var d = new Date((u.ts || 0) * 1000), cle;
      if (unit === "jour") {
        cle = u.date;
      } else if (unit === "semaine") {
        var t = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
        var jr = ((t.getUTCDay() + 6) % 7) + 1;
        t.setUTCDate(t.getUTCDate() - jr + 3);
        cle = "S" + Math.round((t - new Date(Date.UTC(t.getUTCFullYear(), 0, 4))) / (86400000 * 7) + 0.5);
      } else {
        cle = d.toLocaleDateString("fr-FR", { month: "short", year: "2-digit" });
      }
      if (!out[cle]) out[cle] = { n: 0, cpu: 0, mem: 0 };
      out[cle].n++; out[cle].cpu += (u.cpu || 0); out[cle].mem += (u.mem || 0);
    });
    return Object.keys(out).sort().map(function (cle) {
      var g = out[cle];
      return { cle: cle, cpu: g.cpu / g.n, mem: g.mem / g.n };
    });
  }

  function renderUsage() {
    var el = document.getElementById("usage-barchart");
    if (!el) { return; }
    var serie = groupe(PERIODE);
    if (!serie.length) {
      el.innerHTML = '<div class="empty">(source absente — sar ne répond pas)</div>';
      return;
    }
    el.innerHTML = serie.map(function (g) {
      var hc = Math.max(2, Math.round((g.cpu || 0) * 0.6));
      var hm = Math.max(2, Math.round((g.mem || 0) * 0.6));
      return '<div class="bar" title="' + esc(g.cle) + " — CPU " + g.cpu.toFixed(0) +
        "%, RAM " + g.mem.toFixed(0) + '%">' +
        '<div class="b cpu" style="height:' + hc + 'px"></div>' +
        '<div class="b mem" style="height:' + hm + 'px"></div>' +
        '<div class="lb">' + esc(g.cle) + "</div></div>";
    }).join("");
  }

  function render(d) {
    if (!d || d.error) {
      alerte((d && d.error) || "Le robinet ne répond pas (/tour/cockpit/data-vps). Rien n'est inventé : la page reste vide.");
      return;
    }
    alerte("");

    var ram = d.ram || {}, disque = d.disque || {}, charge = d.charge || [];
    var conteneurs = d.conteneurs || [];
    var ramPct = pct((ram.total || 0) - (ram.dispo || 0), ram.total);
    var disquePct = pct(disque.utilise, disque.total);
    var charge1 = charge[0];

    /* sous-titre */
    var st = document.getElementById("soustitre");
    if (st) {
      st.textContent = (ramPct != null ? "RAM " + ramPct.toFixed(1) + " %" : "RAM ?") +
        " · disque " + (disquePct != null ? disquePct.toFixed(1) + " %" : "?") +
        " · " + conteneurs.length + " conteneur(s) · relevé toutes les " + REFRESH + " s";
    }

    /* bandes de vol */
    var strips = document.getElementById("strips");
    function strip(cls, lbl, val, pill, pillCls) {
      if (val === null || val === undefined) { return ""; }
      return '<div class="strip ' + cls + '"><div class="lbl">' + lbl + '</div><div class="val">' + val + "</div>" +
        (pill ? '<span class="pill ' + pillCls + '">' + pill + "</span>" : "") + "</div>";
    }
    if (strips) {
      strips.innerHTML =
        strip("ok", "RAM", ramPct != null ? ramPct.toFixed(1) + ' <small>%</small>' : "?", "mémoire vive", ramPct >= 90 ? "down" : "up") +
        strip("", "Disque", disquePct != null ? disquePct.toFixed(1) + ' <small>%</small>' : "?", "racine /", disquePct >= 90 ? "down" : "flat") +
        strip("blue", "Charge CPU", charge1 != null ? charge1.toFixed(2) : "?", "moyenne 1 min", charge1 >= 3.2 ? "down" : "flat") +
        strip("", "Conteneurs", conteneurs.length, conteneurs.length + " en service", conteneurs.length ? "up" : "down");
    }

    /* RAM */
    jauge((ram.total || 0) - (ram.dispo || 0), ram.total, document.getElementById("ram-jauge"));
    var rd = document.getElementById("ram-detail");
    if (rd) {
      rd.innerHTML =
        "<tr><td>Total</td><td class='mono'>" + esc(octets(ram.total)) + "</td></tr>" +
        "<tr><td>Utilisée</td><td class='mono'>" + esc(octets((ram.total || 0) - (ram.dispo || 0))) + "</td></tr>" +
        "<tr><td>Disponible</td><td class='mono'>" + esc(octets(ram.dispo)) + "</td></tr>";
    }

    /* disque */
    jauge(disque.utilise, disque.total, document.getElementById("disque-jauge"));
    var dd = document.getElementById("disque-detail");
    if (dd) {
      dd.innerHTML =
        "<tr><td>Capacité</td><td class='mono'>" + esc(octets(disque.total)) + "</td></tr>" +
        "<tr><td>Utilisé</td><td class='mono'>" + esc(octets(disque.utilise)) + "</td></tr>" +
        "<tr><td>Libre</td><td class='mono'>" + esc(octets((disque.total || 0) - (disque.utilise || 0))) + "</td></tr>";
    }

    /* charge CPU */
    var cd = document.getElementById("charge-detail");
    if (cd) {
      var noms = ["1 min", "5 min", "15 min"];
      cd.innerHTML = charge.map(function (v, i) {
        var p = Math.min(100, v / 4 * 100); /* 4 cœurs = plein */
        return '<tr><td>' + noms[i] + '</td><td class="mono">' + v.toFixed(2) +
          '</td><td style="width:38%"><div class="j-b"><div class="j-f' +
          classe(p) + '" style="width:' + p.toFixed(1) + '%"></div></div></td></tr>';
      }).join("") || '<tr><td colspan="3" class="empty">(source absente)</td></tr>';
    }

    /* uptime */
    var ud = document.getElementById("uptime-detail");
    if (ud) { ud.textContent = uptime(d.uptime) || "(source absente)"; }

    /* conteneurs */
    var tb = document.getElementById("conteneurs");
    if (tb) {
      tb.innerHTML = "";
      if (!conteneurs.length) {
        tb.innerHTML = '<tr><td colspan="4" class="empty">(aucun conteneur relevé)</td></tr>';
      }
      conteneurs.forEach(function (c) {
        var memPct = parseFloat(String(c.mem_pct || "").replace("%", ""));
        var tr = document.createElement("tr");
        tr.innerHTML =
          "<td>" + esc(c.nom) + "</td>" +
          '<td class="mono">' + esc(c.cpu) + "</td>" +
          '<td class="mono">' + esc(String(c.mem || "").split("/")[0]) + "</td>" +
          '<td><span class="tag ' + (memPct >= 50 ? "bad" : "ok") + '">' + esc(c.mem_pct || "?") + "</span></td>";
        tr.style.cursor = "default";
        tr.addEventListener("mousemove", function (e) {
          showTT("<b>" + esc(c.nom) + "</b><br>CPU " + esc(c.cpu) +
            " · RAM " + esc(c.mem), e.clientX, e.clientY);
        });
        tr.addEventListener("mouseleave", hideTT);
        tb.appendChild(tr);
      });
    }

    /* ports ouverts + tranches fermées */
    var po = document.getElementById("ports");
    if (po) {
      var ports = d.ports || {};
      var ouverts = ports.ouverts || [];
      po.innerHTML = ouverts.length
        ? ouverts.map(function (x) {
            return "<tr><td class='mono'>" + esc(x.port) + "</td><td>" +
              esc(x.service) + "</td><td class='mono'>" + esc(x.adresse) +
              "</td></tr>";
          }).join("")
        : '<tr><td colspan="3" class="empty">(source absente)</td></tr>';
      var pf = document.getElementById("ports-fermes");
      if (pf) {
        var fermes = ports.fermes || [];
        pf.textContent = fermes.length
          ? "Fermés : " + fermes.map(function (r) { return r[0] + "–" + r[1]; }).join(", ")
          : "Aucune plage fermée relevée";
      }
    }

    /* fuites détectées */
    var fy = document.getElementById("fuyards");
    if (fy) {
      var fuyards = d.fuyards || [];
      if (!fuyards.length) {
        fy.innerHTML = '<tr><td colspan="5" class="empty">Aucune fuite détectée.</td></tr>';
      } else {
        fy.innerHTML = fuyards.map(function (f) {
          return "<tr><td class='mono'>" + esc(f.pid) + "</td><td>" + esc(f.user) +
            "</td><td class='mono'>" + esc(f.duree) + "</td><td class='mono'>" +
            esc(f.mo != null ? f.mo + " Mo" : "?") + "</td><td><span class='tag bad'>" +
            esc(f.raison) + "</span></td></tr>";
        }).join("");
      }
    }

    /* connexions des utilisateurs VPS1 & VPS2 */
    var cx = document.getElementById("connexions");
    if (cx) {
      var connexions = d.connexions || {};
      var lignes = "";
      ["vps1", "vps2"].forEach(function (cle) {
        var bloc = connexions[cle];
        if (!bloc || !bloc.users || !bloc.users.length) {
          return;
        }
        var machine = bloc.machine || cle;
        bloc.users.forEach(function (u) {
          var dte = u.date || "jamais";
          var date = dte === "jamais" ? '<span class="tag bad">jamais</span>'
            : '<span class="mono">' + esc(dte.replace("T", " ").slice(0, 19)) + "</span>";
          var depuis = u.ip ? '<span class="mono">' + esc(u.ip) + "</span>" : "—";
          var methode = u.methode || "—";
          lignes += "<tr><td class='mono'>" + esc(machine) + "</td><td>" +
            esc(u.user) + "</td><td>" + date + "</td><td>" + depuis +
            "</td><td>" + esc(methode) + "</td></tr>";
        });
      });
      cx.innerHTML = lignes ||
        '<tr><td colspan="5" class="empty">(source absente — auth.log illisible)</td></tr>';
      var cn = document.getElementById("connexions-note");
      if (cn) {
        cn.textContent = connexions && connexions.vps2 && !(connexions.vps2.users && connexions.vps2.users.length)
          ? "VPS2 : source absente (clé d'accès absente ou serveur injoignable)"
          : "";
      }
    }

    /* utilisation historique */
    usage = d.usage || [];
    renderUsage();
  }

  /* ---------- boucle ---------- */
  function releve() {
    fetch("/tour/cockpit/data-vps", { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(render)
      .catch(function () {
        alerte("Le robinet ne répond pas (/tour/cockpit/data-vps). Rien n'est inventé : la page reste vide.");
      });
  }
  releve();
  setInterval(releve, REFRESH * 1000);
})();
