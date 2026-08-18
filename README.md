# Tour de contrôle — édition Community

**L'édition Community est publique.**

Les briques libres de la tour, installables sur un Odoo standard :

- Code source (AGPL) : https://github.com/fotsopatrick/tour-community
- Démo en ligne : https://democommunity.matourdecontrole.fr (compte demo / demo)

**Ce qu'elle contient (15 briques autonomes) :**

- Les agents libres : **Chloé** (chat) et **Braignak** (observateur), avec votre clé DeepSeek.
- Les briques : Actus, Apprentissage, Condense, Cookie Secure, CV, Messages, Nouveautés, Projets, Rappels, Rate Login, Recette, Réponses, Retours, Sauvegardes, Webapps.

Aucune clé API exigée pour installer. Le cœur de la tour (agents complets,
coffre, circuits, gouvernance) reste une édition séparée, sous licence
propriétaire.

---

La Tour de contrôle (https://matourdecontrole.fr) est une plateforme de
pilotage : un tableau de bord, une équipe d'agents, des circuits de validation
et des garde-fous. L'édition Community contient **des briques autonomes** qui
s'installent sur un Odoo standard et s'utilisent seules — avec Chloé et
Braignak, les deux agents libres.

Ce dépôt **ne contient pas** le cœur complet : ni l'équipage, ni le coffre des
secrets, ni le moteur de circuits, ni la gouvernance. Ces fonctions font
partie de l'édition complète.

## Ce que contient cette édition

### Les agents (libres, avec votre clé)

| module | ce qu'il fait |
|---|---|
| `tour_community_chat` | **Chloé** — l'assistante. Discutez avec elle (clé DeepSeek : paramètre `tour_community_chat.api_key`). |
| `tour_community_braignak` | **Braignak** — l'observateur. Donnez-lui une URL ou une question, il analyse et dit ce qui manque (clé `tour_community_braignak.api_key`). |
| `tour_community_theme` | L'accueil et le login aux couleurs de la tour, sans Odoo. |

### Les briques

| module | ce qu'il fait |
|---|---|
| `tour_actus` | fil d'actualités par centres d'intérêt (flux RSS) |
| `tour_apprentissage` | leçons d'apprentissage, rangées par thème |
| `tour_condense_community` | un résumé court par texte long |
| `tour_cookie_secure` | force `Secure` sur le cookie de session |
| `tour_cv` | un CV en page web |
| `tour_messages` | garder et copier les messages réutilisables |
| `tour_nouveautes` | chaque nouveauté expliquée simplement |
| `tour_projets` | kanban projets/tâches |
| `tour_rappels` | rappels récurrents dans les activités |
| `tour_rate_login` | limite les tentatives de connexion (429) |
| `tour_recette` | cahier de recette et vérification des sites |
| `tour_reponses` | garder les réponses reçues |
| `tour_retours` | déposer un bug avec sa capture |
| `tour_sauvegardes` | voir les sauvegardes et leurs échecs |
| `tour_webapps` | la liste des pages web de la tour |

## L'accueil

Après connexion, vous arrivez sur le **dashboard de la tour** (`/tour/dashboard`,
le même accueil que la démo) : le menu Actions, les briques installées, le fil
d'actualités, et Chloé en bas de page. Le login est aux couleurs de la tour,
sans marque Odoo, et les courriels (invitation, réinitialisation,
notifications) sont débrandés.

## Clé d'API ? Aucune n'est exigée pour installer

Aucun module ne demande de clé pour s'installer. Chloé et Braignak ont besoin
d'une clé DeepSeek pour **parler** : posez-la dans Réglages (paramètres
`tour_community_chat.api_key` et `tour_community_braignak.api_key`), ou
laissez-les muets — l'installation ne bloque jamais.

`tour_condense_community` peut aussi appeler une IA (paramètre
`condense.api_key`) ; sans clé, il retombe sur une coupe locale.

## Installer (testé de bout en bout)

Ce processus a été joué réellement : base Odoo vierge → les modules
s'installent, 0 erreur, aucune clé exigée.

1. Odoo 18 (Community). Le pack de langue française est optionnel.
2. Copier les modules voulus dans votre dossier `custom-addons`.
3. Activer les modules dans Applications.
4. Renseigner votre `.env` (voir `.env.example`) — uniquement vos mots de
   passe, aucun secret fourni.

## Licence

Voir `LICENCE.md`. Les modules de cette édition sont libres de lire et
d'installer (AGPL-3.0). Le cœur de la tour (agents complets, coffre,
circuits) reste une édition séparée, sous licence propriétaire.

## Chiffrement

`chiffrer.sh` et `dechiffrer.sh` protègent un fichier sensible de l'édition
complète : AES-256, dérivation lente (PBKDF2, 600 000 itérations). Le
déchiffrement exige le mot de passe administrateur — casser la clé sans lui
exige des milliers de serveurs.

## Tests

`TEST-MODULES.txt` liste chaque module de la tour et son statut sur une base
Community vierge : `OK` = il s'installe seul, `KO` = il dépend du cœur et
n'appartient pas à cette édition.
