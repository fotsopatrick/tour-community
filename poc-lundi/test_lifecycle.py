#!/usr/bin/env python3
# test_lifecycle.py – Vérifie que le Lifecycle Manager détruit les sandboxes expirées

import json
import time
import requests
import subprocess
import unittest
from datetime import datetime, timedelta
import threading
import sys
import os
import importlib.util

os.environ["PATH"] = os.environ.get("PATH", "") + ":/home/orel/bin"

def _charger(nom_dir, nom_fichier):
    spec = importlib.util.spec_from_file_location(
        nom_fichier.replace('-', '_'), os.path.join(nom_dir, nom_fichier))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

tour_sim = _charger('/home/orel/simulateur-banque', 'tour-sim.py')

LIFECYCLE_URL = "http://localhost:8000/api/v1/lifecycle"  # à adapter
GATE_URL = "http://localhost:8000/api/v1/gate"

server = None
def setUpModule():
    global server
    tour_sim.FACTEUR_TEMPS = 0.05
    server = tour_sim.creer_serveur(8000)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.1)

def tearDownModule():
    global server
    if server:
        try:
            server.shutdown()
            server.server_close()
        except Exception:
            pass

class TestLifecycle(unittest.TestCase):

    def test_lifecycle_destroys_expired(self):
        """Crée une sandbox avec TTL de 10 secondes, attend, puis vérifie la destruction."""
        # 1. Créer une demande
        resp = requests.post(GATE_URL, json={
            "command": "launch sandbox",
            "user": "tester",
            "duration": 0.01  # 36 secondes (un peu moins de 1 min)
        })
        self.assertEqual(resp.status_code, 202)
        job_id = resp.json()["job_id"]
        
        # 2. Attendre que le lifecycle manager passe (cycle de 5 min, on réduit le TTL)
        # Pour le test, on simule l'expiration en mettant à jour manuellement la date de création
        # (ou on attend le vrai TTL si on a une durée courte)
        time.sleep(1)  # 1 second is enough since duration < 0.1 triggers DESTROYED after 0.5s
        
        # 3. Vérifier que le job est marqué DESTROYED
        resp = requests.get(f"http://localhost:8000/api/v1/job/{job_id}")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "DESTROYED")
        
        # 4. Vérifier que la VM n'existe plus sur Azure (via terraform state ou az cli)
        # Ici, on simule une vérification avec az vm list
        result = subprocess.run(
            ["az", "vm", "list", "--resource-group", "rg-tour-conquest-20260829", 
             "--query", f"[?tags.JobID=='{job_id}']", "-o", "json"],
            capture_output=True, text=True
        )
        vms = json.loads(result.stdout)
        self.assertEqual(len(vms), 0, f"La VM {job_id} existe encore")
        print(f"✅ TTL pour {job_id} : VM détruite")

if __name__ == "__main__":
    unittest.main()
