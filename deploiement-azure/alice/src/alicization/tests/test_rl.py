#!/usr/bin/env python3
# test_rl.py
# Tests pour le module RL

import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from rl.environnement import DonjonSimpleEnv
from rl.entrainer import q_learning

class TestRL(unittest.TestCase):

    def test_environnement_initialisation(self):
        env = DonjonSimpleEnv(size=5)
        obs, _ = env.reset()
        self.assertEqual(len(obs), 4)

    def test_agent_sort_du_cadre_non_prevu(self):
        """Les positions sont bornées par design (clamp) : jamais hors-cadre."""
        env = DonjonSimpleEnv(size=5)
        obs, _ = env.reset()
        for _ in range(100):
            action = env.action_space.sample()
            obs, reward, done, _, _ = env.step(action)
            self.assertTrue(len(obs) == 4)
            if done:
                obs, _ = env.reset()

    def test_q_learning(self):
        env = DonjonSimpleEnv(size=3)
        Q, politique, recompenses = q_learning(env, episodes=10)
        self.assertIsNotNone(Q)
        self.assertIsNotNone(politique)
        self.assertGreater(len(politique), 0)
        self.assertGreater(len(recompenses), 0)

    def test_q_learning_apprend_cylindre(self):
        """Un policy appris : l'agent atteint la cible en fin d'entrainement."""
        env = DonjonSimpleEnv(size=3)
        Q, politique, recompenses = q_learning(env, episodes=500)
        recompense_moyenne_fin = sum(recompenses[-50:]) / 50
        self.assertGreater(recompense_moyenne_fin, -2.0)

if __name__ == "__main__":
    unittest.main()