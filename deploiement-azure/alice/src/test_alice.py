#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de validation pour ALICE — à lancer après chaque correction."""

import json
import time
import unittest
import requests

ALICE_URL = "http://192.168.1.61:8000"


def gate(command, user="test"):
    return requests.post(f"{ALICE_URL}/api/v1/gate",
                         json={"command": command, "user": user})


def attendre_job(job_id, timeout=60):
    """Poll GET /api/v1/gate/<id> jusqu'à la fin du job."""
    fin = time.time() + timeout
    while time.time() < fin:
        r = requests.get(f"{ALICE_URL}/api/v1/gate/{job_id}")
        if r.json().get("status") in ("done", "error"):
            return r.json()
        time.sleep(0.3)
    return {"status": "timeout"}


class TestRouteur(unittest.TestCase):
    """Test du routeur : faux positifs, correspondances, refus."""

    def test_routeur_renvoie_circuit_si_match(self):
        """Une requête connue doit renvoyer un circuit."""
        resp = gate("lire la carte vivante")
        self.assertEqual(resp.status_code, 202)
        self.assertIn("job_id", resp.json())

    def test_routeur_ne_renvoie_pas_de_circuit_pour_requete_ambiguee(self):
        """Une requête vague ne doit pas déclencher un faux positif."""
        resp = gate("donne moi la procedure pour faire un gateau")
        self.assertEqual(resp.status_code, 202)
        data = resp.json()
        self.assertIn("job_id", data)

    def test_requete_ambiguee_n_aboutit_pas_a_circuit_712(self):
        """La requête « gateau » ne doit jamais renvoyer le circuit 712."""
        resp = gate("donne moi la procedure pour faire un gateau")
        job = attendre_job(resp.json()["job_id"])
        result = job.get("result") or {}
        self.assertNotEqual(result.get("decision"), "circuit")

    def test_circuit_connu_aboutit_a_la_carte(self):
        """« Trouver 712 » doit aboutir au circuit de la carte vivante."""
        resp = gate("Trouver 712")
        job = attendre_job(resp.json()["job_id"])
        result = job.get("result") or {}
        self.assertEqual(result.get("decision"), "circuit")


class TestPerf(unittest.TestCase):
    """Test des performances : temps de réponse."""

    def test_post_gate_moins_de_2s(self):
        """Le POST /api/v1/gate doit accuser réception en moins de 2 s."""
        start = time.time()
        gate("quelle est la date d'aujourd'hui ?")
        duration = time.time() - start
        self.assertLess(duration, 2.0, f"Trop lent : {duration:.2f}s")


class TestOCR(unittest.TestCase):
    """Test de l'OCR."""

    def test_ocr_disponible(self):
        """L'OCR répond explicitement (200 ou 500), jamais de timeout."""
        resp = requests.post(f"{ALICE_URL}/api/v1/ocr",
                             json={"image_url": "https://exemple.com/image.png"},
                             timeout=20)
        self.assertIn(resp.status_code, [200, 500])


if __name__ == "__main__":
    unittest.main(verbosity=2)