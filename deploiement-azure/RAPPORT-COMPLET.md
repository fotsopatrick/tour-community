================================================================================
  RAPPORT COMPLET — RECRÉATION VM AZURE + DÉPLOIEMENT DE LA TOUR (COMMUNITY)
  Date : 29/08/2026 — Auteur : nomi (agent) pour Patrick
================================================================================

--------------------------------------------------------------------------------
1. CONTEXTE ET MISSION
--------------------------------------------------------------------------------
- La sandbox Azure (http://20.97.179.141) était injoignable : SSH et HTTP en
  timeout, impossible d'y installer la Tour.
- Mission : recréer la VM à l'identique, supprimer l'ancienne, y déployer la
  Tour de contrôle (édition Community : thème, Chloé, Braignak, 15 briques),
  et consigner tous les accès.
- Contrainte : « il est interdit de refaire une installation sans le thème »
  (ça s'était déjà produit 7 fois avant cette session).

--------------------------------------------------------------------------------
2. CHRONOLOGIE DES ACTIONS
--------------------------------------------------------------------------------
1) Inventaire Azure (depuis le VPS tour, seul endroit où vit la CLI az) :
   - ressources du groupe rg-tour-conquest-20260829 : pip-tour-conquest,
     vnet-tour-conquest, nic-tour-conquest, vm-tour-conquest-sandbox, disque,
     compte Cognitive Services tourdecontrole, conteneur tour-community-test.
2) Relevé complet de la VM d'origine : taille Standard_D2s_v7, image Ubuntu
   22.04 LTS gen2, disque 30 Go Premium_LRS, user azureuser, clé SSH (inconnue).
3) Création de la VM de remplacement identique + notre clé (nomi-orel) :
   - NIC nic-tour-conquest-v2 (sous-réseau 10.0.1.0/24)
   - VM vm-tour-conquest-sandbox-v2
4) Suppression de l'ancienne VM + NIC + disque.
5) Rattachement de l'IP publique statique 20.97.179.141 à la nouvelle NIC.
6) Création d'un NSG (trafic entrant 22/80/443) — LE réglage qui manquait.
7) Installation de Docker + Compose sur la VM.
8) Clone du dépôt tour-community + pull de l'image ghcr.
9) Déploiement Odoo 18 + PostgreSQL (docker compose, port 80).
10) Installation des modules : thème + Chloé + Braignak + 15 briques (18 au total).
11) Sauvegarde des accès (Bureau + Desktop + dépôt local) et commits.

--------------------------------------------------------------------------------
3. ERREURS RENCONTRÉES, CAUSES, CORRECTIFS
--------------------------------------------------------------------------------

ERREUR 1 — « La VM ne répond sur aucun port (22/80/443) »
  Cause racine : l'IP publique Azure est en SKU « Standard », qui est SÉCURISÉE
  PAR DÉFAUT : tout trafic entrant depuis Internet est refusé tant qu'un NSG ne
  l'autorise pas explicitement. L'ancienne VM n'avait AUCUN NSG, d'où le timeout
  permanent (port 22 fermé de partout, pourtant sshd tournait à l'intérieur).
  Correctif : création de nsg-tour-conquest avec les règles AllowSSH (22),
  AllowHTTP (80), AllowHTTPS (443) en entrée, rattaché à la NIC.
  → Preuve : avant NSG sshd écoutait mais timeout ; après NSG, `ssh vm-azure` OK.
  Leçon : avec une IP Standard, « pas de NSG » ne veut PAS dire « tout ouvert ».
  C'est l'inverse : sans NSG, tout est fermé.

ERREUR 2 — « Installations d'Odoo sans thème » (le bug qui s'était répété 7 fois)
  Symptôme : en installant l'image ghcr.io/fotsopatrick/tour-community:latest,
  les modules tour_* échouent à l'installation groupée avec :
  ImportError: cannot import name 'models' from partially initialized module
  'odoo.addons.tour_community_theme' (most likely due to a circular import)
  Cause racine : l'IMAGE est INCOMPLÈTE. Son dossier /mnt/extra-addons a perdu
  tous les sous-dossiers models/ (ex. tour_community_theme/models/ manquant),
  alors que les __init__.py font toujours `from . import models`. L'import d'un
  package inexistant produit exactement cette erreur d'« import circulaire ».
  Le dépôt GitHub, lui, est COMPLET (models/ présents).
  Correctif déterministe : monter les addons complets du dépôt PAR-DESSUS ceux
  (incomplets) de l'image, dans docker-compose.yml :
      volumes:
        - ./custom-addons:/mnt/extra-addons
  Résultat : 18/18 modules installés, zéro erreur, thème actif.
  Leçon : ne jamais faire confiance au contenu d'une image pour installer les
  addons d'un projet. Toujours monter le code du dépôt (le dépôt est la vérité).

ERREUR 3 — « La base existe mais est vide ; Odoo renvoie 500 / ir.http »
  Symptôme : HTTP 500 sur / avec KeyError: 'ir.http', et
  « relation ir_module_module does not exist » dans les logs.
  Cause : l'entrypoint crée la base (CREATE DATABASE) mais ne l'initialise
  (installation de base,web) QUE si ODOO_MODULES est défini. Sans ODOO_MODULES,
  Odoo démarre sur une base vide et 500.
  Correctif : définir ODOO_MODULES dans l'environnement du conteneur, ce qui
  déclenche `odoo -i <modules> --stop-after-init` puis le serveur.
  Leçon : pour cette image, une « installation simple » sans ODOO_MODULES ne
  produit PAS une base utilisable.

ERREUR 4 — « L'entrypoint lit des variables qui ne sont pas celles du compose »
  Symptôme : log « entrypoint, DB_NAME=tour_prod HOST= USER= » puis échec de
  connexion à la base.
  Cause : l'entrypoint attend ODOO_DB_HOST / ODOO_DB_PORT / ODOO_DB_USER /
  ODOO_DB_PASSWORD / DB_NAME (pas HOST/USER/PASSWORD comme l'image Odoo
  officielle).
  Correctif : renseigner les bonnes variables (voir compose ci-dessous).
  Leçon : vérifier l'entrypoint de l'image AVANT d'écrire le compose.

ERREUR 5 — « Permission denied » en réécrivant docker-compose.yml sur la VM
  Cause : le fichier avait été créé en sudo → propriétaire root, l'utilisateur
  azureuser ne peut pas l'écraser avec >.
  Correctif : utiliser `sudo tee ... > /dev/null` pour écrire.
  Leçon : sur une VM, écrire un fichier dans un dossier utilisateur via sudo
  dès le début, ou corriger le propriétaire.

ERREUR 6 — Passphrases SSH répétées (ksshaskpass) pendant la session
  Cause : SSH_AUTH_SOCK non défini dans le shell → ssh tentait de déchiffrer
  la clé nomi-orel (protégée par passphrase) hors de l'agent, et le demandeur
  graphique (ksshaskpass) échouait (QtKeychain indisponible).
  Correctif : agent partagé ~/.ssh/agent.sock, chargé au login via
  ~/.ssh/agent-nomi.sh (appelé par ~/.profile). Sauf tour-vps, où la passphrase
  est VOLONTAIREMENT exigée (IdentityAgent none) à la demande de Patrick.

--------------------------------------------------------------------------------
4. ÉTAT FINAL (vérifié après tout)
--------------------------------------------------------------------------------
  Site              : http://20.97.179.141 → login « Tour de contrôle — Community »
  HTTP /web/login   : 200
  Conteneurs        : azureuser-db-1 (postgres:15) + azureuser-tour-1 (Odoo 18)
                      — tous deux « Up »
  Modules installés : 18/18 (thème + chat/Chloé + braignak/Braignak + 15 briques)
  Connexion Odoo    : admin / admin (compte système, is_admin)
  Mot de passe master Odoo : odoo (création/suppression de bases)

--------------------------------------------------------------------------------
5. URL UTILES
--------------------------------------------------------------------------------
  - Tour en ligne  : http://20.97.179.141
  - Login Odoo     : http://20.97.179.141/web/login
  - Dépôt source   : https://github.com/fotsopatrick/tour-community
  - Démo officielle: https://democommunity.matourdecontrole.fr (compte demo/demo)
  - Site public    : https://matourdecontrole.fr

--------------------------------------------------------------------------------
6. ACCÈS (résumé)
--------------------------------------------------------------------------------
  VM Azure          : vm-azure → ssh vm-azure (clé nomi-orel, agent)
                      20.97.179.141 / azureuser / groupe rg-tour-conquest-20260829
  Tour VPS          : ssh tour-vps (PASS PHRASE exigée, sur accord explicite)
                      creds Azure CLI dans /home/ubuntu/tour/.env.azure
  Docker (VM)       : sudo docker compose -f /home/azureuser/docker-compose.yml
  Détail complet    : deploiement-azure/acces-azure-tour.md

--------------------------------------------------------------------------------
7. PROCÉDURE D'INSTALLATION PROPRE (checklist reproductible, sans rien louper)
--------------------------------------------------------------------------------
  PRÉ-REQUIS (une seule fois) :
  □ IP publique Azure en SKU Standard → CRÉER un NSG autorisant 22, 80, 443 en
    entrée et l'attacher à la NIC. (Sans NSG sur IP Standard : TOUT est fermé.)
  □ Clé SSH (nomi-orel) chargée dans l'agent partagé (~/.ssh/agent.sock).

  INSTALLATION :
  1. sudo apt update && sudo apt install -y docker.io docker-compose-v2
  2. git clone https://github.com/fotsopatrick/tour-community.git
  3. sudo docker pull ghcr.io/fotsopatrick/tour-community:latest
  4. Écrire /home/azureuser/docker-compose.yml AVEC :
       - variables ODOO_DB_HOST/ODOO_DB_PORT/ODOO_DB_USER/ODOO_DB_PASSWORD/DB_NAME
       - ODOO_MODULES = liste complète (base,web + tour_*)
       - volume ./custom-addons:/mnt/extra-addons   (LE CORRECTIF ANTÉRIEUR)
  5. sudo docker compose up -d
  6. Attendre l'init (odoo -i ... --stop-after-init), puis vérifier :
       curl -s -o /dev/null -w "%{http_code}" http://IP/web/login   → 200
  7. Vérifier que TOUS les modules sont installés :
       docker exec <db> psql -U odoo -d tour_prod -tc
         "SELECT name FROM ir_module_module WHERE state='installed' AND name LIKE 'tour%';"
     → 18 lignes. Si un module manque : l'image a encore perdu des models/,
       on monte ./custom-addons (le dépôt est la vérité).

  RÈGLES D'OR (pour ne jamais refaire une install « sans thème ») :
  1. Le livrable = la page aux couleurs de la Tour, PAS « un Odoo qui répond ».
  2. Ne jamais faire confiance à une image pour le code des addons : toujours
     monter le dépôt. Le dépôt est complet, l'image ne l'est pas.
  3. Après installation : vérifier les 18 modules AVANT de déclarer victoire.
  4. Un timeout réseau sur une IP Azure Standard = penser NSG immédiatement.

--------------------------------------------------------------------------------
8. TESTS EFFECTUÉS
--------------------------------------------------------------------------------
  - SSH VM : OK (vm-azure)
  - HTTP /  : 303 → /web/login : 200, titre « Tour de contrôle — Community »
  - Authentification Odoo : admin/admin = uid 2, is_admin (validé)
  - Modules tour_* : 18 installés (requête SQL)
  - Conteneurs : db Up 47 min, tour Up 4 min (restart: unless-stopped)
================================================================================