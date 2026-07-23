"""Klient HTTP do Allegro REST API (PRODUKCJA: https://api.allegro.pl).

Automatycznie dodaje nagłówek Authorization i przy 401 odświeża token
oraz ponawia request jeden raz.
"""

import logging

import requests

from auth import get_valid_token, refresh_access_token

logger = logging.getLogger(__name__)

BASE_URL = "https://api.allegro.pl"
CONTENT_TYPE = "application/vnd.allegro.public.v1+json"


class AllegroAPIError(Exception):
    """Błąd zwrócony przez Allegro API."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"Allegro API error {status_code}: {message}")


class AllegroClient:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

    def _headers(self, token: str, accept: str = CONTENT_TYPE) -> dict:
        return {
            "Authorization": f"Bearer {token}",
            "Accept": accept,
            "Content-Type": CONTENT_TYPE,
        }

    def request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        json: dict | None = None,
        accept: str = CONTENT_TYPE,
        raw: bool = False,
    ):
        """Wykonuje request do API. Przy 401 odświeża token i ponawia raz.

        raw=True zwraca surowe bajty (np. etykiety PDF) zamiast JSON-a.
        """
        url = f"{self.base_url}{path}"
        token = get_valid_token()

        for attempt in (1, 2):
            resp = self.session.request(
                method,
                url,
                headers=self._headers(token, accept),
                params=params,
                json=json,
                timeout=60,
            )
            if resp.status_code == 401 and attempt == 1:
                logger.warning("401 z API — odświeżam token i ponawiam request.")
                token = refresh_access_token()
                continue
            break

        if resp.status_code >= 400:
            try:
                errors = resp.json().get("errors", [])
                message = "; ".join(
                    e.get("userMessage") or e.get("message", "") for e in errors
                ) or resp.text
            except (ValueError, AttributeError):
                message = resp.text
            logger.error("%s %s -> %s: %s", method, path, resp.status_code, message)
            raise AllegroAPIError(resp.status_code, message)

        if raw:
            return resp.content
        if resp.status_code == 204 or not resp.content:
            return {"status": "ok", "http_status": resp.status_code}
        return resp.json()

    # Skróty
    def get(self, path: str, params: dict | None = None, **kwargs):
        return self.request("GET", path, params=params, **kwargs)

    def post(self, path: str, json: dict | None = None, **kwargs):
        return self.request("POST", path, json=json, **kwargs)

    def patch(self, path: str, json: dict | None = None, **kwargs):
        return self.request("PATCH", path, json=json, **kwargs)

    def delete(self, path: str, **kwargs):
        return self.request("DELETE", path, **kwargs)
