/* Le banc de tests, dessiné comme une carte électronique (04/08, Patrick).
 *
 * « On sélectionne un test et on voit les étapes par lesquelles il passe. »
 * C'est le même principe que la carte des circuits : on ne dessine pas tout
 * d'un coup — on regarde UNE piste à la fois, et elle se lit d'un bout à
 * l'autre sans croisement.
 *
 * Un test (un cahier) = une piste. Chaque étape = une puce sur la piste. Le
 * signal entre à gauche, traverse les étapes dans l'ordre, et sort par le
 * connecteur de bord.
 *
 * Trois états, trois couleurs, et ce sont les seules :
 *   vert = passe   rouge = échoue   gris = JAMAIS JOUÉ
 * Le gris n'est pas un succès, et il ne doit pas en avoir l'air.
 *
 * Jouer appelle la route existante /tour/cockpit/tests/jouer/<id> : on ne
 * réinvente pas le moteur, on lui donne un tableau de bord. */
(function () {
  var data;
  try { data = JSON.parse(document.getElementById("tests-board-data").textContent); }
  catch (e) { return; }
  // Le controleur sert deja une liste [{cahier:{...}, etapes:[...]}] : on la
  // normalise ici plutot que de toucher au serveur. Un format d affichage se
  // range du cote de l affichage.
  var brut = Array.isArray(data) ? data : (data.cahiers || []);
  var cahiers = brut.map(function (b) {
    return {
      name: (b.cahier && b.cahier.name) || b.name || "(sans nom)",
      groupe: b.groupe || "Sans cible",
      etapes: (b.etapes || []).map(function (e) {
        return {
          id: e.id, name: e.name || "",
          type_etape: e.type_etape || e.type || "",
          chemin: e.chemin || "", attendu: e.attendu || "",
          critique: !!e.critique,
          // « jamais » cote serveur = pas d etat cote carte : gris.
          etat: (e.etat === "jamais" ? "" : (e.etat || "")),
          detail: e.detail || "",
          nb_cibles: e.nb_cibles,
        };
      }),
    };
  });
  var svg = document.getElementById("tests-board");
  if (!svg) return;

  var NS = "http://www.w3.org/2000/svg";
  var W = 1040, H = 620;
  var VERT = "#4ade80", ROUGE = "#f87171", GRIS = "#64748b", OR = "#c9a24c";
  var choisi = 0, enCours = false, actif = -1;

  function el(n, a, p) {
    var e = document.createElementNS(NS, n);
    for (var k in a) e.setAttribute(k, a[k]);
    if (p) p.appendChild(e);
    return e;
  }
  function txt(e, s) { e.appendChild(document.createTextNode(s)); return e; }
  function couleur(etat) {
    return etat === "ok" ? VERT : (etat === "ko" || etat === "echec" ? ROUGE : GRIS);
  }
  function vider(n) { while (n.firstChild) n.removeChild(n.firstChild); }
  function court(s, n) {
    s = s || "";
    return s.length > n ? s.slice(0, n - 1) + "…" : s;
  }

  var panneau = document.getElementById("tests-resultat");
  function ecrire(titre, lignes, ton) {
    if (!panneau) return;
    var c = ton === "ok" ? VERT : (ton === "ko" ? ROUGE : "#e2e8f0");
    panneau.innerHTML =
      '<div style="font-weight:600;color:' + c + ';margin-bottom:.6rem">' +
      String(titre).replace(/</g, "&lt;") + "</div>" +
      lignes.filter(Boolean).map(function (l) {
        return '<div style="color:#94a3b8;font-size:.85rem;line-height:1.65;' +
               'margin-bottom:.35rem">' + String(l).replace(/</g, "&lt;") +
               "</div>";
      }).join("");
  }

  function detail(e) {
    return [
      e.detail || (e.etat === "ok" ? "Le test passe."
                 : e.etat === "ko" ? "Le test échoue."
                 : "Ce test n'a jamais été joué."),
      "genre : " + (e.type_etape || "-"),
      e.chemin ? "chemin : " + e.chemin : "",
      e.attendu ? "attendu : " + e.attendu : "",
      e.critique ? "⚠ étape critique — si elle tombe, le reste ne vaut rien" : "",
    ];
  }

  // ---- Jouer ------------------------------------------------------------
  function jouerUne(e, apres) {
    var fd = new FormData();
    fd.append("csrf_token", window.TDC_CSRF || "");
    fetch("/tour/cockpit/tests/jouer/" + e.id,
          { method: "POST", body: fd, credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        // La route rend un resultat PAR SITE. Une etape ne passe que si elle
        // passe PARTOUT : un test vert sur trois sites et rouge sur le
        // quatrieme n est pas un test vert.
        var res = j.resultats || [];
        var ok = res.length > 0 && res.every(function (x) { return x.ok === true; });
        var ko = res.some(function (x) { return x.ok === false; });
        e.etat = ok ? "ok" : (ko ? "ko" : "");
        e.sites = res;
        e.detail = res.filter(function (x) { return x.ok === false; })
                      .map(function (x) { return x.cible + " : " + (x.detail || "echec"); })
                      .join(" · ") || (ok ? res.length + " site(s) OK" : "");
        dessiner();
        if (apres) apres(ok);
      })
      .catch(function (err) {
        e.etat = "ko";
        e.detail = "La requête n'a pas abouti (" + err.message +
                   ") — l'étape n'a PAS été jouée.";
        dessiner();
        if (apres) apres(false);
      });
  }

  function jouerTout() {
    if (enCours) return;
    var etapes = (cahiers[choisi] || {}).etapes || [];
    if (!etapes.length) return;
    enCours = true;
    var i = 0;
    (function suivant() {
      if (i >= etapes.length) {
        enCours = false; actif = -1; dessiner();
        var ok = etapes.filter(function (e) { return e.etat === "ok"; }).length;
        var kos = etapes.filter(function (e) { return e.etat === "ko"; });
        ecrire(ok === etapes.length ? "✓ La piste passe en entier" : "La piste casse",
               [ok + " étape(s) sur " + etapes.length + " passent."].concat(
                 kos.length ? ["Première étape qui tombe : " + kos[0].name,
                               kos[0].detail || ""] : []),
               ok === etapes.length ? "ok" : "ko");
        return;
      }
      actif = i;
      var e = etapes[i++];
      dessiner();
      ecrire("▶ " + (cahiers[choisi] || {}).name,
             ["étape " + i + " / " + etapes.length + " : " + e.name, "en cours…"],
             null);
      jouerUne(e, suivant);
    })();
  }

  // ---- Le dessin : UNE piste, lue d'un bout à l'autre --------------------
  function dessiner() {
    vider(svg);
    var cahier = cahiers[choisi] || {};
    var etapes = cahier.etapes || [];

    // PLAQUE CALCULEE SUR LE CONTENU (04/08, signale par Patrick : « le
    // circuit s affiche a moitie »). Sans viewBox, le SVG ne se met pas a
    // l echelle de sa colonne : la plaque etait coupee a droite et ecrasee.
    // Meme principe que la carte des circuits : on calcule la hauteur d apres
    // le nombre de rangees, puis on laisse le viewBox faire tenir le tout.
    var PAR_RANGEE = 3, PW = 232, PH = 78, GY = 62;
    var rangees = Math.max(1, Math.ceil(etapes.length / PAR_RANGEE));
    H = 46 + 54 + rangees * PH + (rangees - 1) * GY + 96;
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
    svg.setAttribute("preserveAspectRatio", "xMidYMid meet");

    el("rect", { x: 0, y: 0, width: W, height: H, fill: "#0b1210" }, svg);

    // LE SENS DE CIRCULATION (04/08). La piste serpente pour eviter les
    // croisements : la 2e rangee se lit donc de DROITE A GAUCHE. Sans
    // indication, l oeil lit 1-2-3 puis voit 6-5-4 et croit a une coupure —
    // c est exactement ce que Patrick a signale. Les pistes sont continues,
    // c est la LECTURE qui manquait. Une pointe de fleche par segment suffit.
    var defs = el("defs", {}, svg);
    ["#4ade80", "#f87171", "#64748b", "#c9a24c"].forEach(function (c, i) {
      var mk = el("marker", { id: "fl" + i, viewBox: "0 0 10 10",
        refX: 8, refY: 5, markerWidth: 5, markerHeight: 5,
        orient: "auto-start-reverse" }, defs);
      el("path", { d: "M0 0 L10 5 L0 10 z", fill: c }, mk);
    });
    function fleche(c) {
      var i = c === "#4ade80" ? 0 : (c === "#f87171" ? 1 : (c === "#64748b" ? 2 : 3));
      return "url(#fl" + i + ")";
    }

    var PAD = 60, BX = PAD, BY = 46, BW = W - 2 * PAD, BH = H - BY - 30;
    var plaque = el("g", {}, svg);
    el("rect", { x: BX, y: BY, width: BW, height: BH, rx: 14,
      fill: "#0a3320", stroke: "#155c38", "stroke-width": 2.5 }, plaque);
    var motif = el("pattern", { id: "pcb-grid-tests", width: 26, height: 26,
                                patternUnits: "userSpaceOnUse" }, svg);
    el("path", { d: "M 26 0 L 0 0 0 26", fill: "none",
                 stroke: "#0e4429", "stroke-width": 1 }, motif);
    el("rect", { x: BX, y: BY, width: BW, height: BH, rx: 14,
      fill: "url(#pcb-grid-tests)" }, plaque);
    [[BX + 22, BY + 22], [BX + BW - 22, BY + 22],
     [BX + 22, BY + BH - 22], [BX + BW - 22, BY + BH - 22]].forEach(function (t) {
      el("circle", { cx: t[0], cy: t[1], r: 10, fill: "#0b1210",
        stroke: OR, "stroke-width": 3 }, plaque);
    });

    // LA PISTE SE COUPE A LA PREMIERE ETAPE CRITIQUE EN ECHEC (04/08).
    //
    // Patrick, en regardant la carte : « il y a un truc qui cloche ». C'etait
    // ca : le signal traversait une panne comme si de rien n'etait. Sur une
    // vraie carte, un composant grille coupe le circuit — et surtout, tout ce
    // qui vient APRES n'est plus verifie. Afficher « passe » sur une etape
    // situee derriere une panne critique, c'est afficher un resultat perime.
    var coupe = -1;
    for (var ci = 0; ci < etapes.length; ci++) {
      if (etapes[ci].critique && etapes[ci].etat === "ko") { coupe = ci; break; }
    }

    var compte = el("text", { x: BX, y: 30, fill: "#94a3b8", "font-size": 13,
      "font-family": "system-ui" }, svg);
    var n = { ok: 0, ko: 0, rien: 0 };
    etapes.forEach(function (e) {
      n[e.etat === "ok" ? "ok" : (e.etat === "ko" ? "ko" : "rien")]++;
    });
    txt(compte, etapes.length + " étape(s) — " + n.ok + " passent, " +
        n.ko + " échouent, " + n.rien + " jamais jouées"
        + (coupe >= 0 ? "  ·  PISTE COUPÉE à l'étape " + (coupe + 1)
           + " : ce qui suit n'est plus vérifié" : ""));
    if (coupe >= 0) compte.setAttribute("fill", ROUGE);

    if (!etapes.length) {
      txt(el("text", { x: W / 2, y: H / 2, fill: GRIS, "font-size": 15,
        "text-anchor": "middle", "font-family": "system-ui" }, plaque),
        "Ce cahier n'a aucune étape.");
      return;
    }

    // La piste serpente : 3 étapes par rangée, aller puis retour, angles
    // droits. C'est ce qui évite le plat de spaghettis quand il y en a dix.
    var GX = (BW - 60 - PAR_RANGEE * PW) / Math.max(1, PAR_RANGEE - 1);
    var X0 = BX + 30, Y0 = BY + 54;

    function pos(i) {
      var r = Math.floor(i / PAR_RANGEE), c = i % PAR_RANGEE;
      if (r % 2) c = PAR_RANGEE - 1 - c;          // rangée impaire : on revient
      return { x: X0 + c * (PW + GX), y: Y0 + r * (PH + GY), r: r };
    }

    // L'entrée du signal, à gauche de la première puce.
    var p0 = pos(0);
    el("path", { d: "M" + (BX + 6) + " " + (p0.y + PH / 2) + " H" + p0.x,
      stroke: OR, "stroke-width": 2.5, fill: "none",
      "marker-end": fleche(OR) }, plaque);
    // L etiquette tenait a moitie hors de la plaque : on la pose au-dessus
    // de la premiere puce, ou il y a la place.
    txt(el("text", { x: p0.x, y: p0.y - 9, fill: OR,
      "font-size": 11, "font-family": "system-ui" }, plaque), "entrée du signal");

    // Les pistes entre les puces.
    for (var i = 0; i < etapes.length - 1; i++) {
      var a = pos(i), b = pos(i + 1);
      var ca = couleur(etapes[i].etat);
      var d;
      if (a.r === b.r) {
        var sens = b.x > a.x ? 1 : -1;
        d = "M" + (a.x + (sens > 0 ? PW : 0)) + " " + (a.y + PH / 2) +
            " H" + (b.x + (sens > 0 ? 0 : PW));
      } else {
        // On descend par le côté, à angles droits.
        var bord = (a.x + PW / 2 > BX + BW / 2) ? a.x + PW + 18 : a.x - 18;
        d = "M" + (a.x + PW / 2) + " " + (a.y + PH) +
            " V" + (a.y + PH + GY / 2) +
            " H" + (b.x + PW / 2) +
            " V" + b.y;
      }
      var apresCoupure = (coupe >= 0 && i >= coupe);
      var trait = { d: d, stroke: apresCoupure ? "#334155" : ca,
        "stroke-width": 2.5, fill: "none",
        opacity: apresCoupure ? 0.5 : 0.75 };
      if (apresCoupure) {
        trait["stroke-dasharray"] = "5 6";   // le signal ne passe plus
      } else {
        trait["marker-end"] = fleche(ca);
      }
      el("path", trait, plaque);
    }

    // Le connecteur de bord : la sortie.
    var pf = pos(etapes.length - 1);
    var CY = BY + BH - 34;
    el("rect", { x: BX + 60, y: CY, width: BW - 120, height: 14, rx: 3,
      fill: "#0b1210", stroke: OR, "stroke-width": 1.5 }, plaque);
    for (var d2 = BX + 70; d2 < BX + BW - 66; d2 += 22) {
      el("rect", { x: d2, y: CY + 2, width: 12, height: 10, rx: 2,
        fill: OR, opacity: 0.75 }, plaque);
    }
    el("path", { d: "M" + (pf.x + PW / 2) + " " + (pf.y + PH) + " V" + CY,
      stroke: couleur(etapes[etapes.length - 1].etat), "stroke-width": 2.5,
      fill: "none", opacity: 0.75,
      "marker-end": fleche(couleur(etapes[etapes.length - 1].etat)) }, plaque);

    // Les puces.
    etapes.forEach(function (e, i) {
      var p = pos(i), c = couleur(e.etat);
      var g = el("g", { style: "cursor:pointer" }, plaque);
      g.addEventListener("click", function () {
        actif = i; dessiner();
        ecrire((e.etat === "ok" ? "✓ " : e.etat === "ko" ? "✗ " : "○ ") + e.name,
               detail(e).concat(["", "Clique encore pour rejouer cette étape seule."]),
               e.etat === "ok" ? "ok" : (e.etat === "ko" ? "ko" : null));
        if (!enCours) { enCours = true; jouerUne(e, function (ok) {
          enCours = false;
          ecrire((ok ? "✓ " : "✗ ") + e.name, detail(e), ok ? "ok" : "ko");
        }); }
      });
      if (i === actif) {
        el("rect", { x: p.x - 6, y: p.y - 6, width: PW + 12, height: PH + 12,
          rx: 9, fill: "none", stroke: "#fbbf24", "stroke-width": 2 }, g);
      }
      el("rect", { x: p.x, y: p.y, width: PW, height: PH, rx: 6,
        fill: "#111827", stroke: c, "stroke-width": 2 }, g);
      for (var k = 0; k < 4; k++) {
        el("rect", { x: p.x - 7, y: p.y + 12 + k * 15, width: 7, height: 5,
          fill: OR, opacity: 0.8 }, g);
        el("rect", { x: p.x + PW, y: p.y + 12 + k * 15, width: 7, height: 5,
          fill: OR, opacity: 0.8 }, g);
      }
      el("circle", { cx: p.x + 15, cy: p.y + 16, r: 5.5, fill: c }, g);
      txt(el("text", { x: p.x + 28, y: p.y + 20, fill: "#e2e8f0",
        "font-size": 12, "font-family": "system-ui" }, g),
        (i + 1) + ". " + court(e.name, 24));
      txt(el("text", { x: p.x + 12, y: p.y + 42, fill: "#94a3b8",
        "font-size": 10.5, "font-family": "system-ui" }, g),
        court(e.chemin || e.type_etape || "", 32));
      var perime = (coupe >= 0 && i > coupe);
      txt(el("text", { x: p.x + 12, y: p.y + 60,
        fill: perime ? "#64748b" : c,
        "font-size": 10.5, "font-family": "system-ui" }, g),
        perime ? "non vérifié (piste coupée)"
               : ((e.etat === "ok" ? "passe"
                  : (e.etat === "ko" ? "échoue" : "jamais jouée"))
                  + (e.quand ? " · " + e.quand : "")));
      if (perime) {
        g.setAttribute("opacity", "0.55");
      }
      if (e.critique) {
        txt(el("text", { x: p.x + PW - 10, y: p.y + 20, fill: "#fbbf24",
          "font-size": 10, "text-anchor": "end", "font-family": "system-ui" }, g),
          "critique");
      }
    });
  }

  // ---- Sélecteur et bouton ----------------------------------------------
  var select = document.getElementById("tests-cahier");
  var filtre = document.getElementById("tests-groupe");

  // Le selecteur se remplit selon le groupe choisi : avec beaucoup de
  // cahiers, une liste a plat devient inutilisable (04/08, Patrick).
  function remplirSelect() {
    var g = filtre ? filtre.value : "";
    select.innerHTML = "";
    cahiers.forEach(function (c, i) {
      if (g && c.groupe !== g) { return; }
      var o = document.createElement("option");
      o.value = i;
      o.textContent = c.name + " — " + (c.etapes || []).length + " étape(s)";
      select.appendChild(o);
    });
    if (select.options.length) {
      choisi = parseInt(select.options[0].value, 10) || 0;
      actif = -1;
      dessiner();
    }
  }

  if (select && filtre) {
    var groupes = [];
    cahiers.forEach(function (c) {
      if (groupes.indexOf(c.groupe) < 0) { groupes.push(c.groupe); }
    });
    var tous = document.createElement("option");
    tous.value = "";
    tous.textContent = "Tous les groupes (" + cahiers.length + ")";
    filtre.appendChild(tous);
    groupes.sort().forEach(function (g) {
      var n = cahiers.filter(function (c) { return c.groupe === g; }).length;
      var o = document.createElement("option");
      o.value = g;
      o.textContent = g + " (" + n + ")";
      filtre.appendChild(o);
    });
    filtre.addEventListener("change", remplirSelect);
    remplirSelect();
  } else if (select) {
    cahiers.forEach(function (c, i) {
      var o = document.createElement("option");
      o.value = i;
      o.textContent = c.name + " — " + (c.etapes || []).length + " étape(s)";
      select.appendChild(o);
    });
  }
  if (select) {
    select.addEventListener("change", function () {
      choisi = parseInt(select.value, 10) || 0;
      actif = -1;
      dessiner();
      ecrire(cahiers[choisi].name,
             ["Le signal entre à gauche et traverse les étapes dans l'ordre.",
              "▶ Jouer les lance toutes ; un clic sur une puce n'en joue qu'une."],
             null);
    });
  }
  var bouton = document.getElementById("tests-play");
  if (bouton) bouton.addEventListener("click", jouerTout);

  dessiner();
  ecrire("Banc de tests",
         ["Choisis un test, puis ▶ Jouer.",
          "Une puce grise n'a jamais été jouée — ce n'est pas un succès."],
         null);
})();
