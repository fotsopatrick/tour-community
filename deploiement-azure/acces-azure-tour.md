===============================================================================
  ACCÈS ET ÉTAT — TOUR DE CONTRÔLE (Azure) — mis à jour le 29/08/2026
  Sauvegarde faite après recréation de la VM Azure sandbox.
===============================================================================

1. VM AZURE (NOUVELLE — remplace l'ancienne)
-------------------------------------------------------------------------------
  Nom               : vm-tour-conquest-sandbox-v2
  Adresse publique  : 20.97.179.141  (IP statique, rattachée à nic-tour-conquest-v2)
  Utilisateur SSH   : azureuser
  Clé SSH           : ~/.ssh/nomi-orel  (chargée dans l'agent ~/.ssh/agent.sock)
  Connexion         : ssh vm-azure      (alias défini dans ~/.ssh/config)
  Groupe de res.    : rg-tour-conquest-20260829
  Subscription      : 6db5d8cf-2175-4f43-99da-3c8a5d000afc
  Région            : eastus2
  Taille            : Standard_D2s_v7 (2 vCPU / 8 Go)
  Image             : Canonical Ubuntu 22.04 LTS gen2
  Disque            : 30 Go Premium_LRS
  NSG               : nsg-tour-conquest — ouvert : SSH (22), HTTP (80), HTTPS (443)

2. L'ANCIENNE VM (supprimée)
-------------------------------------------------------------------------------
  vm-tour-conquest-sandbox (+ disque + nic-tour-conquest) : SUPPRIMÉE le 29/08.
  Elle était injoignable (IP publique SKU Standard = trafic entrant bloqué par
  défaut sans NSG — cause du timeout SSH historique).

3. LA TOUR DÉPLOYÉE SUR LA VM (docker compose)
-------------------------------------------------------------------------------
  Dépôt            : https://github.com/fotsopatrick/tour-community
  Fichier          : /home/azureuser/docker-compose.yml (sudo)
  Conteneurs       : azureuser-db-1 (postgres:15) + azureuser-tour-1 (Odoo 18)
  Image            : ghcr.io/fotsopatrick/tour-community:latest
  Port web         : 80 -> 8069  (http://20.97.179.141)
  Base Odoo        : tour_prod (user odoo / mdp odoo — lab)
  Admin Odoo       : mdp odoo
  Modules installés: base, web, tour_community_chat (Chloé), tour_community_braignak (Braignak)
  Commandes        : sudo docker compose -f /home/azureuser/docker-compose.yml ps|logs|up -d

4. LIMITE CONNUE (à corriger côté image)
-------------------------------------------------------------------------------
  Les briques tour_* (actus, cv, projets…) échouent à l'installation GROUPÉE
  par un bug d'import circulaire dans l'image ghcr (ex. tour_rate_login,
  tour_reponses, tour_actus). Chloé et Braignak s'installent seuls. À corriger
  dans l'image ou à installer une à une dans une future session.

5. TOUR VPS (réseau OVH — SÉPARÉ, ne pas y toucher sans accord)
-------------------------------------------------------------------------------
  Adresse          : 145.239.77.232
  Utilisateur      : ubuntu
  Connexion        : ssh tour-vps  — PASS PHRASE exigée (IdentityAgent none),
                     pas de session sans accord explicite (règle du 29/08).
  Identifiants Azure (CLI az) : /home/ubuntu/tour/.env.azure (sur le VPS)

6. AGENT SSH (accès sans passphrase, sauf tour-vps)
-------------------------------------------------------------------------------
  Socket           : ~/.ssh/agent.sock
  Script login     : ~/.ssh/agent-nomi.sh (appelé par ~/.profile)
  Clés             : id_ed25519, porte-nomi (sans passphrase, auto) ;
                     nomi-orel (avec passphrase, chargée une fois par session)
  Config           : ~/.ssh/config (alias tour-vps, vm-azure)

7. ACCÈS ODOO
-------------------------------------------------------------------------------
  Login page       : http://20.97.179.141
  Clés DeepSeek pour Chloé/Braignak : à paramétrer plus tard (agents muets OK).
===============================================================================