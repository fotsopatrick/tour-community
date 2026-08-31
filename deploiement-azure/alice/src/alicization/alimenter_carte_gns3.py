#!/usr/bin/env python3
import json, os, sqlite3, urllib.request

CHEMIN_CARTE = "/home/alice/alicization/carte-vivante/cartes.json"
DB_PATH = "/home/alice/alicization/state/alicization.db"

def check_health(url):
    try:
        return urllib.request.urlopen(url, timeout=2).status == 200
    except:
        return False

llm_ok = check_health("http://192.168.1.61:8081/health")
node_ok = check_health("http://192.168.1.61:9100/metrics")

try:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM procedures")
    nb = c.fetchone()[0]
    conn.close()
except:
    nb = 0

desc_llm = "Port 8081, 8 tok/s" if llm_ok else "Port 8081, injoignable"
etat_llm = "OK" if llm_ok else "HORS LIGNE"
etat_node = "OK" if node_ok else "HORS LIGNE"

carte = {
    "zones": [
        {
            "id": "reseau_ia",
            "nom": "Coeur IA d Alice",
            "description": "Etat temps reel",
            "noeuds": [
                {"id": "llm_qwen", "nom": "Qwen 3B", "type": "IA", "etat": etat_llm, "description": desc_llm},
                {"id": "routeur", "nom": "Routeur Python", "type": "Logiciel", "etat": "ACTIF", "description": "Point entree"},
                {"id": "memoire", "nom": "Memoire SQLite", "type": "Base", "etat": "ACTIF", "description": f"{nb} procedure(s)"},
                {"id": "export_metrics", "nom": "Node Exporter", "type": "Monitoring", "etat": etat_node, "description": "Port 9100"}
            ]
        },
        {
            "id": "applications",
            "nom": "Applications Web",
            "description": "Interface controle",
            "noeuds": [
                {"id": "web_ui", "nom": "Web UI 8003", "type": "Interface", "etat": "ACTIF", "description": "Dashboard"},
                {"id": "cartes_json", "nom": "cartes.json", "type": "Fichier", "etat": "ACTIF", "description": "Config carte"}
            ]
        }
    ],
    "liens": [
        {"source": "routeur", "target": "llm_qwen", "type": "HTTP", "label": "Appel API"},
        {"source": "routeur", "target": "memoire", "type": "SQL", "label": "Requetes SQL"},
        {"source": "web_ui", "target": "cartes_json", "type": "HTTP", "label": "GET /cartes.json"},
        {"source": "llm_qwen", "target": "memoire", "type": "Logique", "label": "Contexte"}
    ]
}

os.makedirs(os.path.dirname(CHEMIN_CARTE), exist_ok=True)
with open(CHEMIN_CARTE, "w", encoding="utf-8") as f:
    json.dump(carte, f, indent=4, ensure_ascii=False)
print(f"Carte mise a jour : {CHEMIN_CARTE} - {nb} procedures - LLM {etat_llm}")
