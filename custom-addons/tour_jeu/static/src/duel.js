/* Le Duel de la Tour — arène 2D éclairée façon Yu-Gi-Oh.
 *
 * Deux avatars face à face autour d'une table lumineuse. Les cartes se
 * créent AVANT le combat (atelier /tour/jeu-de-la-tour/cartes) ; sinon le
 * duel démarre avec les compétences réelles.
 */
(function () {
  "use strict";

  var W = 960, H = 600;
  var canvas, ctx, el = {};
  var ETAT = { toi: null, adv: null, ptToi: 200, ptAdv: 200, main: [],
               tour: "toi", log: [], fini: false };
  var champ = { toi: [], adv: [] };
  var anim = [];   // [{x,y,texte,couleur,t}]

  function rpc(url, params) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ jsonrpc: "2.0", method: "call", params: params || {} })
    }).then(function (r) { return r.json(); }).then(function (d) {
      if (d.error) throw new Error(d.error.message);
      return d.result;
    });
  }

  function tirer(liste, n) {
    var c = [];
    for (var i = 0; i < n && liste.length; i++) {
      var k = Math.floor(Math.random() * liste.length);
      c.push(liste.splice(k, 1)[0]);
    }
    return c;
  }

  /* ---------- dessin : l'arène éclairée ---------- */
  function arrondi(x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }

  function table() {
    // la table lumineuse au centre
    var tx = 70, ty = 150, tw = W - 140, th = 300;
    var halo = ctx.createRadialGradient(W / 2, H / 2, 10, W / 2, H / 2, 360);
    halo.addColorStop(0, "rgba(96,165,250,.35)");
    halo.addColorStop(0.6, "rgba(59,130,246,.12)");
    halo.addColorStop(1, "rgba(0,0,0,0)");
    ctx.fillStyle = halo;
    ctx.fillRect(0, 0, W, H);
    // le plateau
    ctx.save();
    ctx.shadowColor = "rgba(96,165,250,.6)";
    ctx.shadowBlur = 28;
    arrondi(tx, ty, tw, th, 18);
    ctx.fillStyle = "#0a1430";
    ctx.fill();
    ctx.restore();
    ctx.strokeStyle = "#3b82f6";
    ctx.lineWidth = 2;
    arrondi(tx, ty, tw, th, 18);
    ctx.stroke();
    // la ligne centrale qui sépare les deux joueurs
    ctx.strokeStyle = "rgba(59,130,246,.5)";
    ctx.setLineDash([8, 8]);
    ctx.beginPath();
    ctx.moveTo(tx + 8, H / 2);
    ctx.lineTo(tx + tw - 8, H / 2);
    ctx.stroke();
    ctx.setLineDash([]);
    // étiquettes des zones
    ctx.fillStyle = "rgba(148,163,184,.8)";
    ctx.font = "13px system-ui";
    ctx.textAlign = "center";
    ctx.fillText("CÔTÉ " + (ETAT.adv ? ETAT.adv.nom.toUpperCase() : "ADVERSAIRE"), W / 2, ty + 24);
    ctx.fillText("CÔTÉ " + (ETAT.toi ? ETAT.toi.nom.toUpperCase() : "TOI"), W / 2, ty + th - 10);
  }

  function avatar(qui, x, y, sens, embleme, couleur) {
    if (!qui) return;
    var b = Math.floor(x), h = Math.floor(y);
    // corps (petit personnage 2D, comme dans le royaume)
    ctx.fillStyle = "#1c2438";
    ctx.fillRect(b + 10, h + 20 - (sens === "haut" ? 0 : 4), 4, 5);
    ctx.fillRect(b + 22, h + 20 - (sens === "haut" ? 0 : 4), 4, 5);
    ctx.fillStyle = couleur;
    ctx.fillRect(b + 6, h + 12, 24, 9);
    ctx.fillStyle = "#f2c79b";
    ctx.fillRect(b + 10, h + 4, 16, 9);
    ctx.fillStyle = couleur;
    ctx.fillRect(b + 10, h + 2, 16, 4);
    // l'emblème réel au-dessus (adversaire) / en dessous (joueur)
    ctx.font = "34px system-ui";
    ctx.textAlign = "center";
    var ey = sens === "haut" ? h - 26 : h + 36;
    ctx.fillText(embleme, b + 16, ey);
  }

  function cartePlateau(c, x, y, couleur) {
    arrondi(x, y, 96, 54, 8);
    ctx.fillStyle = couleur || "#12224a";
    ctx.fill();
    ctx.strokeStyle = "#3b82f6";
    ctx.lineWidth = 1.5;
    ctx.stroke();
    ctx.fillStyle = "#e2e8f0";
    ctx.font = "bold 11px system-ui";
    ctx.textAlign = "center";
    ctx.fillText((c.name || "").slice(0, 18), x + 48, y + 20);
    ctx.fillStyle = "#f59e0b";
    ctx.fillText("ATK " + c.attaque, x + 48, y + 40);
  }

  function dessiner() {
    ctx.clearRect(0, 0, W, H);
    // fond
    var g = ctx.createLinearGradient(0, 0, 0, H);
    g.addColorStop(0, "#05070f");
    g.addColorStop(1, "#010308");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);
    table();
    // avatars : adversaire en haut (face vers le bas), joueur en bas
    if (ETAT.adv) avatar(ETAT.adv, W / 2 - 16, 34, "haut", ETAT.adv.embleme, ETAT.adv.couleur);
    if (ETAT.toi) avatar(ETAT.toi, W / 2 - 16, H - 116, "bas", ETAT.toi.embleme, ETAT.toi.couleur);
    // cartes jouées sur la table
    for (var i = 0; i < champ.adv.length; i++) {
      cartePlateau(champ.adv[i], 100 + i * 104, 180, "#2a1245");
    }
    for (var j = 0; j < champ.toi.length; j++) {
      cartePlateau(champ.toi[j], 100 + j * 104, 366, "#12224a");
    }
    // animations (dégâts)
    for (var k = anim.length - 1; k >= 0; k--) {
      var a = anim[k];
      a.t++;
      if (a.t > 60) { anim.splice(k, 1); continue; }
      ctx.globalAlpha = 1 - a.t / 60;
      ctx.font = "bold 28px system-ui";
      ctx.textAlign = "center";
      ctx.fillStyle = a.couleur;
      ctx.fillText(a.texte, a.x, a.y - a.t);
      ctx.globalAlpha = 1;
    }
  }

  /* ---------- le jeu ---------- */
  function log(msg) {
    ETAT.log.unshift(msg);
    // chaque entrée est du texte : les noms de cartes viennent du joueur,
    // rien ne doit pouvoir y glisser du HTML
    el.log.innerHTML = "";
    ETAT.log.forEach(function (l) {
      var d = document.createElement("div");
      d.textContent = l;
      el.log.appendChild(d);
    });
  }

  function majHud() {
    el.ptToi.style.width = (ETAT.ptToi / 2) + "%";
    el.ptAdv.style.width = (ETAT.ptAdv / 2) + "%";
    el.nomToi.textContent = ETAT.toi.nom;
    el.nomAdv.textContent = ETAT.adv.nom;
    el.embToi.textContent = ETAT.toi.embleme;
    el.embAdv.textContent = ETAT.adv.embleme;
    el.tourLabel.textContent = ETAT.fini ? "DUEL TERMINÉ" :
      (ETAT.tour === "toi" ? "À toi de jouer" : "L'adversaire réfléchit…");
    // la main
    el.main.innerHTML = "";
    ETAT.main.forEach(function (c) {
      var d = document.createElement("button");
      d.className = "carte";
      // le nom et l'effet viennent du joueur : texte seulement, jamais du HTML
      var nom = document.createElement("span");
      nom.className = "c-nom";
      nom.textContent = c.name;
      d.appendChild(nom);
      if (c.effet) {
        var ef = document.createElement("span");
        ef.className = "c-effet";
        ef.textContent = c.effet;
        d.appendChild(ef);
      }
      var st = document.createElement("span");
      st.className = "c-atk";
      st.textContent = "ATK " + c.attaque + " · DEF " + c.defense;
      d.appendChild(st);
      d.addEventListener("click", function () { jouer(c); });
      el.main.appendChild(d);
    });
  }

  function jouer(c) {
    if (ETAT.fini || ETAT.tour !== "toi") return;
    var idx = ETAT.main.indexOf(c);
    if (idx === -1) return;
    ETAT.main.splice(idx, 1);
    champ.toi.push(c);
    var deg = c.attaque;
    ETAT.ptAdv = Math.max(0, ETAT.ptAdv - deg);
    anim.push({ x: W / 2, y: 240, texte: "-" + deg, couleur: "#f59e0b", t: 0 });
    log("🗡️ Tu joues « " + c.name + " »" + (c.effet ? " — " + c.effet : "") +
        " → " + deg + " dégâts à " + ETAT.adv.nom + ".");
    var pio = tirer(ETAT.toi.cartes, 1);
    if (pio.length) ETAT.main.push(pio[0]);
    if (ETAT.ptAdv <= 0) {
      ETAT.fini = true;
      log("🏆 VICTOIRE ! Ta tour a vaincu " + ETAT.adv.nom + ".");
      majHud();
      return;
    }
    ETAT.tour = "adv";
    majHud();
    setTimeout(tourAdversaire, 700);
  }

  function tourAdversaire() {
    if (ETAT.fini) return;
    var c = ETAT.adv.cartes.slice().sort(function (a, b) { return b.attaque - a.attaque; })[0];
    if (c) {
      var idx = ETAT.adv.cartes.indexOf(c);
      ETAT.adv.cartes.splice(idx, 1);
      champ.adv.push(c);
      var deg = c.attaque;
      ETAT.ptToi = Math.max(0, ETAT.ptToi - deg);
      anim.push({ x: W / 2, y: 380, texte: "-" + deg, couleur: "#f87171", t: 0 });
      log("⚔️ " + ETAT.adv.nom + " joue « " + c.name + " » → " + deg + " dégâts à ta tour.");
      if (ETAT.ptToi <= 0) {
        ETAT.fini = true;
        log("💀 Tu perds. " + ETAT.adv.nom + " a rasé ta tour..");
      }
    } else {
      log("😌 " + ETAT.adv.nom + " n'a plus de carte : il encaisse.");
    }
    ETAT.tour = "toi";
    majHud();
  }

  function demarrer(data) {
    if (!data.toi || !data.adversaire || !data.toi.cartes.length) {
      el.log.innerHTML = "<div class='vide'>Pas encore de cartes. Crée les tiennes dans l'atelier de cartes.</div>";
      return;
    }
    ETAT.ptToi = ETAT.ptAdv = data.pt || 200;
    ETAT.toi = data.toi;
    ETAT.adv = data.adversaire;
    ETAT.toi.cartes = ETAT.toi.cartes.slice();
    ETAT.adv.cartes = ETAT.adv.cartes.slice();
    // 04/08 : la main montre les 8 cartes les PLUS RÉCENTES (l'API les
    // envoie de la plus neuve à la plus ancienne) — une carte qui vient
    // d'être créée est donc toujours visible. Le reste sert de pioche.
    ETAT.main = ETAT.toi.cartes.splice(0, 8);
    log("🔀 L'arène s'illumine : " + ETAT.toi.nom + " contre " + ETAT.adv.nom + ".");
    log("🎴 Tes cartes sont en bas — clique pour attaquer.");
    majHud();
    requestAnimationFrame(boucle);
  }

  function boucle() {
    dessiner();
    requestAnimationFrame(boucle);
  }

  function initialiser() {
    canvas = document.getElementById("arene");
    ctx = canvas.getContext("2d");
    el.ptToi = document.getElementById("pt-toi");
    el.ptAdv = document.getElementById("pt-adv");
    el.nomToi = document.getElementById("nom-toi");
    el.nomAdv = document.getElementById("nom-adv");
    el.embToi = document.getElementById("emb-toi");
    el.embAdv = document.getElementById("emb-adv");
    el.main = document.getElementById("main");
    el.log = document.getElementById("log");
    el.tourLabel = document.getElementById("tour-label");
    rpc("/tour/jeu-de-la-tour/api/duel", {}).then(demarrer).catch(function (e) {
      el.log.innerHTML = "<div class='vide'>Hors ligne : " + e.message + "</div>";
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initialiser);
  } else {
    initialiser();
  }
})();
