#!/usr/bin/env python3
# /home/orel/alicization/rl/entrainer.py
# Entraînement RL (Q-Learning simple, pas de réseau de neurones)

import numpy as np
import json

try:
    from .environnement import DonjonSimpleEnv
except ImportError:
    from environnement import DonjonSimpleEnv


def etat_a_index(obs, size):
    """obs = [ax, ay, tx, ty] → index entier unique dans la table Q."""
    ax, ay, tx, ty = [int(v) for v in obs]
    return ax + ay * size + tx * size * size + ty * size * size * size


def index_a_etat(idx, size):
    """index → (ax, ay, tx, ty). L'inverse de etat_a_index."""
    idx = int(idx)
    ax = idx % size; idx //= size
    ay = idx % size; idx //= size
    tx = idx % size
    ty = idx // size
    return ax, ay, tx, ty


def q_learning(env, episodes=1000, alpha=0.1, gamma=0.9, epsilon=0.1):
    """Q-Learning sur l'environnement Donjon."""
    size = env.size
    nb_etats = size * size * size * size  # positions agent + cible
    nb_actions = env.action_space.n
    Q = np.zeros((nb_etats, nb_actions))

    recompenses = []
    for episode in range(episodes):
        obs, _ = env.reset()
        idx = etat_a_index(obs, size)
        done = False
        total_reward = 0
        while not done:
            if np.random.random() < epsilon:
                action = env.action_space.sample()
            else:
                action = np.argmax(Q[idx])
            new_obs, reward, done, _, _ = env.step(action)
            new_idx = etat_a_index(new_obs, size)
            Q[idx, action] = Q[idx, action] + alpha * (reward + gamma * np.max(Q[new_idx]) - Q[idx, action])
            idx = new_idx
            total_reward += reward
        recompenses.append(total_reward)

    # Extraire la politique : la meilleure action pour chaque état
    politique = {}
    for i in range(nb_etats):
        politique[str(i)] = int(np.argmax(Q[i]))
    return Q, politique, recompenses


def sauvegarder_politique(politique, chemin):
    """Sauvegarde la politique apprise dans un fichier JSON."""
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(politique, f, ensure_ascii=False)


def charger_politique(chemin):
    """Recharge une politique apprise depuis un fichier JSON."""
    with open(chemin, "r", encoding="utf-8") as f:
        return json.load(f)


def action_pour_position(size, position, cible, politique):
    """
    Depuis la politique apprise, retourne l'action pour un état donné.
    position = [x, y] de l'agent ; cible = [x, y] ; action : 0=haut,1=bas,2=gauche,3=droite.
    """
    idx = etat_a_index([position[0], position[1], cible[0], cible[1]], size)
    return int(politique[str(idx)])


def exporter_politique_vers_circuit(politique, nom="Se déplacer vers la cible", taille=5):
    """
    Exporte la politique RL sous forme de circuit Alice.

    Les étapes condensent la VRAIE table Q : pour chaque écart (cible − agent)
    rencontré dans l'apprentissage, on garde l'action dominante apprise.
    (Bon compromis : quelques règles, pas les taille^4 états bruts.)
    """
    regles = {}
    for cle, action in politique.items():
        ax, ay, tx, ty = index_a_etat(int(cle), taille)
        dx, dy = tx - ax, ty - ay
        if dx == 0 and dy == 0:
            continue
        regles.setdefault((dx, dy), []).append(action)

    etapes = ["Actions : 0=haut, 1=bas, 2=gauche, 3=droite"]
    for (dx, dy) in sorted(regles, key=lambda k: (k[1], k[0])):
        actions = regles[(dx, dy)]
        dominante = max(set(actions), key=actions.count)
        etapes.append(f"Si la cible est à dx={dx:+d}, dy={dy:+d} : action {dominante}")

    return {
        "nom": nom,
        "type": "circuit",
        "description": "Politique RL apprise par Q-Learning sur une grille %dx%d "
                       "(vraie table Q compressée par écart cible-agent)" % (taille, taille),
        "mots_cles": ["rl", "deplacement", "cible"],
        "etapes": etapes
    }


if __name__ == "__main__":
    env = DonjonSimpleEnv(size=5)
    Q, politique, recompenses = q_learning(env, episodes=1000)
    print("RL entraîné. Récompense moyenne :", sum(recompenses[-100:])/100)
    # Exporter la politique sous forme de circuit
    circuit = exporter_politique_vers_circuit(politique, taille=5)
    print("Circuit exporté :", circuit["nom"], "|", len(circuit["etapes"])-1, "règles")
    print(json.dumps(circuit, ensure_ascii=False, indent=2))