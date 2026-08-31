#!/usr/bin/env python3
# test_donjon_communication.py
# Tests pour la communication Donjon ↔ Alice

import unittest
import json
import time
import urllib.request
import urllib.error

class TestDonjonCommunication(unittest.TestCase):

    URL = "http://localhost:8002/donjon/observer"
    URL_MESSAGE = "http://localhost:8002/donjon/message/"

    def test_observation_mur_droite(self):
        """Le Donjon voit un mur à droite → Alice répond avec une action."""
        payload = json.dumps({"description": "je vois un mur à droite"}).encode()
        req = urllib.request.Request(self.URL, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            self.assertIn("action", data)
            self.assertEqual(data["action"]["type"], "move")
            self.assertEqual(data["action"]["direction"], "right")

    def test_observation_porte_devant(self):
        """Le Donjon voit une porte devant → Alice répond avec une action open."""
        payload = json.dumps({"description": "je vois une porte devant moi"}).encode()
        req = urllib.request.Request(self.URL, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            self.assertIn("action", data)
            self.assertEqual(data["action"]["type"], "open")

    def test_observation_gauche(self):
        """Le Donjon voit un mur à gauche → Alice répond move/left."""
        payload = json.dumps({"description": "un mur à gauche"}).encode()
        req = urllib.request.Request(self.URL, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            self.assertEqual(data["action"]["type"], "move")
            self.assertEqual(data["action"]["direction"], "left")

    def test_observation_vide(self):
        """Le Donjon ne voit rien → Alice répond avec une action par défaut."""
        payload = json.dumps({"description": "je suis dans une pièce vide"}).encode()
        req = urllib.request.Request(self.URL, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            self.assertIn("action", data)
            self.assertEqual(data["action"]["type"], "wait")
            self.assertIsNone(data["action"]["direction"])

    def test_erreur_payload_invalide(self):
        """Payload invalide → erreur 400."""
        payload = json.dumps({}).encode()
        req = urllib.request.Request(self.URL, data=payload, headers={"Content-Type": "application/json"})
        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(req, timeout=30)
        self.assertEqual(context.exception.code, 400)

    def test_temps_reponse_mur_droite(self):
        """La réponse doit être < 100ms pour l'action."""
        payload = json.dumps({"description": "je vois un mur à droite"}).encode()
        req = urllib.request.Request(self.URL, data=payload, headers={"Content-Type": "application/json"})
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        duree = (time.time() - t0) * 1000
        self.assertLess(duree, 100)
        self.assertEqual(data["action"]["type"], "move")
        self.assertEqual(data["action"]["direction"], "right")

    def test_message_explicatif_recuperable(self):
        """L'action porte un id ; le message devient récupérable via /donjon/message/<id>."""
        payload = json.dumps({"description": "je vois un mur à droite"}).encode()
        req = urllib.request.Request(self.URL, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        identifiant = data["action"]["id"]
        self.assertTrue(identifiant)
        url = self.URL_MESSAGE + urllib.request.quote(identifiant)
        with urllib.request.urlopen(urllib.request.Request(url), timeout=30) as resp:
            msg = json.loads(resp.read().decode())
            self.assertIn("prêt", msg)
            self.assertIn("message", msg)

    def test_message_inexistant(self):
        """Un id inconnu renvoie prêt:False."""
        req = urllib.request.Request(self.URL_MESSAGE + "inconnu", method="GET")
        with urllib.request.urlopen(req, timeout=30) as resp:
            msg = json.loads(resp.read().decode())
            self.assertFalse(msg["prêt"])

if __name__ == "__main__":
    unittest.main()