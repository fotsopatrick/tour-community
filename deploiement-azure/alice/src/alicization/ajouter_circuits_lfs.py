#!/usr/bin/env python3
# /home/alice/alicization/ajouter_circuits_lfs.py
# Ajout des circuits LFS manquants (dédoublonnage inclus)

import json

CHEMIN_CARTE = "/home/alice/carte-vivante/cartes.json"


def normaliser(texte):
    """Normalise les accents pour comparer (é→e, à→a...)."""
    accents = {
        'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
        'à': 'a', 'â': 'a', 'ä': 'a',
        'ç': 'c', 'ô': 'o', 'ö': 'o', 'î': 'i', 'ï': 'i',
        'û': 'u', 'ü': 'u', 'ù': 'u',
        'É': 'e', 'È': 'e', 'Ê': 'e', 'Ë': 'e',
        'À': 'a', 'Â': 'a', 'Ä': 'a', 'Ç': 'c', 'Ô': 'o',
        'Ö': 'o', 'Î': 'i', 'Ï': 'i', 'Û': 'u', 'Ü': 'u', 'Ù': 'u'
    }
    for origin, fin in accents.items():
        texte = texte.replace(origin, fin)
    return texte.lower()


def ajouter_circuit(carte, nom, description, etapes, mots_cles):
    identifiant = normaliser(nom).replace(" ", "-").replace(":", "").replace("/", "-")

    # Doublons exacts (id ou nom identiques)
    for zone in carte["zones"]:
        for noeud in zone.get("noeuds", []):
            if noeud.get("nom") == nom or noeud.get("id") == identifiant:
                print(f"⚠️ Circuit '{nom}' déjà couvert — ignoré.")
                return False

    zone_cible = None
    for zone in carte["zones"]:
        if zone.get("id") == "connaissances" or zone.get("nom") == "connaissances":
            zone_cible = zone
            break
    if zone_cible is None:
        zone_cible = {"id": "connaissances", "nom": "Ce qu'Alice sait",
                      "description": "Les tours de magie qu'elle connaît", "noeuds": []}
        carte["zones"].insert(0, zone_cible)

    zone_cible.setdefault("noeuds", []).append({
        "id": identifiant,
        "nom": nom,
        "type": "circuit",
        "description": description,
        "mots_cles": mots_cles,
        "etapes": etapes
    })
    print(f"✅ Circuit '{nom}' ajouté.")
    return True


# Liste des circuits LFS à ajouter
# "couvert": True = déjà présent dans la carte équivalent → ignoré
circuits_lfs = [
    {
        "nom": "Préparation du disque pour LFS",
        "description": "Partitionner, formater et monter le disque pour LFS",
        "mots_cles": ["partition", "format", "mkfs", "mount", "LFS", "disque"],
        "etapes": [
            "Partitionner le disque avec fdisk ou gdisk",
            "Formater la partition avec mkfs.ext4 /dev/sdX1",
            "Monter la partition sur /mnt/lfs",
            "Créer les dossiers nécessaires : sources, tools, etc."
        ],
        "couvert": True
    },
    {
        "nom": "Compiler Binutils pour LFS",
        "description": "Compilation de Binutils (Pass 1 et Pass 2) pour LFS",
        "mots_cles": ["binutils", "compiler", "LFS", "make", "configure"],
        "etapes": [
            "Extraire l'archive : tar -xf binutils-2.46.0.tar.xz",
            "Créer un répertoire de build : mkdir build && cd build",
            "Configurer : ../configure --prefix=/tools --target=$LFS_TGT --disable-nls",
            "Compiler : make",
            "Installer : make install"
        ]
    },
    {
        "nom": "Compiler GCC pour LFS",
        "description": "Compilation de GCC (Pass 1 et Pass 2) pour LFS",
        "mots_cles": ["gcc", "compiler", "LFS", "make", "configure"],
        "etapes": [
            "Extraire l'archive : tar -xf gcc-15.2.0.tar.xz",
            "Extraire les dépendances : GMP, MPFR, MPC dans le répertoire GCC",
            "Créer un répertoire de build : mkdir build && cd build",
            "Configurer : ../configure --prefix=/tools --target=$LFS_TGT --disable-multilib",
            "Compiler : make",
            "Installer : make install"
        ],
        "couvert": True
    },
    {
        "nom": "Compiler Glibc pour LFS",
        "description": "Compilation de Glibc pour LFS",
        "mots_cles": ["glibc", "compiler", "LFS", "make", "configure"],
        "etapes": [
            "Extraire l'archive : tar -xf glibc-2.43.tar.xz",
            "Créer un répertoire de build : mkdir build && cd build",
            "Configurer : ../configure --prefix=/tools --host=$LFS_TGT --disable-nscd",
            "Compiler : make",
            "Installer : make install"
        ]
    },
    {
        "nom": "Configuration réseau LFS",
        "description": "Configurer le réseau, /etc/fstab, /etc/hosts",
        "mots_cles": ["réseau", "fstab", "hosts", "LFS", "configuration"],
        "etapes": [
            "Créer /etc/fstab : définir les points de montage",
            "Créer /etc/hosts : définir le nom d'hôte",
            "Configurer /etc/resolv.conf pour la résolution DNS",
            "Configurer les interfaces réseau via systemd-networkd"
        ],
        "couvert": True
    },
    {
        "nom": "Installer GRUB pour LFS",
        "description": "Installer et configurer GRUB pour LFS",
        "mots_cles": ["grub", "boot", "LFS", "configuration"],
        "etapes": [
            "Installer GRUB : grub-install /dev/sda",
            "Créer /boot/grub/grub.cfg",
            "Définir le timeout et l'ordre de démarrage",
            "Ajouter une entrée pour LFS avec linux et initrd"
        ]
    },
    {
        "nom": "GOVERN Function NIST CSF",
        "description": "Mettre en place la fonction GOVERN du NIST Cybersecurity Framework",
        "mots_cles": ["nist", "csf", "govern", "gouvernance", "cybersécurité"],
        "etapes": [
            "Comprendre le contexte organisationnel (GV.OC)",
            "Définir la stratégie de gestion des risques (GV.RM)",
            "Attribuer les rôles et responsabilités (GV.RR)",
            "Établir la politique de sécurité (GV.PO)",
            "Mettre en place la supervision et l'oversight (GV.OV)",
            "Gérer les risques de la chaîne d'approvisionnement (GV.SC)"
        ],
        "couvert": True
    }
]


def main():
    with open(CHEMIN_CARTE, 'r', encoding='utf-8') as f:
        carte = json.load(f)
    ajoutes = 0
    for circ in circuits_lfs:
        if circ.get("couvert"):
            print(f"⚠️ Circuit '{circ['nom']}' déjà couvert — ignoré.")
            continue
        if ajouter_circuit(carte, circ["nom"], circ["description"], circ["etapes"], circ["mots_cles"]):
            ajoutes += 1
    with open(CHEMIN_CARTE, 'w', encoding='utf-8') as f:
        json.dump(carte, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Terminé : {ajoutes} circuit(s) ajouté(s).")


if __name__ == "__main__":
    main()