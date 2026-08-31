#!/usr/bin/env python3
# test_demo_script.py – Lance le script demo.sh et vérifie qu'il se termine correctement

import subprocess
import unittest
import os

class TestDemoScript(unittest.TestCase):

    def test_demo_script_runs(self):
        """Exécute demo.sh et vérifie qu'il affiche l'IP de la VM."""
        os.chdir("/home/orel/poc-lundi")
        result = subprocess.run(
            ["bash", "demo.sh"],
            capture_output=True, text=True, timeout=120
        )
        self.assertEqual(result.returncode, 0, f"Script échoué:\n{result.stderr}")
        self.assertIn("Sandbox prête", result.stdout)
        self.assertIn("20.", result.stdout)  # L'IP doit commencer par 20.
        print("✅ Démo terminée avec succès")

if __name__ == "__main__":
    unittest.main()
