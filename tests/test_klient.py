"""Testy klienta HTTP: ponawianie, paginacja, rozpoznawanie błędów.

Kluczowy jest `test_5xx_nie_ponawia_posta`: ponowiony POST tworzy drugą ofertę,
a to konto ma już za sobą sesję z duplikatami.
"""

from unittest import mock

import pytest

import allegro_client as ac
from allegro_client import AllegroAPIError, AllegroClient


def odpowiedz(status=200, dane=None, naglowki=None, tresc=b"{}"):
    r = mock.Mock(status_code=status, headers=naglowki or {}, content=tresc)
    r.json.return_value = dane if dane is not None else {}
    return r


@pytest.fixture(autouse=True)
def bez_prawdziwej_autoryzacji(monkeypatch):
    monkeypatch.setattr(ac, "get_valid_token", lambda: "token-testowy")
    monkeypatch.setattr(ac, "refresh_access_token", lambda uzyty_token=None: "token-nowy")
    monkeypatch.setattr(ac.time, "sleep", lambda s: None)


def test_401_odswieza_token_i_ponawia_raz():
    c = AllegroClient()
    with mock.patch.object(
        c.session, "request", side_effect=[odpowiedz(401), odpowiedz(200, {"ok": True})]
    ) as req:
        assert c.get("/me") == {"ok": True}
    assert req.call_count == 2
    # Drugie zapytanie musi iść z nowym tokenem.
    assert req.call_args_list[1].kwargs["headers"]["Authorization"] == "Bearer token-nowy"


def test_429_ponawia_i_slucha_retry_after():
    c = AllegroClient()
    czekania = []
    with mock.patch.object(ac.time, "sleep", side_effect=czekania.append):
        with mock.patch.object(
            c.session,
            "request",
            side_effect=[
                odpowiedz(429, naglowki={"Retry-After": "7"}),
                odpowiedz(200, {"ok": True}),
            ],
        ):
            assert c.get("/sale/offers") == {"ok": True}
    assert czekania == [7], "Klient ma czekać dokładnie tyle, ile każe API"


def test_429_ponawia_takze_posta():
    """429 znaczy „nie przyjąłem zapytania", więc POST jest bezpieczny."""
    c = AllegroClient()
    with mock.patch.object(
        c.session, "request", side_effect=[odpowiedz(429), odpowiedz(200, {"id": "1"})]
    ) as req:
        assert c.post("/sale/product-offers", json={}) == {"id": "1"}
    assert req.call_count == 2


def test_5xx_nie_ponawia_posta():
    """Ponowiony POST potrafi utworzyć drugą ofertę: wolimy zgłosić błąd."""
    c = AllegroClient()
    with mock.patch.object(c.session, "request", return_value=odpowiedz(502)) as req:
        with pytest.raises(AllegroAPIError) as e:
            c.post("/sale/product-offers", json={})
    assert e.value.status_code == 502
    assert req.call_count == 1, "POST po 5xx nie może być ponawiany"


def test_5xx_ponawia_geta():
    c = AllegroClient()
    with mock.patch.object(
        c.session, "request", side_effect=[odpowiedz(503), odpowiedz(200, {"ok": True})]
    ) as req:
        assert c.get("/me") == {"ok": True}
    assert req.call_count == 2


def test_blad_kolejki_jest_rozpoznawany():
    e = AllegroAPIError(422, "InProgressTaskLimitReachedException: previous changes")
    assert e.to_kolejka is True
    assert AllegroAPIError(422, "cos innego").to_kolejka is False


def test_konflikt_katalogu_jest_rozpoznawany():
    assert AllegroAPIError(422, "EAN already used in catalog").to_konflikt_katalogu
    assert AllegroAPIError(422, "product mismatch").to_konflikt_katalogu
    # Inny kod to nie konflikt katalogu, nawet gdy tekst wspomina o produkcie.
    assert not AllegroAPIError(400, "product mismatch").to_konflikt_katalogu


def test_paginacja_przechodzi_wszystkie_strony():
    c = AllegroClient()
    strony = [
        {"offers": [{"id": "1"}, {"id": "2"}], "totalCount": 3},
        {"offers": [{"id": "3"}], "totalCount": 3},
    ]
    with mock.patch.object(c, "get", side_effect=strony) as g:
        wynik = list(c.paginate("/sale/offers", "offers", limit=2))
    assert [o["id"] for o in wynik] == ["1", "2", "3"]
    assert g.call_args_list[0].kwargs["params"]["offset"] == 0
    assert g.call_args_list[1].kwargs["params"]["offset"] == 2


def test_paginacja_konczy_na_niepelnej_stronie():
    """Brak totalCount nie może zapętlić klienta."""
    c = AllegroClient()
    with mock.patch.object(c, "get", side_effect=[{"offers": [{"id": "1"}]}]) as g:
        wynik = list(c.paginate("/sale/offers", "offers", limit=100))
    assert len(wynik) == 1
    assert g.call_count == 1


def test_paginacja_respektuje_limit_pozycji():
    c = AllegroClient()
    strony = [{"offers": [{"id": str(i)} for i in range(100)], "totalCount": 1000}]
    with mock.patch.object(c, "get", side_effect=strony):
        wynik = list(c.paginate("/sale/offers", "offers", max_pozycji=5))
    assert len(wynik) == 5


def test_czekaj_na_kolejke_ponawia_tylko_ten_blad():
    proby = []

    def zajete():
        proby.append(1)
        if len(proby) < 3:
            raise AllegroAPIError(422, "InProgressTaskLimitReachedException")
        return {"ok": True}

    with mock.patch.object(ac.time, "sleep", lambda s: None):
        assert ac.czekaj_na_kolejke(zajete, prob=5, odstep=0) == {"ok": True}
    assert len(proby) == 3

    # Inny błąd leci w górę od razu.
    with pytest.raises(AllegroAPIError):
        ac.czekaj_na_kolejke(
            mock.Mock(side_effect=AllegroAPIError(400, "zly payload")), prob=3, odstep=0
        )
