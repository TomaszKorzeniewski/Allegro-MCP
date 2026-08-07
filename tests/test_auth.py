"""Testy autoryzacji: rotacja tokenu, blokada, wygasanie.

Najważniejszy jest `test_rownolegly_proces_nie_pali_refresh_tokenu`: to on
pilnuje błędu, który potrafi trwale odciąć konto od API.
"""

import multiprocessing
import os
import time
from unittest import mock

import pytest

import auth


@pytest.fixture
def env_tymczasowy(tmp_path, monkeypatch):
    """Podstawia `.env` i `.env.lock` w katalogu tymczasowym."""
    env = tmp_path / ".env"
    env.write_text(
        "ALLEGRO_CLIENT_ID=id-testowe\n"
        "ALLEGRO_CLIENT_SECRET=sekret-testowy\n"
        "ALLEGRO_ACCESS_TOKEN=stary-access\n"
        "ALLEGRO_REFRESH_TOKEN=stary-refresh\n"
    )
    monkeypatch.setattr(auth, "ENV_PATH", env)
    monkeypatch.setattr(auth, "LOCK_PATH", tmp_path / ".env.lock")
    for k in list(os.environ):
        if k.startswith("ALLEGRO_"):
            monkeypatch.delenv(k, raising=False)
    auth._przeladuj_env()
    return env


def test_wartosc_zdejmuje_apostrofy(monkeypatch):
    """dotenv zapisuje w apostrofach, a Allegro odrzuca taki token przez 401."""
    monkeypatch.setenv("ALLEGRO_ACCESS_TOKEN", "'token-w-apostrofach'")
    assert auth._wartosc("ALLEGRO_ACCESS_TOKEN") == "token-w-apostrofach"

    monkeypatch.setenv("ALLEGRO_ACCESS_TOKEN", '"token-w-cudzyslowie"')
    assert auth._wartosc("ALLEGRO_ACCESS_TOKEN") == "token-w-cudzyslowie"


def test_token_wazny_uwzglednia_margines(monkeypatch):
    """Token wygasający za chwilę traktujemy jak wygasły."""
    monkeypatch.setenv("ALLEGRO_ACCESS_TOKEN", "cokolwiek")

    monkeypatch.setenv("ALLEGRO_TOKEN_EXPIRES_AT", str(int(time.time()) + 3600))
    assert auth._token_wazny() is True

    # Wygasa wcześniej, niż wynosi margines bezpieczeństwa.
    monkeypatch.setenv(
        "ALLEGRO_TOKEN_EXPIRES_AT",
        str(int(time.time()) + auth.MARGINES_WYGASNIECIA - 10),
    )
    assert auth._token_wazny() is False

    monkeypatch.setenv("ALLEGRO_TOKEN_EXPIRES_AT", str(int(time.time()) - 1))
    assert auth._token_wazny() is False


def test_brak_znacznika_wygasania_nie_wymusza_odswiezenia(monkeypatch):
    """`.env` sprzed tej zmiany nie ma znacznika, a mimo to ma działać.

    Gdyby brak znacznika znaczył „odśwież", wdrożenie spaliłoby refresh token
    bez potrzeby na każdym istniejącym koncie.
    """
    monkeypatch.delenv("ALLEGRO_TOKEN_EXPIRES_AT", raising=False)
    monkeypatch.setenv("ALLEGRO_ACCESS_TOKEN", "istniejacy-token")
    assert auth._token_wazny() is True


def test_zapis_tokenow_ustawia_wygasanie(env_tymczasowy, monkeypatch):
    monkeypatch.setattr(time, "time", lambda: 1_000_000.0)
    auth._zapisz_tokeny(
        {
            "access_token": "nowy-access",
            "refresh_token": "nowy-refresh",
            "expires_in": 43200,
        }
    )
    tresc = env_tymczasowy.read_text()
    assert "nowy-access" in tresc
    assert "nowy-refresh" in tresc
    assert str(1_000_000 + 43200) in tresc


def test_rownolegly_proces_nie_pali_refresh_tokenu(env_tymczasowy):
    """Gdy inny proces zdążył odświeżyć, korzystamy z jego wyniku.

    To jest zabezpieczenie przed najgroźniejszym błędem tego projektu: refresh
    token jest jednorazowy, więc dwa równoległe odświeżenia unieważniają konto.
    """
    # Symulujemy: na dysku leży już token nowszy niż ten, który dostał 401.
    env_tymczasowy.write_text(
        "ALLEGRO_CLIENT_ID=id-testowe\n"
        "ALLEGRO_CLIENT_SECRET=sekret-testowy\n"
        "ALLEGRO_ACCESS_TOKEN=token-od-innego-procesu\n"
        "ALLEGRO_REFRESH_TOKEN=refresh-od-innego-procesu\n"
    )

    with mock.patch.object(auth.requests, "post") as post:
        wynik = auth.refresh_access_token(uzyty_token="moj-stary-token")

    assert wynik == "token-od-innego-procesu"
    post.assert_not_called(), "Nie wolno odświeżać, skoro zrobił to inny proces"


def test_odswiezenie_gdy_token_faktycznie_nasz(env_tymczasowy):
    """Gdy na dysku leży ten sam token, który dostał 401, odświeżamy naprawdę."""
    odpowiedz = mock.Mock(status_code=200)
    odpowiedz.json.return_value = {
        "access_token": "swiezy-access",
        "refresh_token": "swiezy-refresh",
        "expires_in": 43200,
    }
    with mock.patch.object(auth.requests, "post", return_value=odpowiedz) as post:
        wynik = auth.refresh_access_token(uzyty_token="stary-access")

    assert wynik == "swiezy-access"
    post.assert_called_once()


def _zajmij_blokade(sciezka, gotowy, zwolnij):
    """Pomocnik do testu międzyprocesowego (musi być na poziomie modułu)."""
    import auth as a

    a.LOCK_PATH = sciezka
    with a._blokada():
        gotowy.set()
        zwolnij.wait(timeout=10)


def test_blokada_jest_wylaczna_miedzy_procesami(tmp_path, monkeypatch):
    """Drugi proces nie wejdzie pod blokadę, dopóki pierwszy jej nie odda."""
    lock = tmp_path / ".env.lock"
    monkeypatch.setattr(auth, "LOCK_PATH", lock)
    monkeypatch.setattr(auth, "TIMEOUT_BLOKADY", 1)

    ctx = multiprocessing.get_context("fork")
    gotowy, zwolnij = ctx.Event(), ctx.Event()
    p = ctx.Process(target=_zajmij_blokade, args=(lock, gotowy, zwolnij))
    p.start()
    try:
        assert gotowy.wait(timeout=10), "Proces potomny nie zdobył blokady"
        with pytest.raises(RuntimeError, match="blokad"):
            with auth._blokada():
                pass
    finally:
        zwolnij.set()
        p.join(timeout=10)

    # Po zwolnieniu blokada znów jest do wzięcia.
    with auth._blokada():
        pass
