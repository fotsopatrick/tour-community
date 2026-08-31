#!/usr/bin/env python3
# test_regression_flux.py
# Tests de non-régression pour le flux GNS3 8002 -> 8003
# Couvre les bugs corrigés le 2026-08-28 :
#  - 8002 Connection refused (flask manquant, mauvais python, BASE /home/orel)
#  - 8003 page blanche (duplicate </script>, thème, missing liveGNS3, missing /live.json)
#  - cartes.json vidé / tronqué / exemple (doit garder 6 zones, 44 noeuds)
#  - exporter_circuit_rl chemin /home/orel obsolète
#  - serveur.py sans route /live.json, mauvais cache
#
# Usage:
#   python3 -m pytest tests/test_regression_flux.py -v
#   python3 -m unittest tests.test_regression_flux -v
# Les tests d'intégration (TestFluxIntegration) sont skippés si les ports ne répondent pas.

import unittest
import json
import re
import sys
import os
from pathlib import Path
import urllib.request
import urllib.error
import socket

# --- helpers ---
def _root():
    """Racine du projet (dossier parent de tests/)."""
    return Path(__file__).parent.parent

def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore")

def _port_ouvert(host, port, timeout=1):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False

def _script_index(p: Path) -> str:
    """Extrait le contenu du bloc <script> d'un index.html (une seule balise)."""
    t = _read(p)
    i = t.find("<script>")
    j = t.find("</script>", i)
    if i < 0 or j < 0:
        raise AssertionError(f"index.html sans <script> dans {p}: <script>={i} </script>={j}")
    return t[i + len("<script>"):j]

def _analyse_js(js: str):
    """Mini-analyse JavaScript indépendante de node :
       - équilibre des (), [] et {} (en ignorant chaînes et commentaires)
       - aucune paire de littéraux string collés (bug du 28/08: `"% " ""+`)
       Retourne (desequilibres, strings_colles)."""
    match = {")": "(", "}": "{", "]": "["}
    ouvre = "([{"; ferme = ")]}"
    pile = []
    cdes = []; adj = []
    k, n = 0, len(js)
    ligne = 1
    in_line = in_block = False
    in_str = None
    dernier_string = False
    while k < n:
        c = js[k]
        if c == "\n":
            ligne += 1; in_line = False; k += 1; continue
        if in_line: k += 1; continue
        if in_block:
            if c == "*" and k + 1 < n and js[k + 1] == "/":
                in_block = False; k += 2; continue
            k += 1; continue
        if in_str:
            if c == "\\": k += 2; continue
            if c == in_str: in_str = None; dernier_string = True
            k += 1; continue
        if c in "\"'`":
            if dernier_string:
                adj.append((ligne, k))
            dernier_string = False
            in_str = c; k += 1; continue
        if c == "/" and k + 1 < n and js[k + 1] == "/":
            in_line = True; k += 2; continue
        if c == "/" and k + 1 < n and js[k + 1] == "*":
            in_block = True; k += 2; continue
        if dernier_string and c not in " \t\r":
            if c in ouvre + ferme + ".,;:+*/%<>=!?&|~^-":
                dernier_string = False
            else:
                adj.append((ligne, k))
                dernier_string = False
        if c in ouvre:
            pile.append((c, ligne)); k += 1; continue
        if c in ferme:
            if pile and pile[-1][0] == match[c]:
                pile.pop()
            else:
                cdes.append((c, ligne))
            dernier_string = False
            k += 1; continue
        k += 1
    return {"desequilibres": [(p, l) for p, l in pile] + cdes, "strings_colles": adj}

# Chemins candidats (workspace et machine Alice) - ordre prioritaire: d'abord les vrais, pas les reliquats
CANDIDATS_CARTE = [
    Path("/home/alice/carte-vivante/cartes.json"),
    Path("/home/alice/carte-vivante-src/cartes.json"),
    Path("/workspace/carte-vivante-main/cartes.json"),
    _root() / "carte-vivante" / "cartes.json",
    _root().parent / "carte-vivante-main" / "cartes.json",
    Path("/workspace/alicizzaztionAVoir2/carte-vivante/cartes.json"),
]
CANDIDATS_INDEX = [
    _root() / "carte-vivante" / "index.html",
    Path("/workspace/carte-vivante-main/index.html"),
    Path("/home/alice/carte-vivante/index.html"),
    Path("/home/alice/carte-vivante-src/index.html"),
]
CANDIDATS_SERVEUR = [
    _root() / "carte-vivante" / "serveur.py",
    Path("/workspace/carte-vivante-main/serveur.py"),
    Path("/home/alice/carte-vivante-src/serveur.py"),
]
CANDIDATS_CHAT = [
    _root() / "chat_backend.py",
    Path("/workspace/alicizzaztionAVoir2/chat_backend.py"),
    Path("/home/alice/chat_backend.py"),
    Path("/home/alice/alicization/chat_backend.py"),
]
CANDIDATS_START = [
    _root() / "start_alice.sh",
    Path("/home/alice/alicization/start_alice.sh"),
]
CANDIDATS_EXPORTER = [
    _root() / "exporter_circuit_rl.py",
    Path("/home/alice/alicization/exporter_circuit_rl.py"),
]

def _premier_existant(candidats):
    for p in candidats:
        if p.exists():
            return p
    return None


class TestCartesJsonNonVide(unittest.TestCase):
    """cartes.json ne doit jamais être l'exemple vide ni tronqué."""

    def test_fichier_existe_et_non_vide(self):
        p = _premier_existant(CANDIDATS_CARTE)
        self.assertIsNotNone(p, f"aucun cartes.json trouvé parmi {CANDIDATS_CARTE}")
        self.assertGreater(p.stat().st_size, 5000, f"{p} trop petit ({p.stat().st_size} octets) -> exemple vide ?")
        data = json.loads(p.read_text(encoding="utf-8"))
        self.assertIn("zones", data)

    def test_6_zones_attendues(self):
        p = _premier_existant(CANDIDATS_CARTE)
        if p is None:
            self.skipTest("cartes.json absent")
        data = json.loads(p.read_text(encoding="utf-8"))
        ids = [z["id"] for z in data["zones"]]
        for attendu in ["live", "infrastructure", "cerveau", "outils", "connaissances", "donjon"]:
            self.assertIn(attendu, ids, f"zone manquante: {attendu} (trouvé {ids})")

    def test_live_zone_complete(self):
        p = _premier_existant(CANDIDATS_CARTE)
        if p is None:
            self.skipTest("cartes.json absent")
        data = json.loads(p.read_text(encoding="utf-8"))
        live = next(z for z in data["zones"] if z["id"] == "live")
        ids = [n["id"] for n in live["noeuds"]]
        for attendu in ["client", "c-api", "routeur", "adaptateur-carte", "memoire", "outil-ocr", "moteur-qwen", "c-llama"]:
            self.assertIn(attendu, ids, f"noeud manquant dans live: {attendu}")
        self.assertEqual(len(live["noeuds"]), 9, "live doit avoir 9 noeuds (circuit 8 + element demande)")
        self.assertEqual(len(live["liens"]), 10)
        self.assertIn("Flux LIVE", live["nom"])
        demande = next((n for n in live["noeuds"] if n.get("type") == "demande"), None)
        self.assertIsNotNone(demande, "live doit porter un element type=demande (suivi du paquet)")
        self.assertIsInstance(demande.get("chemin"), list, "l'element demande doit avoir un chemin (ids du circuit)")
        self.assertEqual(demande["chemin"][0], "client", "le chemin de la demande doit demarrer au client")
        self.assertIn("demande", [n["id"] for n in live["noeuds"]])

    def test_live_chemin_fait_aller_retour(self):
        """Le chemin de la demande doit faire l'aller-retour complet (…→c-llama→
        c-api→client) et chaque étape consécutive doit être un lien réel, pour que
        la carte affiche aussi le RETOUR du paquet (bug : revenait directement de
        c-llama à client, le fil c-llama→c-api→client ne s'allumait jamais)."""
        p = _premier_existant(CANDIDATS_CARTE)
        if p is None:
            self.skipTest("cartes.json absent")
        data = json.loads(p.read_text(encoding="utf-8"))
        live = next(z for z in data["zones"] if z["id"] == "live")
        demande = next(n for n in live["noeuds"] if n.get("type") == "demande")
        ch = demande["chemin"]
        self.assertGreater(len(ch), 9, "le chemin doit inclure les étapes de retour")
        self.assertEqual(ch[-3:], ["c-llama", "c-api", "client"],
                         "le chemin doit repasser par c-api pour remonter au client")
        paires = {(l["de"], l["vers"]) for l in live["liens"]}
        for i in range(len(ch) - 1):
            self.assertIn((ch[i], ch[i + 1]), paires,
                          f"etape {ch[i]}->{ch[i+1]} du chemin sans lien réel dans live")

    def test_live_noeuds_ont_position_flux(self):
        """Les 8 nœuds du circuit live portent une position explicite (fractions
        x/y en ordre de flux) : sans elle placer() les empile par type alphabétique
        et le paquet zigzague (c-llama en dernière colonne, pas au bout de l'aller)."""
        p = _premier_existant(CANDIDATS_CARTE)
        if p is None:
            self.skipTest("cartes.json absent")
        data = json.loads(p.read_text(encoding="utf-8"))
        live = next(z for z in data["zones"] if z["id"] == "live")
        for n in live["noeuds"]:
            if n["id"] == "demande":
                continue
            self.assertIsInstance(n.get("x"), (int, float), f"{n['id']} sans x explicite")
            self.assertIsInstance(n.get("y"), (int, float), f"{n['id']} sans y explicite")
            self.assertGreaterEqual(n["x"], 0); self.assertLessEqual(n["x"], 1)
            self.assertGreaterEqual(n["y"], 0); self.assertLessEqual(n["y"], 1)

    def test_live_liens_retour_ont_plis(self):
        """Les liens du retour (c-llama→c-api, c-api→client) ont des plis w qui
        les font repasser clairement par le haut/sous l'arc au lieu de retomber en
        ligne droite dans le sens de l'aller."""
        p = _premier_existant(CANDIDATS_CARTE)
        if p is None:
            self.skipTest("cartes.json absent")
        data = json.loads(p.read_text(encoding="utf-8"))
        live = next(z for z in data["zones"] if z["id"] == "live")
        for att in [("c-llama", "c-api"), ("c-api", "client")]:
            l = next((x for x in live["liens"] if x["de"] == att[0] and x["vers"] == att[1]), None)
            self.assertIsNotNone(l, f"lien {att} manquant")
            self.assertTrue(l.get("w"), f"lien de retour {att} sans plis w")

    def test_depart_et_releve(self):
        p = _premier_existant(CANDIDATS_CARTE)
        if p is None:
            self.skipTest("cartes.json absent")
        data = json.loads(p.read_text(encoding="utf-8"))
        self.assertIn("depart", data)
        self.assertIn("releve_le", data)
        self.assertNotEqual(data["releve_le"], "exemple", "cartes.json est revenu à l'exemple -> resync perdu")

    def test_connaissances_a_au_moins_3_circuits(self):
        p = _premier_existant(CANDIDATS_CARTE)
        if p is None:
            self.skipTest("cartes.json absent")
        data = json.loads(p.read_text(encoding="utf-8"))
        conn = next(z for z in data["zones"] if z["id"] == "connaissances")
        circuits = [n for n in conn["noeuds"] if n.get("type") == "circuit"]
        self.assertGreaterEqual(len(circuits), 3, f"connaissances doit garder ≥3 circuits (trouvé {len(circuits)})")


class TestIndexHtmlLive(unittest.TestCase):
    """index.html doit contenir le bloc LIVE GNS3 sans duplicate."""

    def test_fichier_existe(self):
        p = _premier_existant(CANDIDATS_INDEX)
        self.assertIsNotNone(p, f"index.html introuvable {CANDIDATS_INDEX}")
        self.assertGreater(p.stat().st_size, 30000)

    def test_contient_liveGNS3(self):
        p = _premier_existant(CANDIDATS_INDEX)
        if p is None:
            self.skipTest("index.html absent")
        t = _read(p)
        self.assertIn("liveGNS3", t, "bloc LIVE GNS3 manquant -> 8003 ne bougera jamais")
        self.assertIn("http://192.168.1.61:8002/live", t)
        self.assertIn("pollLive", t)
        self.assertIn("setInterval(pollLive, 350)", t)

    def test_pas_de_duplicate_closing(self):
        p = _premier_existant(CANDIDATS_INDEX)
        if p is None:
            self.skipTest("index.html absent")
        t = _read(p)
        # Le bug du 28/08: </script></body></html> dupliqué -> page blanche
        self.assertEqual(t.count("</script>"), 1, f"duplicate </script> ({t.count('</script>')} fois) -> page blanche")
        self.assertEqual(t.count("</body>"), 1)
        self.assertEqual(t.count("</html>"), 1)

    def test_theme_sombre_et_fetch_slash(self):
        p = _premier_existant(CANDIDATS_INDEX)
        if p is None:
            self.skipTest("index.html absent")
        t = _read(p)
        # Thème sombre attendu sur alice (#0d1116), pas blanc #ffffff qui était une régression
        self.assertIn("#0d1116", t, "thème sombre #0d1116 manquant (était écrasé par blanc)")
        # fetch doit être /cartes.json (avec slash) pour Flask
        self.assertIn('fetch("/cartes.json")', t, "fetch doit être /cartes.json avec slash (Flask)")

    def test_index_html_script_equivale(self):
        """Le JS du bloc <script> doit être équilibré (pas de ( ni { orphelins).

        Bug 27/08 retrouvé via node --check: l'IIFE (async function vivant() {  est
        ouverte mais n'a jamais de fermeture })(); -> le script complet ne compile
        pas (Unexpected end of input) et la page reste morte. Vérifiable sans node."""
        for p in CANDIDATS_INDEX:
            if not p.exists():
                continue
            r = _analyse_js(_script_index(p))
            self.assertEqual(r["desequilibres"], [],
                             f"{p}: (), [] ou {{}} déséquilibrés (bug IIFE non fermée) -> {r['desequilibres']}")

    def test_index_html_script_strings_non_colles(self):
        """Aucun littéral string ne doit être collé à un autre sans opérateur.

        Bug 28/08 ligne
        lampeLive.textContent=...+"% ""+(live.message...)   (= "% " suivi de "" tout
        de suite) -> SyntaxError: Unexpected string à (index):795 -> script mort."""
        for p in CANDIDATS_INDEX:
            if not p.exists():
                continue
            r = _analyse_js(_script_index(p))
            self.assertEqual(r["strings_colles"], [],
                             f"{p}: littéraux string collés (SyntaxError Unexpected string) -> {r['strings_colles']}")

    def test_index_render_retour_en_ambre(self):
        """Le rendu des liens doit chercher la DERNIÈRE occurrence de la paire
        (de,vers) dans le chemin : l'aller-retour (client→…→c-llama→c-api→client)
        doit allumer les fils du retour, pas seulement l'aller (bug : indexOf
        tombait sur la 1re occurrence, positionnée sur client/c-api du départ)."""
        p = _premier_existant(CANDIDATS_INDEX)
        if p is None:
            self.skipTest("index.html absent")
        t = _read(p)
        self.assertIn("s + 1 < ch.length", t,
                      "le scan des paires consécutives (retour en ambre) manque")
        self.assertIn("etape = -1", t, "le balayage cherche la dernière occurrence")

    def test_index_placer_respecte_positions_explicites(self):
        """placer() doit respecter les x/y explicites (fractions) de cartes.json
        pour la zone live, sinon l'ordre alphabétique par type remet le zigzag
        (client/c-llama en colonnes séparées) et le retour c-llama->c-api revient
        en travers du tableau."""
        p = _premier_existant(CANDIDATS_INDEX)
        if p is None:
            self.skipTest("index.html absent")
        t = _read(p)
        self.assertIn("typeof n.x === 'number'", t,
                      "placer() doit lire des positions x/y explicites en fractions")

    def test_index_paquet_suit_les_plis(self):
        """Le point-paquet animé doit suivre le tracé réel du lien (avec ses plis
        w), sinon sur le retour c-llama->c-api il reste sur la ligne droite
        routeOrtho pendant que le filament passe par le haut."""
        p = _premier_existant(CANDIDATS_INDEX)
        if p is None:
            self.skipTest("index.html absent")
        t = _read(p)
        self.assertIn("l.de===chemin[i]&&l.vers===chemin[i+1]", t,
                      "le paquet doit emprunter le lien réel (avec ses plis)")


class TestServeurPy(unittest.TestCase):
    """serveur.py (8003) doit servir /live.json et /cartes.json."""

    def test_fichier_existe(self):
        p = _premier_existant(CANDIDATS_SERVEUR)
        self.assertIsNotNone(p, f"serveur.py introuvable {CANDIDATS_SERVEUR}")

    def test_routes_presentes(self):
        p = _premier_existant(CANDIDATS_SERVEUR)
        if p is None:
            self.skipTest("serveur.py absent")
        t = _read(p)
        self.assertIn('@app.route("/")', t)
        self.assertIn('@app.route("/cartes.json")', t)
        self.assertIn('@app.route("/live.json")', t, "route /live.json manquante -> fallback live.json 404")
        self.assertIn("CORS", t)
        self.assertIn("port=8003", t)

    def test_pas_de_cache_infini(self):
        p = _premier_existant(CANDIDATS_SERVEUR)
        if p is None:
            self.skipTest("serveur.py absent")
        t = _read(p)
        self.assertIn("CACHE", t)


class TestChatBackendPy(unittest.TestCase):
    """chat_backend.py (8002) doit exposer les bonnes routes et utiliser /home/alice."""

    def test_fichier_existe(self):
        p = _premier_existant(CANDIDATS_CHAT)
        self.assertIsNotNone(p, f"chat_backend.py introuvable {CANDIDATS_CHAT}")

    def test_routes(self):
        p = _premier_existant(CANDIDATS_CHAT)
        if p is None:
            self.skipTest("chat_backend.py absent")
        t = _read(p)
        for route in ["/health", "/live", "/chat", "/donjon/observer", "/carte_donjon"]:
            self.assertIn(route, t, f"route {route} manquante dans chat_backend.py")

    def test_chemins_alice(self):
        p = _premier_existant(CANDIDATS_CHAT)
        if p is None:
            self.skipTest("chat_backend.py absent")
        t = _read(p)
        self.assertIn("/home/alice", t, "chemin /home/alice manquant")
        self.assertNotIn("/home/orel/chat_backend.py", t, "ancien chemin /home/orel resté")

    def test_live_structure(self):
        p = _premier_existant(CANDIDATS_CHAT)
        if p is None:
            self.skipTest("chat_backend.py absent")
        t = _read(p)
        self.assertIn("_live", t)
        self.assertIn("LIVE_JSON", t)
        self.assertIn("port=8002", t)


class TestStartAliceSh(unittest.TestCase):
    """start_alice.sh ne doit plus utiliser python3 système pour 8002."""

    def test_fichier_existe(self):
        p = _premier_existant(CANDIDATS_START)
        self.assertIsNotNone(p, f"start_alice.sh introuvable {CANDIDATS_START}")

    def test_utilise_venv(self):
        p = _premier_existant(CANDIDATS_START)
        if p is None:
            self.skipTest("start_alice.sh absent")
        t = _read(p)
        self.assertIn("alicization-venv/bin/python", t, "doit lancer chat_backend avec le venv (sinon ModuleNotFoundError flask)")
        self.assertIn('BASE="${1:-/home/alice}"', t, "BASE doit être /home/alice, pas /home/orel")

    def test_pattern_pgrep(self):
        p = _premier_existant(CANDIDATS_START)
        if p is None:
            self.skipTest("start_alice.sh absent")
        t = _read(p)
        # Le pattern doit être chat_backend.py, pas python3 ... (sinon ne détecte pas le venv)
        self.assertIn('"chat_backend.py"', t)


class TestExporterChemin(unittest.TestCase):
    def test_pas_de_home_orel(self):
        p = _premier_existant(CANDIDATS_EXPORTER)
        if p is None:
            self.skipTest("exporter_circuit_rl.py absent")
        t = _read(p)
        self.assertNotIn("/home/orel/carte-vivante", t, "chemin obsolète /home/orel resté -> FileNotFoundError")
        self.assertIn("/home/alice/carte-vivante", t)


class TestIngestFiltre(unittest.TestCase):
    """Le /ingest de chat_backend.py doit filtrer l'upload (extensions, taille, magic PDF)."""

    def test_fichier_existe(self):
        p = _premier_existant(CANDIDATS_CHAT)
        self.assertIsNotNone(p, f"chat_backend.py introuvable {CANDIDATS_CHAT}")

    def test_route_ingest_presente(self):
        p = _premier_existant(CANDIDATS_CHAT)
        if p is None:
            self.skipTest("chat_backend.py absent")
        self.assertIn("/ingest", _read(p), "route /ingest manquante -> la carte Ingest ne répond pas")

    def test_extensions_whitelist(self):
        p = _premier_existant(CANDIDATS_CHAT)
        if p is None:
            self.skipTest("chat_backend.py absent")
        t = _read(p)
        for ext in [".pdf", ".txt", ".md"]:
            self.assertIn(ext, t, f"extension {ext} absente de la whitelist /ingest")
        self.assertIn("ext not in ext_ok", t, "l'extension doit être filtrée par un ensemble fixe")
        self.assertIn("os.path.splitext(source)[1].lower()", t,
                      "l'extension doit être lue sur le nom NORMALISÉ (basename) -> pas de montée de répertoire")

    def test_taille_max(self):
        p = _premier_existant(CANDIDATS_CHAT)
        if p is None:
            self.skipTest("chat_backend.py absent")
        t = _read(p)
        self.assertIn("25 * 1024 * 1024", t, "taille max 25 Mo absente du filtre")
        self.assertIn("413", t, "HTTP 413 (trop grand) manquant")

    def test_magic_pdf(self):
        p = _premier_existant(CANDIDATS_CHAT)
        if p is None:
            self.skipTest("chat_backend.py absent")
        t = _read(p)
        self.assertIn("%PDF", t, "vérification des magic bytes %PDF absente")
        self.assertIn("415", t, "HTTP 415 (type refusé) manquant")

    def test_chat_html_filtre_cote_client(self):
        html = None
        for candidat in [Path("/home/alice/alicization/chat.html"), _root() / "chat.html"]:
            if candidat.exists():
                html = _read(candidat)
                break
        if html is None:
            self.skipTest("chat.html introuvable (la carte Ingest côté client)")
        self.assertIn("25*1024*1024", html, "filtre taille côté client manquant")
        self.assertIn("extension", html, "filtre extension côté client manquant")


class TestConnaissanceSwitchApprise(unittest.TestCase):
    """La connaissance ingérée (ex: PDF Libre « switches niveau 2 ») doit rester
    sur la carte et être retrouvée par le routeur (source=carte), sinon l'ingest
    est une illusion : Alice redescendrait au modèle."""

    def test_circuit_l2_present_dans_connaissances(self):
        p = _premier_existant(CANDIDATS_CARTE)
        if p is None:
            self.skipTest("cartes.json absent")
        data = json.loads(p.read_text(encoding="utf-8"))
        conn = next(z for z in data["zones"] if z["id"] == "connaissances")
        circuits = [n for n in conn["noeuds"] if n.get("type") == "circuit"]
        noms = [n["nom"] for n in circuits]
        self.assertTrue(any("commutateur" in n for n in noms),
                       f"le circuit L2 ingéré (commutateur) a disparu de connaissances -> {noms}")
        l2 = next((n for n in circuits if "Layer" in n["nom"]), None)
        self.assertIsNotNone(l2, "circuit 'Layer 2' manquant après ingestion du PDF CCNP")
        self.assertGreaterEqual(len(l2.get("etapes", [])), 3,
                                "le circuit L2 doit porter ≥3 étapes (connaissance réelle)")

    def test_routeur_source_carte_apres_ingestion(self):
        # Même question que l'« avant » (avant ingestion Alice répondait modele/nouveau).
        # Si quelqu'un resynchronise cartes.json sans l'ingestion, source redevient nouveau.
        p = _premier_existant(CANDIDATS_CHAT)
        if p is None:
            self.skipTest("chat_backend.py absent")
        t = _read(p)
        self.assertIn("/ingest", t)
        self.assertIn("ingesteur_qwen", t, "le lien vers ingesteur_qwen (PDF->circuits) a été enlevé")


class TestIngestIntegration(unittest.TestCase):
    """Intégration live du /ingest et du rappel de la connaissance (skippés si 8002 fermé)."""

    @staticmethod
    def _post_fichier(nom_fichier, contenu):
        import uuid as _uuid
        boundary = "----" + _uuid.uuid4().hex
        debut = ("--%s\r\nContent-Disposition: form-data; name=\"file\"; filename=\"%s\"\r\n"
                 "Content-Type: application/octet-stream\r\n\r\n" % (boundary, nom_fichier)).encode()
        fin = ("\r\n--%s--\r\n" % boundary).encode()
        req = urllib.request.Request("http://127.0.0.1:8002/ingest",
                                     data=debut + contenu + fin, method="POST",
                                     headers={"Content-Type": "multipart/form-data; boundary=" + boundary})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode())

    @unittest.skipUnless(_port_ouvert("127.0.0.1", 8002), "8002 fermé")
    def test_refuse_extension_zip(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self._post_fichier("mauvais.zip", b"contenu quelconque")
        self.assertEqual(cm.exception.code, 415, "un .zip doit être refusé (415)")

    @unittest.skipUnless(_port_ouvert("127.0.0.1", 8002), "8002 fermé")
    def test_refuse_pdf_renomme(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self._post_fichier("faux.pdf", b"pas un pdf du tout")
        self.assertEqual(cm.exception.code, 415, "un .pdf qui ne commence pas par %PDF doit être refusé (415)")

    @unittest.skipUnless(_port_ouvert("127.0.0.1", 8002), "8002 fermé")
    def test_text_ingere_en_procedure(self):
        payload = json.dumps({"text": "Procedure anti regression\n1. lire la carte\n2. verifier la memoire"}).encode()
        req = urllib.request.Request("http://127.0.0.1:8002/ingest", data=payload,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode())
        self.assertTrue(data.get("ok"))
        self.assertIn("Procedure anti regression", data.get("procedures", []))

    @unittest.skipUnless(_port_ouvert("127.0.0.1", 8002), "8002 fermé")
    def test_question_switch_repond_depuis_sa_carte(self):
        # La preuve du « après » : Alice répond depuis SA carte (source=carte) avec les
        # étapes du PDF ingéré, pas depuis le modèle (modele/nouveau).
        payload = json.dumps({"message": "explique l operation de base du commutateur layer 2"}).encode()
        req = urllib.request.Request("http://127.0.0.1:8002/chat", data=payload,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read().decode())
        self.assertEqual(data.get("source"), "carte",
                         "Alice doit répondre depuis sa carte après l'ingestion du PDF (source=carte)")
        self.assertGreaterEqual(len(data.get("etapes") or []), 3, "les étapes du circuit L2 doivent être restituées")


class TestFluxIntegration(unittest.TestCase):
    """Tests d'intégration réseau - skippés si les ports ne répondent pas."""

    @unittest.skipUnless(_port_ouvert("127.0.0.1", 8002), "8002 fermé")
    def test_8002_health(self):
        with urllib.request.urlopen("http://127.0.0.1:8002/health", timeout=3) as r:
            data = json.loads(r.read().decode())
            self.assertEqual(data.get("status"), "ok")

    @unittest.skipUnless(_port_ouvert("127.0.0.1", 8002), "8002 fermé")
    def test_8002_live_structure(self):
        with urllib.request.urlopen("http://127.0.0.1:8002/live", timeout=3) as r:
            data = json.loads(r.read().decode())
            for k in ["chemin", "position", "etape", "message"]:
                self.assertIn(k, data)

    @unittest.skipUnless(_port_ouvert("127.0.0.1", 8002), "8002 fermé")
    def test_8002_chat_repond(self):
        payload = json.dumps({"message": "bonjour regression test"}).encode()
        req = urllib.request.Request("http://127.0.0.1:8002/chat", data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode())
            self.assertIn("reponse", data)
            self.assertIn("source", data)

    @unittest.skipUnless(_port_ouvert("127.0.0.1", 8003), "8003 fermé")
    def test_8003_index_contient_live(self):
        with urllib.request.urlopen("http://127.0.0.1:8003/", timeout=3) as r:
            html = r.read().decode(errors="ignore")
            self.assertIn("liveGNS3", html)
            self.assertEqual(html.count("</script>"), 1)

    @unittest.skipUnless(_port_ouvert("127.0.0.1", 8003), "8003 fermé")
    def test_8003_cartes_json(self):
        with urllib.request.urlopen("http://127.0.0.1:8003/cartes.json", timeout=3) as r:
            data = json.loads(r.read().decode())
            self.assertIn("zones", data)
            self.assertGreaterEqual(len(data["zones"]), 6)

    @unittest.skipUnless(_port_ouvert("127.0.0.1", 8003), "8003 fermé")
    def test_8003_live_json(self):
        try:
            with urllib.request.urlopen("http://127.0.0.1:8003/live.json", timeout=3) as r:
                data = json.loads(r.read().decode())
                self.assertIn("position", data)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                # En workspace http.server simple n'a pas /live.json, on vérifie le fallback 8002/live
                if _port_ouvert("127.0.0.1", 8002):
                    with urllib.request.urlopen("http://127.0.0.1:8002/live", timeout=3) as r2:
                        data = json.loads(r2.read().decode())
                        self.assertIn("position", data)
                else:
                    self.skipTest("live.json 404 et 8002 fermé (workspace http.server)")
            else:
                raise

    @unittest.skipUnless(_port_ouvert("127.0.0.1", 8081), "8081 fermé")
    def test_8081_health(self):
        with urllib.request.urlopen("http://127.0.0.1:8081/health", timeout=3) as r:
            data = json.loads(r.read().decode())
            self.assertEqual(data.get("status"), "ok")


if __name__ == "__main__":
    unittest.main()
