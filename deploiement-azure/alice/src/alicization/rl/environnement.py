#!/usr/bin/env python3
# /home/orel/alicization/rl/environnement.py
# Environnement de test pour RL (Donjon simplifié)

import gymnasium as gym
from gymnasium import spaces
import numpy as np

class DonjonSimpleEnv(gym.Env):
    """
    Environnement minimal : un agent doit se déplacer vers une cible.
    - État : position de l'agent (x, y) et position de la cible (x, y) → 4 entiers
    - Action : 0=haut, 1=bas, 2=gauche, 3=droite
    - Récompense : +1 si atteint la cible, -1 si sort du cadre, -0.1 par pas
    """

    def __init__(self, size=5):
        super().__init__()
        self.size = size
        self.observation_space = spaces.Box(low=0, high=size-1, shape=(4,), dtype=np.int32)
        self.action_space = spaces.Discrete(4)

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.agent_pos = np.array([0, 0])
        self.target_pos = np.array([self.size-1, self.size-1])
        return np.concatenate([self.agent_pos, self.target_pos]), {}

    def step(self, action):
        # Déplacement
        if action == 0: self.agent_pos[1] = max(0, self.agent_pos[1] - 1)
        elif action == 1: self.agent_pos[1] = min(self.size-1, self.agent_pos[1] + 1)
        elif action == 2: self.agent_pos[0] = max(0, self.agent_pos[0] - 1)
        elif action == 3: self.agent_pos[0] = min(self.size-1, self.agent_pos[0] + 1)

        # Récompense
        if np.array_equal(self.agent_pos, self.target_pos):
            reward = 1.0
            done = True
        elif self.agent_pos[0] < 0 or self.agent_pos[0] >= self.size or self.agent_pos[1] < 0 or self.agent_pos[1] >= self.size:
            reward = -1.0
            done = True
        else:
            reward = -0.1
            done = False

        return np.concatenate([self.agent_pos, self.target_pos]), reward, done, False, {}