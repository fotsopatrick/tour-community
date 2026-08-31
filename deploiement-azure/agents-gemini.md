# Agents de la Tour — clé Gemini configurée (29/08/2026, démo lundi)

## État
Chloé et Braignak répondent en **Gemini** (vrai cerveau) sur la Tour Azure
`http://20.97.179.141`.

## Configuration (paramètres Odoo, ir_config_parameter)

| Paramètre | Valeur |
|---|---|
| `tour_community_chat.moteur` | `gemini` |
| `tour_community_chat.gemini_key` | clé Gemini (AQ.Ab8RN6KbnU…) |
| `tour_community_chat.modele` | `gemini-3.6-flash` |
| `tour_community_braignak.moteur` | `gemini` |
| `tour_community_braignak.gemini_key` | clé Gemini (partagée) |

La clé est posée dans la base Odoo (ir_config_parameter), **jamais dans le code**.

## Comment ça a été fait
1. Modules mis à jour sur la VM : `tour_community_chat`, `tour_community_braignak`,
   `tour_webmcp` (version avec support `moteur`/gemini, issue du conteneur
   alicization-builder, commit local 5755b16 absent de GitHub).
2. `odoo -u tour_community_chat,tour_community_braignak,tour_webmcp --stop-after-init`
   (application du nouveau code).
3. INSERT ir_config_parameter (moteur + gemini_key + modele) via psql.
4. `docker compose restart tour`.

## Preuve (testé le 29/08)
- POST `/community/chat/message` → `{"reponse": "Bonjour ! C'est un plaisir de
  vous accueillir, je suis Chloé, votre assistante pour la Tour de contrôle."}`
- POST `/community/braignak/observer` `{cible: https://example.com}` → Braignak
  décrit réellement la page.

## Note
- La version déployée précédemment (clone GitHub 65d65f8) ne supportait pas
  gemini (DeepSeek seulement). Les modules à jour sont ceux du conteneur
  (commit 5755b16 « webmcp + Gemini », à pousser sur GitHub quand le token
  sera étendu — voir circuit-deploiement-alice-cloud.md, H5).
- Clé fournie par Patrick : `GOOGLE_GENERATIVE_AI_API_KEY`. Format `AQ.…` =
  clé Gemini (AI Studio).