# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
"""Réglages de la Tour WebMCP et des moteurs d'agents.

Les clés restent dans `ir.config_parameter` (jamais dans le code, jamais
dans le dépôt). Les moteurs de Chloé et de Braignak se choisissent ici :
`deepseek` (défaut) ou `gemini`.
"""

from odoo import fields, models

PARAM_API_KEY = "tour_webmcp.api_key"
PARAM_GEMINI_KEY = "tour_webmcp.gemini_key"
PARAM_CARTES_PATH = "tour_dashboard.cartes_path"
PARAM_CHAT_MOTEUR = "tour_community_chat.moteur"
PARAM_BRAIGNak_MOTEUR = "tour_community_braignak.moteur"


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    webmcp_api_key = fields.Char(
        string="Clé d'accès WebMCP (token client)",
        config_parameter=PARAM_API_KEY,
        help="Token que les clients MCP envoient dans Authorization: Bearer.",
    )
    webmcp_gemini_key = fields.Char(
        string="Clé API Gemini",
        config_parameter=PARAM_GEMINI_KEY,
        help="Clé Google Gemini (AI Studio / Vertex) partagée par les agents.",
    )
    webmcp_cartes_path = fields.Char(
        string="Chemin du JSON de la carte vivante",
        config_parameter=PARAM_CARTES_PATH,
        help="Fichier relevé par carte-zones.sh ; lu par /tour/cockpit/carte-vivante et l'outil lire_carte.",
    )
    webmcp_chat_moteur = fields.Selection(
        [("deepseek", "DeepSeek"), ("gemini", "Gemini")],
        string="Moteur de Chloé (chat)",
        config_parameter=PARAM_CHAT_MOTEUR,
        default="deepseek",
    )
    webmcp_braignak_moteur = fields.Selection(
        [("deepseek", "DeepSeek"), ("gemini", "Gemini")],
        string="Moteur de Braignak (observateur)",
        config_parameter=PARAM_BRAIGNak_MOTEUR,
        default="deepseek",
    )