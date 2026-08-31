# Règles pour tout agent travaillant sur ce poste (nomi)

## ALICE — à ne JAMAIS confondre avec la tour (27/08/2026)

- **Alice** = machine `alice@192.168.1.61` (i7-7700, ~8 Go RAM).
  L'utilisateur SSH est **`alice`**, pas `orel`.
- **INTERDIT de redémarrer Alice.** Il y a un mot de passe au boot et un
  chiffrement LUKS : si elle redémarre, plus personne n'a accès sans
  saisir ces secrets au clavier. Ne jamais lancer `reboot`, `shutdown`,
  `poweroff`, ni masquer/démasquer des targets qui forceraient un restart.
- Alice doit rester **allumée sans veille** (écran en continu, pas de
  suspension). Mesures appliquées : mask des targets sleep/suspend/
  hibernate + idle-delay 0 côté session graphique.
- La tour est une AUTRE machine. `~/connexion-tour.sh` ne concerne PAS
  Alice. Ne jamais proposer ce script pour Alice.

## LA CARTE VIVANTE — on la LIT, on ne la devine JAMAIS

**Né d'une faute réelle (22/08/2026).** J'ai cherché le champ « elements »
dans `atelier/cartes.json`. Le vrai nom était « noeuds ». J'ai donc annoncé
à Patrick que sa carte était **vide**. Elle contenait **461 éléments**.
Une carte fausse est pire qu'aucune carte.

**La règle, sans exception :**

1. Toute recherche sur la tour commence par la carte vivante, avec l'outil —
   jamais avec un `grep` au hasard, jamais en ouvrant le JSON à la main :
   ```
   python3 ~/outils/carte-tour.py            # le résumé
   python3 ~/outils/carte-tour.py <un mot>   # chercher dedans
   ```
   Sur la tour, le même outil est à `~/outils/carte-tour.py`.

2. **Ne jamais deviner le nom d'un champ.** On regarde ce qui existe, on
   essaie les noms connus, et si aucun ne marche on le DIT. L'outil le fait
   déjà et s'arrête avec un code d'erreur plutôt que de mentir.

3. **« Zéro trouvé » ne veut jamais dire « ça n'existe pas ».** Ça veut dire
   « absent de la carte » — donc on nomme la porte qu'on n'a pas ouverte.

4. **Ne jamais déduire le produit d'une de ses fonctions.** Même jour, même
   faute : j'ai lu « Duelle : échecs en ligne » et j'ai dit « c'est un site
   d'échecs ». C'est un **site de rencontre avec des jeux**. Une fonction
   n'est pas le produit. On lit la description complète, ou on demande.

**Le contrôle** : `bash ~/outils/test-carte-tour.sh` doit passer au vert.

## TRAVAUX LOCAUX — la tour n'est PAS nécessaire (23/08/2026)

**Né d'une faute réelle (23/08/2026).** Deux fois aujourd'hui, chercher
« donjon » a déclenché la carte vivante, donc un SSH vers la tour, donc une
demande de passphrase à Patrick alors que l'agent SSH n'était pas chargé.
La tour n'était pas nécessaire au travail.

**Pour ces travaux, ne JAMAIS appeler `carte-tour.py` ni aucun SSH :**
- **le jeu donjon / KOTOAGE** (`~/donjon-vr/`) — tout est en local,
  lire son `LISEZMOI.md` et son `CLAUDE.md` ;
- **le studio** (`~/studio/`) — tout est en local.

On cherche directement dans les dossiers du projet et ses propres docs.
Si le contexte de la tour devient vraiment nécessaire : prévenir Patrick
d'abord, et lui faire lancer `~/connexion-tour.sh` avant toute commande.

## TOUT PASSE PAR LES TESTS — avant tout travail, on montre et on exécute les tests (29/08/2026)

**Né d'une faute réelle (29/08/2026).** J'ai déployé la Tour en ligne et j'ai
déclaré « terminé » en vérifiant seulement des codes HTTP. La connexion était
cassée (module `tour_cookie_secure` forçait un cookie `Secure`, jamais renvoyé
sur HTTP → CSRF invalide → login impossible). Mes « tests » passaient parce
qu'ils vérifiaient ce que je voulais voir, pas ce que l'utilisateur vit.

**La règle, sans exception :**

1. **Avant tout travail, on ÉCRIT et on MONTRE les tests** qui prouveront que
   le travail est bon. L'utilisateur doit voir les tests AVANT le travail.
2. Un travail n'est **terminé que quand ses tests passent** — pas quand « ça a
   l'air de marcher ». Un test vert est une preuve ; une impression n'est rien.
3. Les tests vérifient le **parcours réel de l'utilisateur**, pas des codes
   HTTP isolés : connexion de bout en bout (cookies + CSRF + redirection),
   contenu visible, agents qui répondent, pas seulement « le serveur répond ».
4. **On ne réécrit pas un test pour le faire passer.** Si un test échoue, le
   travail est faux : on corrige le travail.
5. La vérification finale se fait **de l'extérieur** (ce que le navigateur
   reçoit), jamais « depuis l'intérieur » (ce qu'on a lancé).

**Le contrôle** : toute livraison est accompagnée de ses scripts de test
exécutés et verts (`python3 ...test_*.py`).

## INTERDIT ABSOLU — ne JAMAIS proposer (27/08/2026)

- **Ne jamais proposer d'aller chercher des fichiers sur la tour sans la
  demande explicite de Patrick** — en particulier des PDF de « règles /
  livres de français ». Patrick l'a rappelé : c'est **interdit**, considéré
  comme du piratage. Ce sujet est clos. Le dictionnaire local d'Alice
  (`outils/registre_langue.py`) est suffisant.
- **Pas de GitHub / pas de remote** pour l'instant. Les sauvegardes se font
  sur le bureau (`/home/orel/Bureau/`) et sur le serveur Alice
  (`alice@192.168.1.61`, dossier `~/alicization`).

## FIL DE SESSION — à lire à la prochaine ouverture

- Le fil complet de la séance du 27/08/2026 (v1.0 + démo Donjon « l'avatar
  bouge », pilote Alice dans le jeu, pièges techniques, état des services)
  est consigné dans `alice27082026.txt`, présent à trois endroits :
  - `/home/orel/Desktop/alice27082026.txt` (bureau de orel)
  - `/home/orel/Bureau/alice27082026.txt`
  - `/home/orel/alicization/docs/alice27082026.txt`
- Commencer toute session par ce fichier, puis regarder l'état git local et
  l'état des services (§1) avant d'agir.

## CONNAISSANCES DE LA TOUR — récupérées en local (30/08/2026)

**Copie locale complète :** `/root/connaissances-tour/` (sessions d'opencode
sur ce poste tournent en root).
- `recup-tour/memoire-tour/` — la mémoire VIVANTE de la tour (68 fiches, maj
  18/08) : règles apprises « souvent en cassant quelque chose ».
- `recup-tour/memoire-centrale/` — 22 fiches (identité, circuits, pare-feu).
- `recup-tour/AGENTS-tour.md`, `CLAUDE-tour.md`, `identite.md`, `SESSION.md`
  (le vrai journal, 282 Ko).
- `recup-claude/` — skills Claude de la tour : `kotodama`, `portiers` +
  settings. L'historique de sessions (`~/.claude/projects/*.jsonl`) n'est PAS
  rapatrié (volume) ; il reste sur la tour.
- `recup-gits/` — les deux dépôts git des connaissances :
  `tour-memoire-prive` (github fotsopatrick, snapshot 06/08) et
  `memoire-ecriture`.

**MCP de la tour récupérés :** `/root/opencode-tour-mcp/` (mcp-tour.py,
mcp-ocr.py, mcp-file.py, mcp-repartiteur.py + wrappers `*-wrapper.sh` qui
forcent l'agent SSH → **aucune passphrase**). Utilisables comme référence ou
branchés via SSH (voir config opencode).

**SSH tour sans passphrase (canal fiable) :**
```
SSH_AUTH_SOCK=/home/orel/.ssh/agent.sock ssh -o BatchMode=yes \
  -o IdentityAgent=/home/orel/.ssh/agent.sock -o IdentitiesOnly=yes tour-vps '...'
```
La config `~/.ssh/config` (tour-vps) a `IdentityAgent none` → sans ces options,
opencode relance ksshaskpass (la passphrase de Patrick). BatchMode + IdentityAgent
pointé sur l'agent partagé évite toute demande. Ne PAS déclencher de passphrase.

## NAVIGATEUR PILOTÉ — outillage installé (30/08/2026)

- **`/root/opencode-navigateur/`** (github fotsopatrick/opencode-navigateur) :
  profil Chrome persistant (`npm run profil` → port 9222), enregistrement de
  session (vidéo+captures+script rejouable), pilotage d'un Chrome déjà ouvert.
- **MCP branchés dans `/root/.config/opencode/opencode.json`** : `navigateur`
  (Playwright, `--cdp-endpoint http://127.0.0.1:9222`) et `pont-chrome`
  (pilote le Chrome réel via extension + serveur 8777). Testés.
- **Skill « cast »** dans `~/.config/opencode/skills/cast/` : diffuser une page
  sur la TV/box du réseau. Dépendance `pychromecast` installée. La box
  Bouygues répond à `192.168.1.144` (Bouygtel4K).

## RAPPEL : les MCP opencode du POSTE sont définis dans la config root

La session opencode de ce poste (nomi) tourne en **root**. Les configs et
connaissances vivent sous `/root/` (`.config/opencode/`, `opencode-tour-mcp/`,
`connaissances-tour/`), PAS sous `/home/orel/` (sauf ce fichier et les skills
copiés pour la relecture orel).
