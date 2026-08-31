# RÈGLES DE LA TOUR — tout passe par les tests (29/08/2026)

Cette règle est née d'une faute réelle : la Tour a été déployée et déclarée
« terminée » alors que la connexion était cassée — `tour_cookie_secure`
forçait un cookie `Secure`, jamais renvoyé sur HTTP, donc CSRF invalide et
login impossible. Les « tests » d'alors vérifiaient des codes HTTP, pas ce que
l'utilisateur vit.

## La règle, sans exception

1. **Avant tout travail, on ÉCRIT et on MONTRE les tests** qui prouveront que
   le travail est bon. L'utilisateur voit les tests AVANT le travail.
2. Un travail n'est **terminé que quand ses tests passent** — pas quand « ça
   a l'air de marcher ». Un test vert est une preuve ; une impression n'est rien.
3. Les tests vérifient le **parcours réel de l'utilisateur**, pas des codes
   HTTP isolés : connexion de bout en bout (cookies + CSRF + redirection),
   contenu visible, agents qui répondent, pas seulement « le serveur répond ».
4. **On ne réécrit pas un test pour le faire passer.** Si un test échoue, le
   travail est faux : on corrige le travail.
5. La vérification finale se fait **de l'extérieur** (ce que le navigateur
   reçoit), jamais « depuis l'intérieur » (ce qu'on a lancé).

## Contrôle

Toute livraison est accompagnée de ses scripts de test exécutés et verts :
`python3 deploiement-azure/tests/test_*.py`.

## Les scripts de la Tour Community

- `tests/test_login.py`   — connexion admin de bout en bout (CSRF + cookies +
  redirection + page d'accueil)
- `tests/test_theme.py`   — le thème « Tour de contrôle » est présent et installé
- `tests/test_chloe.py`   — Chloé : page et route de chat répondent
- `tests/test_braignak.py`— Braignak : page et route d'observation répondent