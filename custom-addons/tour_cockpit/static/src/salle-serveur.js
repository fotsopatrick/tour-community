/* La salle serveur 2D (refonte 09/08, Patrick) — une vraie salle de serveurs,
 * style jeu. Clic sur un agent -> GRAND popup : recap clair en cartes et le
 * texte COMPLET de ce qu'il fait, sans bouton « tout voir ». Onglets :
 * Ce qu'il fait / Activite (graphe).
 */
(function () {
  var PALETTE = ['#4f8ef7','#e868a8','#3fa63f','#c9a227','#e06040','#8a5ae0',
                 '#2bb8c9','#d8732a','#7a9a4a','#b04090','#5a6ae0','#c04040',
                 '#2fae5a','#d0b040','#4090b0','#b060c0','#60b060','#f59e0b'];
  function couleurDe(nom) {
    var h = 0;
    for (var i = 0; i < nom.length; i++) h = (h * 31 + nom.charCodeAt(i)) >>> 0;
    return PALETTE[h % PALETTE.length];
  }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function dur(s) {
    if (s == null || isNaN(s)) return "?";
    s = Math.max(0, Math.round(s));
    if (s < 60) return s + " s";
    if (s < 3600) return Math.floor(s / 60) + " min";
    return Math.floor(s / 3600) + " h " + Math.floor((s % 3600) / 60) + " min";
  }

  var SERVEURS = [
    { nom: "VPS1 — la tour", x: 0.06, y: 0.16, w: 0.40, h: 0.52 },
    { nom: "VPS2 — réserve", x: 0.54, y: 0.16, w: 0.40, h: 0.52 }
  ];
  function led(ctx, x, y, on, c) {
    ctx.fillStyle = on ? (c || "#5cf27d") : "rgba(255,255,255,.10)";
    ctx.beginPath();
    ctx.arc(x, y, 2.2, 0, Math.PI * 2);
    ctx.fill();
    if (on) {
      ctx.fillStyle = "rgba(255,255,255,.25)";
      ctx.beginPath();
      ctx.arc(x, y, 4.5, 0, Math.PI * 2);
      ctx.fill();
    }
  }
  function rack(ctx, x, y, w, h, nom, clignote) {
    ctx.fillStyle = "#10161f";
    ctx.fillRect(x, y, w, h);
    ctx.strokeStyle = "rgba(255,255,255,.22)";
    ctx.strokeRect(x + .5, y + .5, w - 1, h - 1);
    ctx.fillStyle = "rgba(255,255,255,.03)";
    ctx.fillRect(x, y, w, 3);
    var n = 4, uh = (h - 14) / n;
    for (var i = 0; i < n; i++) {
      var uy = y + 12 + i * uh;
      ctx.fillStyle = i % 2 ? "#182230" : "#1c2936";
      ctx.fillRect(x + 6, uy + 2, w - 12, uh - 5);
      ctx.strokeStyle = "rgba(255,255,255,.08)";
      ctx.strokeRect(x + 6, uy + 2, w - 12, uh - 5);
      ctx.fillStyle = "rgba(120,200,160,.18)";
      ctx.fillRect(x + 9, uy + 5, (w - 18) * 0.6, 3);
      ctx.fillRect(x + 9, uy + 10, (w - 18) * 0.35, 3);
      led(ctx, x + w - 16, uy + 6, true, "#5cf27d");
      led(ctx, x + w - 9, uy + 6, Math.floor(clignote + i) % 2 === 0, "#f5a623");
      led(ctx, x + w - 16, uy + 12, true, "#4f8ef7");
    }
    ctx.fillStyle = "#0c1118";
    ctx.fillRect(x, y, w, 12);
    ctx.fillStyle = "rgba(255,255,255,.8)";
    ctx.font = "bold 10px ui-monospace, monospace";
    ctx.textAlign = "left";
    ctx.fillText(nom, x + 8, y + 9);
    ctx.strokeStyle = "rgba(255,255,255,.15)";
    ctx.beginPath();
    ctx.arc(x + w - 24, y + 10, 5, 0, Math.PI * 2);
    ctx.stroke();
    ctx.fillStyle = "rgba(255,255,255,.12)";
    ctx.fillRect(x + w - 25, y + 9, 2, 2);
    ctx.textAlign = "left";
  }
  function bonhomme(ctx, px, py, couleur, nom, actif) {
    var o = ctx.createRadialGradient(px, py + 8, 2, px, py + 8, 12);
    o.addColorStop(0, "rgba(0,0,0,.4)");
    o.addColorStop(1, "rgba(0,0,0,0)");
    ctx.fillStyle = o;
    ctx.beginPath();
    ctx.ellipse(px, py + 8, 10, 4, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = couleur;
    ctx.beginPath();
    ctx.arc(px, py, 7, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#f0c8a0";
    ctx.beginPath();
    ctx.arc(px, py - 8, 5, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#3a2a20";
    ctx.beginPath();
    ctx.arc(px, py - 9, 5, Math.PI, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#fff";
    ctx.fillRect(px - 2, py - 9, 1.5, 1.5);
    ctx.fillRect(px + 1, py - 9, 1.5, 1.5);
    ctx.strokeStyle = couleur;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(px, py - 9, 7, Math.PI * 1.1, Math.PI * 1.9);
    ctx.stroke();
    ctx.lineWidth = 1;
    if (actif) {
      ctx.fillStyle = "rgba(92,242,125,.15)";
      ctx.beginPath();
      ctx.arc(px, py, 13, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.fillStyle = "rgba(255,255,255,.9)";
    ctx.font = "bold 10px ui-monospace, monospace";
    ctx.textAlign = "center";
    ctx.fillText(nom, px, py + 24);
    ctx.textAlign = "left";
  }
  function salleServeur(el, largeur, hauteur, clignote) {
    el.width = largeur;
    el.height = hauteur;
    var ctx = el.getContext("2d");
    ctx.clearRect(0, 0, largeur, hauteur);
    var g = ctx.createLinearGradient(0, 0, 0, hauteur);
    g.addColorStop(0, "#0a1018");
    g.addColorStop(0.85, "#131b28");
    g.addColorStop(1, "#0c121c");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, largeur, hauteur);
    ctx.fillStyle = "rgba(255,255,255,.02)";
    ctx.fillRect(0, hauteur * 0.78, largeur, 2);
    ctx.strokeStyle = "rgba(255,255,255,.03)";
    for (var i = 0; i < 6; i++) {
      ctx.beginPath();
      ctx.moveTo(0, hauteur * 0.78 + i * 10);
      ctx.lineTo(largeur, hauteur * 0.78 + i * 10);
      ctx.stroke();
    }
    SERVEURS.forEach(function (srv, k) {
      rack(ctx, srv.x * largeur, srv.y * hauteur, srv.w * largeur, srv.h * hauteur,
           srv.nom, clignote + k);
    });
    ctx.strokeStyle = "rgba(90,160,255,.25)";
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(0.40 * largeur, 0.42 * hauteur);
    ctx.quadraticCurveTo(0.5 * largeur, 0.34 * hauteur, 0.54 * largeur, 0.42 * hauteur);
    ctx.stroke();
    ctx.setLineDash([]);
    return ctx;
  }

  var selection = null;
  var positions = [];
  function lireDonnees() {
    var enc = document.getElementById("encours");
    var agents = [];
    if (enc && enc.dataset && enc.dataset.agents) {
      try { agents = JSON.parse(enc.dataset.agents); } catch (e) {}
    }
    var compteurs = { en_cours: agents.length, en_attente: 0, finies: 0 };
    var att = document.getElementById("attente");
    if (att) compteurs.en_attente = att.querySelectorAll("li").length;
    var rec = document.getElementById("recentes");
    if (rec) compteurs.finies = rec.querySelectorAll("tr").length;
    return { agents: agents, compteurs: compteurs };
  }
  function metrique(lbl, val) {
    return '<div style="flex:1;min-width:120px;background:rgba(255,255,255,.04);' +
      'border:1px solid rgba(255,255,255,.08);border-radius:10px;padding:10px 12px">' +
      '<div style="font:10px ui-monospace,monospace;text-transform:uppercase;letter-spacing:.1em;color:#7e93a8;margin-bottom:3px">' +
      lbl + '</div><div style="font:14px ui-monospace,monospace;color:#fff;font-weight:600">' + val + "</div></div>";
  }
  function grapheBarres(compteurs, couleur) {
    var max = Math.max(1, compteurs.en_cours, compteurs.en_attente, compteurs.finies);
    function bar(v, lbl, c) {
      return '<div style="display:flex;align-items:center;gap:10px;margin:6px 0">' +
        '<span style="width:96px;font:11px ui-monospace,monospace;color:#94a3b8">' + lbl + "</span>" +
        '<div style="flex:1;background:rgba(255,255,255,.05);border-radius:6px;height:16px;overflow:hidden">' +
          '<div style="width:' + Math.round(v / max * 100) + '%;height:100%;background:' + c + '"></div>' +
        '</div><b style="width:26px;text-align:right;color:#fff">' + v + "</b></div>";
    }
    return bar(compteurs.en_cours, "En cours", couleur || "#5cf27d") +
           bar(compteurs.en_attente, "En attente", "#f5a623") +
           bar(compteurs.finies, "Finies récemment", "#4f8ef7");
  }


  /* --- LIRE LA VRAIE MISSION (11/08, Raphael) -----------------------------
     Le service sert deja tout ; on le montrait juste mal. */

  function sujetDeMission(p) {
    var r = String(p.resume || "");
    var m = r.match(/SUJET\s*:\s*(.+)$/i);
    if (m) return m[1].trim().slice(0, 120);
    if (r) return r.trim().slice(0, 120);
    return p.id ? String(p.id) : "mission sans sujet";
  }

  function nomDeAgent(p) {
    /* Le service renvoie parfois « === » : il a pris la ligne de separation
       au lieu du nom. Le nom est dans la consigne : « Tu es Wags, ... ». */
    var a = String(p.agent || "").trim();
    if (a && a.length > 1 && /[A-Za-zÀ-ÿ]/.test(a)) return a;
    var m = String(p.consigne || "").match(/Tu es ([^,\n.]{2,40})/i);
    return m ? m[1].trim() : String(p.moteur || "agent");
  }

  function heureLisible(t) {
    var n = Number(t);
    if (!n) return "?";
    var d = new Date(n * (n > 1e11 ? 1 : 1000));
    return d.toLocaleTimeString("fr-FR", {hour: "2-digit", minute: "2-digit", second: "2-digit"});
  }

  function detailMission(p) {
    /* On decoupe la consigne en trois blocs utiles plutot que de la vomir
       en entier — et on ne remplace JAMAIS un contenu reel par du texte
       generique : le vide se dit, il ne se maquille pas. */
    var c = String(p.consigne || "").replace(/\r/g, "");
    var bouts = [];
    var sujet = sujetDeMission(p);
    bouts.push("CE QU ON LUI DEMANDE\n" + sujet);

    var prod = c.match(/(?:REGLE DE LIVRAISON|LIVRABLE|DOIT PRODUIRE|TU DOIS RENDRE)\s*:?\s*([\s\S]{0,400}?)(?:\n\n|===)/i);
    bouts.push("CE QUE LA MISSION DOIT PRODUIRE\n" +
      (prod ? prod[1].trim() : "pas ecrit dans la consigne"));

    var souci = c.match(/(?:PROBLEME|BLOCAGE|ATTENTION|ERREUR)\s*:?\s*([\s\S]{0,300}?)(?:\n\n|===)/i);
    bouts.push("CE QUI COINCE\n" + (souci ? souci[1].trim() : "rien de signale"));

    if (c) bouts.push("LA CONSIGNE COMPLETE\n" + c.slice(0, 2500));
    return bouts.join("\n\n");
  }

  function majPopup(posSel) {
    var ov = document.getElementById("popup-agent-overlay");
    if (!posSel) { if (ov) ov.style.display = "none"; return; }
    var d = lireDonnees();
    if (!ov) {
      ov = document.createElement("div");
      ov.id = "popup-agent-overlay";
      ov.style.cssText = "position:fixed;inset:0;background:rgba(2,8,16,.72);" +
        "z-index:70;display:flex;align-items:center;justify-content:center;padding:16px;";
      ov.addEventListener("click", function (e) { if (e.target === ov) { selection = null; ov.style.display = "none"; } });
      document.body.appendChild(ov);
    }
    var coul = couleurDe(posSel.agent);
    var texteComplet = detailMission(posSel);
    if (!texteComplet || texteComplet.length < 15) {
        texteComplet = "Aucune consigne lisible pour cette mission — le service ne l a pas fournie.";
    }
    var metriques =
      metrique("Mission", esc(sujetDeMission(posSel))) +
      metrique("Moteur", esc(posSel.moteur)) +
      metrique("Depuis", dur(posSel.ecoule)) +
      metrique("Debut", esc(heureLisible(posSel.debut))) +
      metrique("Numero", esc(posSel.id || "?"));
    var box = document.createElement("div");
    box.style.cssText = "background:linear-gradient(180deg,#131f2c,#0b141e);color:#e8f0f8;" +
      "border:1px solid " + coul + "55;border-radius:16px;max-width:720px;width:100%;" +
      "max-height:86vh;overflow:auto;padding:20px 22px;box-shadow:0 24px 70px rgba(0,0,0,.65)," +
      "0 0 0 1px rgba(255,255,255,.04) inset;font:13px ui-sans-serif,system-ui";
    box.innerHTML =
      '<div style="display:flex;align-items:center;gap:14px;margin-bottom:14px">' +
        '<span style="width:22px;height:22px;border-radius:50%;background:' + coul +
          ';box-shadow:0 0 16px ' + coul + 'aa;flex:0 0 auto"></span>' +
        '<div style="flex:1;min-width:0">' +
          '<div style="font-size:20px;font-weight:700;color:#fff">' + esc(nomDeAgent(posSel)) + "</div>" +
          '<div style="font:11px ui-monospace,monospace;color:#8ba1b5">' + esc(posSel.moteur) + "</div>" +
        "</div>" +
        '<span style="font:11px ui-monospace,monospace;background:' + coul + "22;color:" + coul +
          ';border:1px solid ' + coul + "44;padding:4px 10px;border-radius:999px\">EN COURS</span>" +
        '<button id="popup-fermer" style="background:none;border:none;color:#c7d3e0;font-size:22px;' +
        'cursor:pointer;padding:0 6px;line-height:1">x</button>' +
      "</div>" +
      '<div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px">' + metriques + "</div>" +
      '<div style="display:flex;gap:6px;border-bottom:1px solid rgba(255,255,255,.10);margin-bottom:14px">' +
        '<button data-onglet="texte" style="background:none;border:none;border-bottom:2px solid ' + coul +
          ';color:#fff;font:600 12px ui-sans-serif,system-ui;padding:7px 14px;cursor:pointer">Ce qu il fait</button>' +
        '<button data-onglet="act" style="background:none;border:none;border-bottom:2px solid transparent;' +
          'color:#8ba1b5;font:600 12px ui-sans-serif,system-ui;padding:7px 14px;cursor:pointer">Activite</button>' +
      "</div>" +
      '<div id="popup-contenu">' +
        '<div style="font:13px/1.7 ui-sans-serif,system-ui;color:#c9d6e2;white-space:pre-wrap;word-break:break-word">' +
        esc(texteComplet) + "</div>" +
      "</div>";
    ov.innerHTML = "";
    ov.appendChild(box);
    ov.style.display = "flex";
    var panneaux = {
      texte: '<div style="font:13px/1.7 ui-sans-serif,system-ui;color:#c9d6e2;white-space:pre-wrap;word-break:break-word">' +
        esc(texteComplet) + "</div>",
      act: grapheBarres(d.compteurs, coul)
    };
    var bt = document.getElementById("popup-fermer");
    if (bt) bt.onclick = function () { selection = null; ov.style.display = "none"; };
    box.querySelectorAll("[data-onglet]").forEach(function (b) {
      b.onclick = function () {
        box.querySelectorAll("[data-onglet]").forEach(function (x) {
          x.style.color = "#8ba1b5"; x.style.borderBottomColor = "transparent";
        });
        b.style.color = "#fff"; b.style.borderBottomColor = coul;
        document.getElementById("popup-contenu").innerHTML = panneaux[b.dataset.onglet];
      };
    });
  }

  function clic(canvas, agents, evt) {
    var rect = canvas.getBoundingClientRect();
    var x = evt.clientX - rect.left, y = evt.clientY - rect.top;
    var meilleur = -1, dist = 22;
    positions.forEach(function (p, k) {
      var d = Math.hypot(x - p.px, y - p.py);
      if (d < dist) { dist = d; meilleur = k; }
    });
    if (meilleur < 0) { selection = null; }
    else {
      var id = agents[meilleur].id || agents[meilleur].agent || String(meilleur);
      selection = (selection === id) ? null : id;
    }
    dessiner();
  }

  function dessiner() {
    var canvas = document.getElementById("salle-serveur");
    if (!canvas) return;
    var wrap = canvas.parentElement;
    var w = Math.max(280, wrap.clientWidth - 16);
    var h = 340;
    var t = Date.now();
    var ctx = salleServeur(canvas, w, h, Math.floor(t / 600));
    var d = lireDonnees();
    var agents = d.agents;
    if (!agents.length) {
      ctx.fillStyle = "rgba(255,255,255,.55)";
      ctx.font = "12px ui-monospace, monospace";
      ctx.textAlign = "center";
      ctx.fillText("Aucun agent en activite a cette seconde — l'atelier tourne chaque minute.",
                   w / 2, h / 2);
      ctx.textAlign = "left";
      majPopup(null);
      return;
    }
    var posSel = null;
    agents.forEach(function (m, k) {
      var x = 0.14 + (k % 3) * 0.30;
      var y = 0.18 + Math.floor(k / 3) * 0.20;
      if (y > 0.70) y = 0.70;
      var px = x * w, py = y * h;
      var coul = couleurDe(m.agent || m.id || "agent");
      var id = m.id || m.agent || String(k);
      positions[k] = { px: px, py: py, id: id };
      bonhomme(ctx, px, py, coul, (m.agent || m.id || "agent").slice(0, 12),
               selection === id);
      if (selection === id) {
        posSel = { agent: m.agent || m.id, id: id, moteur: m.moteur || "",
                   texte: (m.consigne || "(consigne non lue)"),
                   consigne: m.consigne || "",
                   resume: m.resume || "",
                   ecoule: m.ecoule, debut: m.debut };
      }
    });
    majPopup(posSel);
    if (!canvas._salleClicLie) {
      canvas._salleClicLie = true;
      canvas.addEventListener("click", function (evt) { clic(canvas, agents, evt); });
    }
  }

  function raccorder() {
    var enc = document.getElementById("encours");
    if (enc) setTimeout(dessiner, 30);
  }
  window.dessinerSalle = function () { raccorder(); };
})();
