/* Le PROGRAMME du chat (31/07) : pendant la minute de latence, on montre à
 * l'utilisateur ce qui va se passer, étape par étape, au lieu d'un « Réponse
 * en cours… » muet. Les étapes s'allument une par une (le temps que la
 * latence passe), et la réponse est cherchée tout seul (bouton Actualiser).
 *
 * Le verrou reste : pendant en_attente, le champ question est en lecture
 * seule et le bouton Envoyer est masqué — l'utilisateur ne peut rien envoyer
 * tant que l'agent n'a pas répondu. Ce script ne fait QUE montrer et
 * actualiser.
 */
(function () {
  "use strict";
  var CSS =
    "#tour-programme .tp{opacity:.35;transition:opacity .4s;font-size:.85rem}" +
    "#tour-programme .tp.vivant{opacity:1}" +
    "#tour-programme .tp.fait{opacity:1;color:#22c55e}";

  function injecterCss() {
    var s = document.createElement("style");
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  function demarrer() {
    var bloc = document.getElementById("tour-programme");
    if (!bloc || bloc.dataset.tourEnCours === "1") {
      return !!bloc;
    }
    bloc.dataset.tourEnCours = "1";

    // Les étapes, une par une, à rythme de la latence (~15 s chacune).
    var etapes = bloc.querySelectorAll(".tp");
    var i = 0;
    function avance() {
      if (i >= etapes.length) {
        return;
      }
      if (i > 0) {
        etapes[i - 1].className += " fait";
      }
      etapes[i].className += " vivant";
      i += 1;
    }
    avance();
    var pas = setInterval(avance, 15000);

    // On va chercher la réponse tout seul (comme le bouton Actualiser).
    var clics = 0;
    var relance = setInterval(function () {
      var btn = document.querySelector('button[name="action_relever"]');
      if (btn && btn.offsetParent !== null) {
        btn.click();
        clics += 1;
      }
      if (clics >= 6) {
        clearInterval(relance);
        clearInterval(pas);
      }
    }, 20000);

    // Quand la réponse arrive, le bloc disparaît (invisible) : on arrête.
    var verif = setInterval(function () {
      if (!document.getElementById("tour-programme")) {
        clearInterval(relance);
        clearInterval(pas);
        clearInterval(verif);
      }
    }, 4000);
    return true;
  }

  // La page Odoo est une SPA : le bloc n'existe pas encore au chargement.
  // On sonde quelques secondes, puis on anime dès qu'il est là.
  injecterCss();
  var sondes = 0;
  var sonde = setInterval(function () {
    if (demarrer() || ++sondes > 25) {
      clearInterval(sonde);
    }
  }, 700);
})();
