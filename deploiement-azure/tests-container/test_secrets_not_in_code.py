import subprocess

# Vérifie qu'aucun secret n'est en dur dans le code de la Tour Community.
PATTERNS = (
    "sk-[a-zA-Z0-9]{16,}",
    "AIza[0-9A-Za-z_-]{20,}",
    "sk-or-v1-",
    "AQ\\.[A-Za-z0-9_-]{8,}",
)


def test_secrets_not_hardcoded():
    found = []
    for pat in PATTERNS:
        r = subprocess.run(
            ["grep", "-rn", "--include=*.py", "-E", pat,
             "/workspace/tour-community/custom-addons/",
             "--exclude-dir=__pycache__", "--exclude-dir=.git"],
            capture_output=True, text=True, timeout=60)
        if r.stdout:
            found.append(r.stdout)
    if found:
        print("⚠️ Secrets potentiels en clair :")
        for block in found:
            print(block)
        raise AssertionError("Des clés API sont en clair dans le code")
    print("✅ Aucun secret trouvé en clair dans le code de la Tour")


if __name__ == "__main__":
    test_secrets_not_hardcoded()
