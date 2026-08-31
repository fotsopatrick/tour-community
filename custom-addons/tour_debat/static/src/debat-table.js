/* LA TABLE DE DÉBAT (02/08, Patrick).
 *
 * Chaque débat devient une table rectangulaire VERTICALE : les membres de
 * l'équipe sont assis AUTOUR (à gauche et à droite), ceux qui ont rendu leur
 * avis passent au vert, les autres attendent en gris. En dessous, la zone de
 * discussion fait défiler les avis rendus. La donnée vient de la base
 * (JSON du contrôleur), rien n'est dessiné à la main.
 */
(function () {
  "use strict";

  var el = document.getElementById("tables-debat");
  if (!el) return;
  var data;
  try {
    data = JSON.parse(document.getElementById("debat-data").textContent);
  } catch (e) { return; }
  if (!data || !data.length) {
    el.innerHTML = '<div class="vide">Aucun débat pour l\'instant.</div>';
    return;
  }

  function placer(participants, table) {
    var n = participants.length;
    if (!n) return;
    var rows = Math.ceil(n / 2);
    participants.forEach(function (p, i) {
      var d = document.createElement("div");
      d.className = "membre" + (p.avis ? " avis" : "");
      d.textContent = p.embleme || "•";
      var nom = document.createElement("span");
      nom.className = "nom";
      nom.textContent = p.nom;
      d.appendChild(nom);
      var row = Math.floor(i / 2);
      var top = 14 + row * (72 / Math.max(1, rows - 1));
      var left = (i % 2 === 0) ? 10 : 90;
      d.style.top = top + "%";
      d.style.left = left + "%";
      table.appendChild(d);
    });
  }

  data.forEach(function (d) {
    var carte = document.createElement("div");
    carte.className = "debat-table";

    var titre = document.createElement("h3");
    titre.textContent = d.question;
    carte.appendChild(titre);

    var sous = document.createElement("div");
    sous.className = "sous-t";
    var etatNom = d.etat === "rendu" ? "Avis rendus" :
                  (d.etat === "en_cours" ? "Ils réfléchissent" : "Brouillon");
    sous.textContent = etatNom + " · " + d.nb_avis + "/" + d.nb_attendus + " avis";
    carte.appendChild(sous);

    var table = document.createElement("div");
    table.className = "table" + (d.nb_avis >= d.nb_attendus && d.nb_attendus ? " done" : "");
    var centre = document.createElement("div");
    centre.className = "centre";
    var q = document.createElement("div");
    q.className = "q";
    q.textContent = d.question;
    var prog = document.createElement("div");
    prog.className = "prog";
    prog.textContent = d.nb_avis + "/" + (d.nb_attendus || "?") + " ont répondu";
    centre.appendChild(q);
    centre.appendChild(prog);
    table.appendChild(centre);
    placer(d.participants, table);
    carte.appendChild(table);

    var disc = document.createElement("div");
    disc.className = "discussion";
    if (d.messages && d.messages.length) {
      d.messages.forEach(function (m) {
        var msg = document.createElement("div");
        msg.className = "msg";
        var a = document.createElement("b");
        a.textContent = m.auteur + " · ";
        msg.appendChild(a);
        msg.appendChild(document.createTextNode(m.texte));
        disc.appendChild(msg);
      });
    } else {
      var vide = document.createElement("div");
      vide.className = "vide";
      vide.textContent = "La discussion s'ouvrira quand les avis arrivent.";
      disc.appendChild(vide);
    }
    carte.appendChild(disc);

    el.appendChild(carte);

    // La discussion défile en bas (le plus récent visible).
    disc.scrollTop = disc.scrollHeight;
  });
})();
