# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Tour de contrôle — Degré de pilotage",
    "version": "18.0.1.0.0",
    "summary": "La part des gestes de la tour que l'on fait en discutant, sans lire de doc",
    "description": """
Degré de pilotage
=================

Patrick : « j'essaie de faire en sorte que les users n'aient besoin de rien
faire — juste discuter, lire aucune doc, pour utiliser la tour ».

Ce module rend ce but MESURABLE. Il recense les gestes que fait un utilisateur
de la tour (créer une tâche, construire une app, relancer un invité, vérifier
la sécurité...) et, pour chacun, note s'il est pilotable à la PAROLE (un agent
le fait si on le lui demande, ou un circuit automatique s'en charge) ou
manuel (il faut cliquer, lire une doc, ouvrir un écran).

Le « degré de pilotage » est la part des gestes pilotables à la parole. Il est
RECALCULÉ à chaque affichage : quand un geste devient pilotable, quand un
nouvel agent prend un métier, le chiffre bouge tout seul. C'est la règle du
propriétaire : un chiffre qui ne peut pas être faux.
    """,
    "author": "Code Nomi Nomi",
    "website": "https://matourdecontrole.fr",
    "category": "Tour de contrôle",
    "license": "OPL-1",
    "depends": ["base"],
    "data": [
        "security/ir.model.access.csv",
        "data/capacite_data.xml",
    ],
    "installable": True,
    "application": False,
}
