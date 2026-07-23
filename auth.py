"""OAuth 2.0 Device Flow dla Allegro API (PRODUKCJA).

Uruchom bezpośrednio, żeby się autoryzować:
    python auth.py

Moduł udostępnia też:
    get_valid_token()      - zwraca aktualny access token (odświeża jeśli trzeba)
    refresh_access_token() - wymusza odświeżenie tokenu
"""

import base64
import logging
import os
import sys
import time
import webbrowser
from pathlib import Path

import requests
from dotenv import load_dotenv, set_key

logger = logging.getLogger(__name__)

ENV_PATH = Path(__file__).parent / ".env"
AUTH_BASE = "https://allegro.pl/auth/oauth"
DEVICE_URL = f"{AUTH_BASE}/device"
TOKEN_URL = f"{AUTH_BASE}/token"

load_dotenv(ENV_PATH)


def _client_credentials() -> tuple[str, str]:
    client_id = os.getenv("ALLEGRO_CLIENT_ID", "").strip()
    client_secret = os.getenv("ALLEGRO_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise RuntimeError(
            "Brak ALLEGRO_CLIENT_ID lub ALLEGRO_CLIENT_SECRET w pliku .env"
        )
    return client_id, client_secret


def _basic_auth_header() -> dict:
    client_id, client_secret = _client_credentials()
    creds = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    return {"Authorization": f"Basic {creds}"}


def _save_tokens(access_token: str, refresh_token: str) -> None:
    set_key(ENV_PATH, "ALLEGRO_ACCESS_TOKEN", access_token)
    set_key(ENV_PATH, "ALLEGRO_REFRESH_TOKEN", refresh_token)
    os.environ["ALLEGRO_ACCESS_TOKEN"] = access_token
    os.environ["ALLEGRO_REFRESH_TOKEN"] = refresh_token


def device_flow_authorize() -> str:
    """Pełny device flow: pokazuje kod, czeka na autoryzację, zapisuje tokeny."""
    client_id, _ = _client_credentials()

    resp = requests.post(
        DEVICE_URL,
        headers={
            **_basic_auth_header(),
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"client_id": client_id},
        timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"Nie udało się rozpocząć device flow ({resp.status_code}): {resp.text}"
        )
    data = resp.json()

    verification_uri = data.get("verification_uri_complete") or data.get(
        "verification_uri"
    )
    user_code = data.get("user_code", "")
    device_code = data["device_code"]
    interval = int(data.get("interval", 5))
    expires_in = int(data.get("expires_in", 600))

    print("\n=== Autoryzacja Allegro ===")
    print(f"Otwórz w przeglądarce: {verification_uri}")
    if user_code:
        print(f"Kod użytkownika: {user_code}")
    print(f"(kod wygasa za {expires_in // 60} min)\n")
    try:
        webbrowser.open(verification_uri)
    except Exception:
        pass

    deadline = time.time() + expires_in
    while time.time() < deadline:
        time.sleep(interval)
        token_resp = requests.post(
            TOKEN_URL,
            headers={**_basic_auth_header()},
            params={
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "device_code": device_code,
            },
            timeout=30,
        )
        if token_resp.status_code == 200:
            tokens = token_resp.json()
            _save_tokens(tokens["access_token"], tokens["refresh_token"])
            print("Autoryzacja zakończona — tokeny zapisane w .env")
            return tokens["access_token"]

        error = token_resp.json().get("error", "")
        if error == "authorization_pending":
            continue
        if error == "slow_down":
            interval += 5
            continue
        raise RuntimeError(f"Autoryzacja nieudana: {error} — {token_resp.text}")

    raise RuntimeError("Kod urządzenia wygasł — uruchom autoryzację ponownie.")


def refresh_access_token() -> str:
    """Odświeża access token przy pomocy refresh tokenu. Zapisuje nowe tokeny."""
    refresh_token = os.getenv("ALLEGRO_REFRESH_TOKEN", "").strip()
    if not refresh_token:
        raise RuntimeError(
            "Brak refresh tokenu — uruchom `python auth.py`, żeby się autoryzować."
        )
    resp = requests.post(
        TOKEN_URL,
        headers={**_basic_auth_header()},
        params={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"Odświeżenie tokenu nieudane ({resp.status_code}): {resp.text}. "
            "Uruchom `python auth.py`, żeby autoryzować ponownie."
        )
    tokens = resp.json()
    _save_tokens(tokens["access_token"], tokens["refresh_token"])
    logger.info("Access token odświeżony.")
    return tokens["access_token"]


def get_valid_token() -> str:
    """Zwraca aktualny access token; jeśli go nie ma, próbuje refresh."""
    load_dotenv(ENV_PATH, override=True)
    token = os.getenv("ALLEGRO_ACCESS_TOKEN", "").strip()
    if token:
        return token
    return refresh_access_token()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        device_flow_authorize()
    except RuntimeError as e:
        print(f"BŁĄD: {e}", file=sys.stderr)
        sys.exit(1)
