#!/usr/bin/env python3
# test_tour_gate.py – Vérifie que l'API de la Tour déclenche bien le provisioning Azure

import json
import time
import requests
import unittest
import subprocess
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

GATE_URL = "http://localhost:8000/api/v1/gate"
JOB_URL = "http://localhost:8000/api/v1/job/"

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

class TestTourGate(unittest.TestCase):

    def test_gate_provisions_azure(self):
        """Envoie une demande valide et vérifie qu'une VM Azure est créée."""
        # 1. Demande valide
        resp = requests.post(GATE_URL, json={
            "command": "launch sandbox",
            "user": "trader",
            "duration": 1
        })
        self.assertEqual(resp.status_code, 202)
        job_id = resp.json()["job_id"]
        print(f"Job ID: {job_id}")
        
        # 2. Attendre que le worker ait créé la VM (polling)
        for _ in range(30):  # 30 * 5s = 150s max
            time.sleep(1) # shortened for fast local test
            resp = requests.get(JOB_URL + job_id)
            data = resp.json()
            if data.get("status") == "DONE":
                self.assertIn("output", data, "Pas d'IP dans la réponse")
                print(f"✅ VM créée avec IP: {data['output']}")
                break
        else:
            self.fail("Le worker n'a pas terminé le job en temps voulu")
        
        # 3. Vérifier que la VM existe réellement sur Azure
        ip = data["output"]
        result = subprocess.run(
            ["az", "vm", "list", "--resource-group", "rg-tour-conquest-20260829",
             "--query", f"[?publicIpAddress=='{ip}']", "-o", "json"],
            capture_output=True, text=True
        )
        vms = json.loads(result.stdout)
        self.assertEqual(len(vms), 1, f"VM avec IP {ip} introuvable sur Azure")
        print(f"✅ VM trouvée sur Azure avec IP {ip}")

if __name__ == "__main__":
    unittest.main()
