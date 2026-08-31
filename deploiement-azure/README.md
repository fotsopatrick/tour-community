# Tour de contrôle — déploiement Azure (sandbox VM)
## Déployé le 29/08/2026 — état fonctionnel complet.

## Ce que c'est
La sandbox Azure (`vm-tour-conquest-sandbox-v2`, http://20.97.179.141) fait
tourner l'édition Community complète de la Tour : thème, Chloé, Braignak et
les 15 briques.

## Le piège qui a fait défaut 7 fois (documenté ici pour ne plus le payer)
L'image publiée `ghcr.io/fotsopatrick/tour-community:latest` est **incomplète** :
son dossier `/mnt/extra-addons` a perdu tous les sous-dossiers `models/`.
Les `__init__.py` des modules font `from . import models` → à l'installation,
Odoo échoue sur « cannot import name 'models' » (import circulaire apparent).

C'est pourquoi une installation « simple » de l'image produit un Odoo nu sans
thème : le thème (`tour_community_theme`) est lui aussi amputé de `models/`.

## Le correctif (déterministe, pas une promesse)
Monter les addons **complets du dépôt** par-dessus ceux (incomplets) de l'image,
dans `docker-compose.yml` :

```yaml
services:
  db:
    image: postgres:15
    environment:
      POSTGRES_USER: odoo
      POSTGRES_PASSWORD: odoo
      POSTGRES_DB: tour_prod
    volumes:
      - pgdata:/var/lib/postgresql/data
    restart: unless-stopped

  tour:
    image: ghcr.io/fotsopatrick/tour-community:latest
    ports:
      - "80:8069"
    depends_on: [db]
    environment:
      DB_NAME: tour_prod
      ODOO_DB_HOST: db
      ODOO_DB_PORT: "5432"
      ODOO_DB_USER: odoo
      ODOO_DB_PASSWORD: odoo
      ODOO_ADMIN_PASSWD: odoo
      ODOO_MODULES: base,web,tour_community_chat,tour_community_braignak,tour_community_theme,tour_actus,tour_apprentissage,tour_condense_community,tour_cookie_secure,tour_cv,tour_messages,tour_nouveautes,tour_projets,tour_rappels,tour_rate_login,tour_recette,tour_reponses,tour_retours,tour_sauvegardes,tour_webapps
      TZ: Europe/Paris
    volumes:
      - odoo-data:/var/lib/odoo
      - ./custom-addons:/mnt/extra-addons   # <-- LE CORRECTIF
    restart: unless-stopped

volumes:
  pgdata:
  odoo-data:
```

## Le réglage d'origine qui bloquait tout
L'IP publique Azure (SKU Standard) **bloque tout trafic entrant** tant qu'aucun
NSG ne l'autorise. L'ancienne VM était donc injoignable (timeout SSH) sans NSG.
Il faut un NSG (ici `nsg-tour-conquest`) autorisant 22, 80, 443 en entrée.

## Accès
- Site : http://20.97.179.141 — page de connexion « Tour de contrôle — Community »
- SSH : `ssh vm-azure` (clé nomi-orel, agent ~/.ssh/agent.sock)
- Odoo : base `tour_prod`, admin passwd `odoo` (lab)
- Détail complet : `acces-azure-tour.md` (Bureau/Desktop de nomi)