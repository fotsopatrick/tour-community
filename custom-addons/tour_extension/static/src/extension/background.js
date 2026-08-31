// Background : reçoit une question de la page, ouvre la recherche dans un
// onglet réel, puis renvoie les résultats à la page.
//
// LE PONT HUMAIN : la recherche se fait dans l'onglet du navigateur de
// Patrick (session réelle, cookies, exécution JS) — pas dans un serveur que
// les moteurs bloquent. C'est exactement le rôle de l'extension.
//
// GARDE-FOU (règle n°1, 31/07) : l'extension n'a AUCUNE permission sur les
// onglets existants, l'historique, les cookies. Elle ne fait qu'OUVRIR une
// nouvelle recherche et lire la page qu'elle a elle-même ouverte. Elle ne
// lit jamais une autre page.

let requeteEnCours = null;

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  // 1. La page demande une recherche
  if (message && message.type === "recherche") {
    const q = String(message.question || "").trim();
    if (!q) {
      sendResponse({ ok: false, erreur: "question vide" });
      return;
    }
    requeteEnCours = {
      tabIdPage: sender.tab ? sender.tab.id : null,
      question: q,
    };
    const url = "https://www.bing.com/search?q=" + encodeURIComponent(q);
    chrome.tabs.create({ url, active: false })
      .then(() => sendResponse({ ok: true }))
      .catch((e) => {
        requeteEnCours = null;
        sendResponse({ ok: false, erreur: String(e) });
      });
    return true; // réponse asynchrone
  }

  // 2. La page de recherche renvoie les résultats extraits
  if (message && message.type === "resultats") {
    const cible = requeteEnCours ? requeteEnCours.tabIdPage : null;
    requeteEnCours = null;
    if (cible != null) {
      chrome.tabs.sendMessage(cible, {
        type: "resultats",
        resultats: message.resultats || [],
        question: message.question || "",
      }).catch(() => { /* la page a peut-être fermé l'onglet */ });
    }
    sendResponse({ ok: true });
    return false;
  }

  // 3. Écho simple (compatibilité test initial)
  if (message && message.fromPage) {
    sendResponse("EXT OK : j'ai bien recu « " + String(message.question).slice(0, 60) + " »");
    return false;
  }
});
