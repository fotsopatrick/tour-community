import requests
import subprocess

# Config de Chloé : le moteur doit être DeepSeek.
# La valeur vit dans ir_config_parameter (pas de route publique /config).
# On la lit via la base Odoo (psql) faute de route dédiée.


def test_chloe_uses_deepseek():
    r = subprocess.run(
        ["psql", "-h", "127.0.0.1", "-U", "odoo", "-d", "odoo", "-tAc",
         "SELECT value FROM ir_config_parameter "
         "WHERE key='tour_community_chat.moteur'"],
        env={"PGPASSWORD": "odoo", "PATH": "/usr/bin:/bin"},
        capture_output=True, text=True, timeout=10)
    moteur = r.stdout.strip()
    assert moteur == "deepseek", f"Chloé n'utilise pas DeepSeek (moteur={moteur!r})"
    print("✅ Chloé configurée avec DeepSeek")


if __name__ == "__main__":
    test_chloe_uses_deepseek()
