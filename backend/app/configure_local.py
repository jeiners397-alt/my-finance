"""Create a local .env with a random dashboard token without printing it."""

from pathlib import Path
import secrets

if __name__ == "__main__":
    path = Path(".env")
    if path.exists():
        raise SystemExit(".env ya existe; no se sobrescribió.")
    template = Path(".env.example").read_text()
    template = template.replace(
        "replace-with-a-unique-random-token-at-least-32-characters",
        secrets.token_urlsafe(48),
    )
    path.write_text(template)
    path.chmod(0o600)
    print("Creado .env local. El token está en ACCOUNT_TOKENS; no lo subas a GitHub.")
