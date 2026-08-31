# Tour de contrôle — Thème

Skin complet de l'interface Odoo 18 Community : impossible de deviner que c'est Odoo.

## Ce que fait le module

- **Thème sombre par défaut** (palette slate + bleu reprise de `alder`/`web-agent` :
  fond `#020817`, surfaces `#0f172a`/`#1e293b`, texte `#f8fafc`, primaire `#3b82f6`,
  radius `0.5rem`), avec bascule clair/sombre dans le menu utilisateur (via OCA
  `web_dark_mode`).
- **Navigation latérale gauche** : la navbar devient une sidebar verticale
  (marque en tête, bouton Applications, sections de l'app courante, systray en bas).
  `NavBar.adapt()` est neutralisé pour ne jamais replier les sections dans « Plus ».
- **Menu applications plein écran** (OCA `web_responsive`) re-skinné en sombre.
- **Login 100 % custom** : surcharge QWeb de `web.login_layout`, carte sombre
  DaisyUI, logo « tour de contrôle », zéro marque Odoo.
- **Débranding** : titre d'onglet « Tour de contrôle », favicon SVG custom,
  entrées odoo.com retirées du menu utilisateur, OdooBot renommé « Copilote »,
  pointeurs de tours d'onboarding masqués.

## Architecture des assets

| Bundle | Fichiers | Rôle |
|---|---|---|
| `web._assets_primary_variables` | `scss/primary_variables.scss` | Couleurs de marque (les deux schémas) |
| `web.assets_variables_dark` | `scss/primary_variables.dark.scss` | Palette sombre, chargée **avant** celle de `web_dark_mode` (premier `!default` gagne) |
| `web.assets_backend` | `backend/*` | Sidebar, skin, patchs JS, template navbar |
| `web.assets_frontend` | `login/login.scss` | Page de connexion |

Pièges connus :

- Les variables dérivées tôt par le cœur (ex. `$o-navbar-entry-bg--active`) sont
  figées avant nos fichiers → on les écrase via les custom properties
  `--NavBar-entry-*` dans `theme.scss`.
- `web_dark_mode` aligne le cookie `color_scheme` sur le champ `res.users.dark_mode`
  à chaque requête : le défaut sombre passe par ce champ (`default=True` +
  data d'installation), pas par le cookie seul.

## Cycle de dev

```bash
docker compose run --rm odoo odoo -d tour -u tour_de_controle_theme --stop-after-init
docker compose restart odoo
# puis Ctrl+Shift+R (ou mode dev → Regenerate Assets Bundles)
```
