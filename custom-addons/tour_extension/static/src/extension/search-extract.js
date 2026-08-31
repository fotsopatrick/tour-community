// search-extract.js : s'exécute sur la page de résultats (Bing) et envoie
// les résultats au background. C'est la lecture de la page que l'extension a
// elle-même ouverte — jamais une autre.
//
// Bing sert une structure stable : chaque résultat est un bloc <li class="b_algo">
// avec <h2><a href="...">titre</a></h2> et <p>extrait</p>. On extrait les 5
// premiers. Si Bing change de structure (anti-bot, page de consentement), on
// renvoie un tableau vide + le titre de la page : la Tour saura que la
// recherche n'a rien rendu plutôt que d'inventer.

function extraire() {
  const resultats = [];
  const blocs = document.querySelectorAll("li.b_algo");
  for (const b of Array.from(blocs).slice(0, 5)) {
    const a = b.querySelector("h2 a");
    const p = b.querySelector("p, .b_caption p");
    if (!a) continue;
    resultats.push({
      titre: (a.textContent || "").trim().slice(0, 120),
      lien: a.href || "",
      extrait: (p ? p.textContent : "").trim().slice(0, 200),
    });
  }
  return resultats;
}

// On attend que la page soit stable (Bing charge parfois en deux temps).
function envoie() {
  const resultats = extraire();
  chrome.runtime.sendMessage(
    { type: "resultats", resultats, question: document.title || "" },
    () => {}
  );
}

if (document.readyState === "complete") {
  setTimeout(envoie, 1200);
} else {
  window.addEventListener("load", () => setTimeout(envoie, 1200));
}
