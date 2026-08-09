# Tour — Condensation (Community Edition)

Un résumé court par texte long, le détail à un clic. Rien n'est supprimé.

## Ce que ça fait

Tout texte long (réponse, note, guide, échange) s'affiche PAR DÉFAUT comme un
résumé court, compréhensible par un enfant de six ans. Le texte d'origine
reste entier, dans un onglet « Détail ».

Deux règles dans le code :

1. **La coupe d'abord, l'IA en secours.** Quand le texte est écrit conclusion
   d'abord, les premières phrases sont déjà le résumé : on coupe, on ne paie
   pas de clé d'API. On n'appelle un modèle que si la coupe ne suffit pas.
2. **On ne supprime jamais.** Le résumé se stocke À CÔTÉ du texte d'origine,
   qui ne bouge pas. Un résumé qui remplace l'original est une perte de
   données.

## Installation

1. Copier le module dans le dossier des addons d'Odoo.
2. Installer : `odoo -i tour_condense_community`.
3. (Optionnel) Pour le résumé par IA, poser la clé :
   - paramètre système `condense.api_key`, ou
   - variable d'environnement `CONDENSE_API_KEY`.
   Sans clé, le module fonctionne quand même : il coupe intelligemment.

## Usage

Un cron (ou un bouton) appelle le moteur de condensation sur les textes
récents. Le catalogue des cibles se trouve dans le code
(`CATALOGUE` dans `models/condense.py`) : chaque entrée est
`(modèle, champ, seuil)` — ajouter une cible, c'est ajouter une ligne, sans
toucher au moteur.

## Licence

LGPL-3. Copyright (C) 2026 Code Nomi Nomi. Écrit par Patrick Fotso et
Clark, agent développeur de la tour de contrôle.
