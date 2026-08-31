# -*- coding: utf-8 -*-
"""Le Jeu de la Tour — la lecture, pas la monnaie.

Un jeu façon Pokémon : explorer → rencontrer → faire évoluer. Mais ici rien
n'est gagné en jouant : chaque point se LIT dans le travail réel déjà en base.
Règle du jeu (Patrick, 04/08) : « un chiffre compté informe, un chiffre gagné
en jouant décore ». Le niveau est une trace, jamais une carotte.

Le vocabulaire est celui d'un jeu / d'un isekai : les hauts faits d'une tour
sont des quêtes, des épreuves, des boucliers, des fractures. En clair (côté
interne), quête = circuit conclu, épreuve = test au vert, bouclier =
garde-fou, fracture = bug corrigé — la lecture reste la même.

Rien n'est stocké : on relit la base à chaque affichage, comme la salle des
débats. Un niveau qui montrerait les chiffres d'hier ferait douter de tous
les autres.
"""

from datetime import datetime

from odoo import api, models

# Pondération publique, affichée dans le jeu. La fracture réparée vaut le
# plus : c'est la chaîne complète (trouvé → compris → corrigé).
POIDS = {
    "circuit_approuve": 3,
    "test_vert": 1,
    "garde_fou": 2,
    "bug_corrige": 5,
}

# Termes du jeu / de l'isekai, affichés à tous (vitrine comprise).
LIBELLES = {
    "circuit_approuve": "Quêtes accomplies",
    "test_vert": "Épreuves surmontées",
    "garde_fou": "Boucliers dressés",
    "bug_corrige": "Fractures réparées",
}

# La traduction en clair, réservée à la page interne (pour reconnaître le
# travail vraiment fait).
EN_CLAIR = {
    "circuit_approuve": "un circuit conclu",
    "test_vert": "un test passé au vert",
    "garde_fou": "un garde-fou posé",
    "bug_corrige": "un bug reproduit puis corrigé",
}

# Les étages de l'évolution — la boucle Pokémon, en version tour. Chaque
# étage se gagne sur du travail réel, jamais sur un score.
ETAGES = [
    (0, "Bivouac", "Un campement. On commence par poser des pierres."),
    (3, "Abri", "Les premières murailles tiennent debout."),
    (6, "Tourelle", "La tour guette et répond."),
    (10, "Forteresse", "On frappe à la porte, elle tient."),
    (15, "Citadelle", "Des remparts, des gardes, une mémoire."),
    (20, "Titan", "Personne ne la contourne."),
]

XP_PAR_NIVEAU = 100

# Les paliers (badges) : chacun se gagne sur des sommes d'enregistrements
# réels, jamais sur un drapeau posé à la main.
PALIERS = [
    ("premier_circuit", "Première quête accomplie",
     "Un circuit porté jusqu'à l'approbation : une quête menée au bout."),
    ("dix_circuits", "Dix quêtes accomplies",
     "Explorer puis valider est devenu un réflexe."),
    ("cinquante_circuits", "Cinquante quêtes accomplies",
     "La tour ne démarre plus rien qu'elle ne puisse finir."),
    ("premier_vert", "Première épreuve surmontée",
     "Un test repassé jusqu'au vert."),
    ("cent_verts", "Cent épreuves surmontées",
     "La piste tient : une centaine de preuves comptées."),
    ("premier_garde_fou", "Premier bouclier dressé",
     "Un garde-fou écrit et branché sur la tour."),
    ("dix_garde_fous", "Dix boucliers dressés",
     "Les portes se ferment toutes seules."),
]

CONDITIONS_PALIERS = {
    "premier_circuit": ("circuit_approuve", 1),
    "dix_circuits": ("circuit_approuve", 10),
    "cinquante_circuits": ("circuit_approuve", 50),
    "premier_vert": ("test_vert", 1),
    "cent_verts": ("test_vert", 100),
    "premier_garde_fou": ("garde_fou", 1),
    "dix_garde_fous": ("garde_fou", 10),
}

ICONES = {
    "circuit_approuve": "🧭",
    "test_vert": "✅",
    "garde_fou": "🛡️",
    "bug_corrige": "🐞",
}


class JeuTour(models.Model):
    _name = "jeu.tour"
    _description = "Le Jeu de la Tour — lecture seule, rien n'est stocké"

    @api.model
    def _lire_evenements(self, user_id):
        """Les événements réels d'un utilisateur. Rien n'est inventé : chaque
        ligne est un enregistrement qui existe déjà en base."""
        env = self.env
        evts = []
        Circuit = env["circuit.instance"].sudo()
        for inst in Circuit.search([
                ("create_uid", "=", user_id), ("etat", "=", "publie_prive")]):
            evts.append({"type": "circuit_approuve",
                         "label": inst.name or "Circuit conclu",
                         "date": inst.create_date,
                         "icone": ICONES["circuit_approuve"],
                         "xp": POIDS["circuit_approuve"]})
        Rec = env["recette.resultat"].sudo()
        for r in Rec.search([("create_uid", "=", user_id),
                             ("etat", "=", "ok")]):
            cible = ""
            if r.passage_id and r.passage_id.cible_id:
                cible = r.passage_id.cible_id.name or ""
            label = "Test au vert"
            if cible:
                label += " — %s" % cible
            evts.append({"type": "test_vert", "label": label,
                         "date": r.create_date,
                         "icone": ICONES["test_vert"],
                         "xp": POIDS["test_vert"]})
        Gf = env["garde_fou.garde_fou"].sudo()
        for gf in Gf.search([("create_uid", "=", user_id)]):
            evts.append({"type": "garde_fou",
                         "label": gf.name or "Garde-fou posé",
                         "date": gf.create_date,
                         "icone": ICONES["garde_fou"],
                         "xp": POIDS["garde_fou"]})
        Bug = env["bug.retour"].sudo()
        for b in Bug.search([("user_id", "=", user_id),
                             ("etat", "=", "corrige")]):
            evts.append({"type": "bug_corrige",
                         "label": b.name or "Bug corrigé",
                         "date": b.create_date,
                         "icone": ICONES["bug_corrige"],
                         "xp": POIDS["bug_corrige"]})
        return evts

    @api.model
    def _calculer(self, user_id):
        nom = "?"
        if user_id:
            u = self.env["res.users"].sudo().browse(user_id)
            nom = u.partner_id.name or u.login or "?"
        evts = self._lire_evenements(user_id)
        evts.sort(key=lambda e: e.get("date") or datetime.min, reverse=True)
        comptes = dict.fromkeys(POIDS, 0)
        xp = 0
        for e in evts:
            comptes[e["type"]] += 1
            xp += POIDS[e["type"]]
        niveau = int(xp / XP_PAR_NIVEAU) + 1
        en_cours = xp - (niveau - 1) * XP_PAR_NIVEAU
        paliers = []
        for code, nom_p, aide in PALIERS:
            champ, seuil = CONDITIONS_PALIERS[code]
            paliers.append({"code": code, "nom": nom_p, "aide": aide,
                            "gagne": comptes[champ] >= seuil})
        domaine = max(comptes, key=lambda k: comptes[k]) if xp else ""
        total = len(evts)
        for e in evts:
            e["date_aff"] = self._date_aff(e.get("date"))
        return {
            "user_id": user_id,
            "nom": nom,
            "xp": xp,
            "niveau": niveau,
            "en_cours": en_cours,
            "reste": max(0, XP_PAR_NIVEAU - en_cours),
            "comptes": comptes,
            "comptes_list": [
                {"code": k, "nom": LIBELLES[k], "n": comptes[k],
                 "poids": POIDS[k], "icone": ICONES[k], "en_clair": EN_CLAIR[k]}
                for k in POIDS],
            "en_clair": EN_CLAIR,
            "paliers": paliers,
            "nb_badges": sum(1 for p in paliers if p["gagne"]),
            "domaine": domaine,
            "domaine_nom": LIBELLES.get(domaine, ""),
            "etage": self._etage(niveau),
            "etage_aide": self._etage_aide(niveau),
            "etage_suivant": self._etage_suivant(niveau),
            "derniere_activite": self._date_aff(evts[0]["date"]) if evts else "—",
            "evenements": evts[:60],
            "evenements_visibles": evts[:12],
            "evenements_suite": evts[12:60],
            "total_evenements": total,
        }

    @staticmethod
    def _date_aff(dt):
        if not dt:
            return "—"
        try:
            return dt.strftime("%d/%m/%Y")
        except Exception:  # noqa: BLE001
            return "—"

    @staticmethod
    def _etage(niveau):
        nom = ETAGES[-1][1]
        for seuil, n, _aide in ETAGES:
            if niveau >= seuil:
                nom = n
        return nom

    @staticmethod
    def _etage_aide(niveau):
        aide = ETAGES[-1][2]
        for seuil, _n, a in ETAGES:
            if niveau >= seuil:
                aide = a
        return aide

    @staticmethod
    def _etage_suivant(niveau):
        for seuil, n, _aide in ETAGES:
            if niveau < seuil:
                return n
        return ""

    @api.model
    def _toutes_tours(self):
        """Toutes les tours qui ont de l'activité : niveau, badges, domaine.
        Jamais le fonctionnement interne — le jeu montre ce que la tour sait
        faire, jamais la clé de la porte."""
        ids = set()
        for modele, champ in (("circuit.instance", "create_uid"),
                              ("recette.resultat", "create_uid"),
                              ("garde_fou.garde_fou", "create_uid"),
                              ("bug.retour", "user_id")):
            M = self.env[modele].sudo()
            for r in M.search_read([], [champ]):
                v = r.get(champ)
                if isinstance(v, (list, tuple)):
                    v = v[0] if v else False
                if v:
                    ids.add(v)
        tours = []
        for uid in ids:
            t = self._calculer(uid)
            if t["xp"] > 0:
                tours.append(t)
        tours.sort(key=lambda t: t["xp"], reverse=True)
        return tours
