# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Tour de contrôle — WebMCP",
    "summary": "Expose les outils de la Tour au protocole Model Context Protocol (MCP) : carte vivante, Chloé, Braignak, actus, projets, circuits.",
    "description": """
Tour de contrôle — WebMCP
========================
Une couche Model Context Protocol (MCP) branchée sur les briques libres de la
Tour de contrôle. L'endpoint `/mcp/tour` parle le transport MCP Streamable
HTTP (JSON-RPC 2.0 : `initialize`, `tools/list`, `tools/call`) et expose les
outils réels de la Tour :

- `lire_carte` : la carte vivante (JSON d'infrastructure).
- `statut_tour` : l'état de l'instance (modules, clés, compteurs).
- `demander_a_chloe` : pose une question à l'assistante Chloé.
- `observer_braignak` : demande à l'observateur Braignak d'analyser une URL
  ou une question.
- `fil_actus` : le fil d'actualités collecté par la Tour.
- `lister_projets` : les projets et leurs tâches.
- `creer_tache` : crée une tâche dans la Tour.
- `lister_rappels` : les rappels récurrents.
- `executer_circuit` : exécute un circuit connu (mini-moteur Community, les
  étapes deviennent de vraies tâches).

Sécurité : l'endpoint exige un jeton (`tour_webmcp.api_key`) porté dans
l'en-tête `Authorization: Bearer <clé>`. Aucun secret du Coffre n'est
exposé par les outils.
    """,
    "version": "18.0.1.0.0",
    "author": "Patrick Fotso (Code Nomi Nomi)",
    "license": "AGPL-3",
    "category": "Productivity",
    "depends": [
        "base",
        "web",
        "mail",
        "project",
        "tour_community_chat",
        "tour_community_braignak",
        "tour_actus",
        "tour_rappels",
        "tour_vault",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/webmcp_circuit_data.xml",
        "views/res_config_settings_views.xml",
    ],
    "installable": True,
    "application": False,
}