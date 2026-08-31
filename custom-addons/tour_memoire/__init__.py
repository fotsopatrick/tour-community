# -*- coding: utf-8 -*-
from . import controllers


def _installer_garde_fou(env):
    """Garde-fou consigné au registre tour_garde_fous : tout nouvel outil
    passe par la zone, la crainte, le fonctionnement et la vérification."""
    if "garde_fou.garde_fou" not in env:
        return
    Modele = env["garde_fou.garde_fou"].sudo()
    if Modele.search_count([("code", "=", "tour_memoire_rappel")]):
        return
    Modele.create({
        "name": "Outil de rappel — mémoire indexée (tour_memoire)",
        "code": "tour_memoire_rappel",
        "zone": "tour",
        "niveau": "deterministe",
        "module": "tour_memoire",
        "etat": "en_place",
        "crainte": ("Le rappel exposerait de l'interne ou servirait de porte "
                    "d'entrée : injection, exfiltration de secrets, surcharge."),
        "fonctionnement": ("Routes /tour/memoire* réservées au pilote "
                           "(base.group_system). q borné à 120 caractères, "
                           "échappé (aucun SQL brut : recherche ORM en ilike). "
                           "Résultats limités à 20. Sortie passée au masque "
                           "des secrets. Fichiers memoire.json bornés à 256 Ko, "
                           "JSON strict."),
        "verification": ("curl sans session → redirection/403 ; avec session "
                         "pilote → JSON ; injecter %% ou _ dans q → aucun effet ; "
                         "aucun secret apparent dans la sortie."),
        "actif": True,
    })
