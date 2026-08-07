"""Testy hamulców bezpieczeństwa w narzędziach MCP.

Te narzędzia wywołuje model na koncie produkcyjnym ze 115 aktywnymi ofertami.
Każdy test sprawdza to samo: bez jawnego potwierdzenia NIE poszło żadne
zapytanie zapisujące (PUT, POST, PATCH, DELETE).
"""

from unittest import mock

import pytest

import server


@pytest.fixture
def klient(monkeypatch):
    """Podstawia klienta API, żeby żaden test nie dotknął produkcji."""
    fake = mock.Mock()
    monkeypatch.setattr(server, "client", fake)
    return fake


def zapytania_zapisujace(fake):
    """Ile razy wywołano cokolwiek, co zmienia stan na Allegro."""
    return (
        fake.put.call_count
        + fake.post.call_count
        + fake.patch.call_count
        + fake.delete.call_count
    )


# --- end_offer --------------------------------------------------------------

def test_end_offer_bez_potwierdzenia_nic_nie_konczy(klient):
    klient.get.return_value = {
        "name": "Taśma testowa",
        "external": {"id": "TP/0001"},
        "publication": {"status": "ACTIVE"},
        "stock": {"available": 12},
        "sellingMode": {"price": {"amount": "4.90"}},
    }

    wynik = server.end_offer("18791552054")

    assert wynik["wykonano"] is False
    assert zapytania_zapisujace(klient) == 0, "Oferta nie mogła zostać zakończona"
    # Podgląd ma pozwolić sprawdzić, czy to na pewno ta oferta.
    assert wynik["oferta_do_zakonczenia"]["nazwa"] == "Taśma testowa"
    assert wynik["oferta_do_zakonczenia"]["sku"] == "TP/0001"


def test_end_offer_z_potwierdzeniem_wysyla_polecenie_zakonczenia(klient):
    klient.get.return_value = {
        "name": "Taśma testowa",
        "external": {"id": "TP/0001"},
        "publication": {"status": "ACTIVE"},
        "stock": {"available": 12},
        "sellingMode": {"price": {"amount": "4.90"}},
    }
    klient.put.return_value = {"status": "OK"}

    wynik = server.end_offer("18791552054", potwierdzam=True)

    assert wynik["wykonano"] is True
    klient.put.assert_called_once()
    sciezka = klient.put.call_args[0][0]
    payload = klient.put.call_args.kwargs["json"]
    assert sciezka.startswith("/sale/offer-publication-commands/")
    assert payload["publication"]["action"] == "END"
    assert payload["offerCriteria"][0]["offers"] == [{"id": "18791552054"}]


# --- cenniki dostawy --------------------------------------------------------

def test_update_shipping_rate_bez_zastosuj_nic_nie_zapisuje(klient):
    klient.get.side_effect = [
        {
            "id": "CEN-1",
            "name": "tuba 13x13x120",
            "type": "PHYSICAL",
            "dispatchCountry": "PL",
            "rates": [
                {"deliveryMethod": {"id": "M-KURIER"}},
                {"deliveryMethod": {"id": "M-PACZKOMAT"}},
            ],
        },
        {
            "deliveryMethods": [
                {"id": "M-KURIER", "name": "Allegro Kurier DPD"},
                {"id": "M-PACZKOMAT", "name": "Allegro One Box"},
            ]
        },
    ]

    wynik = server.update_shipping_rate(
        "CEN-1", metody=[{"delivery_method_id": "M-KURIER"}]
    )

    assert wynik["wykonano"] is False
    assert zapytania_zapisujace(klient) == 0
    # Podgląd musi nazwać po imieniu to, co zniknie z cennika.
    assert wynik["zmiany"]["usuwane"] == ["Allegro One Box"]
    assert wynik["zmiany"]["pozostajace"] == ["Allegro Kurier DPD"]


def test_update_shipping_rate_z_zastosuj_wysyla_komplet_wymaganych_pol(klient):
    klient.get.side_effect = [
        {
            "id": "CEN-1",
            "name": "tuba 13x13x120",
            "type": "PHYSICAL",
            "dispatchCountry": "PL",
            "rates": [{"deliveryMethod": {"id": "M-PACZKOMAT"}}],
        },
        {"deliveryMethods": [{"id": "M-KURIER", "name": "Kurier"}]},
    ]
    klient.put.return_value = {"id": "CEN-1"}

    wynik = server.update_shipping_rate(
        "CEN-1",
        metody=[
            {
                "delivery_method_id": "M-KURIER",
                "max_sztuk_w_paczce": 4,
                "pierwsza_sztuka": "14.99",
                "kolejna_sztuka": "0.00",
            }
        ],
        zastosuj=True,
    )

    assert wynik["wykonano"] is True
    payload = klient.put.call_args.kwargs["json"]
    # Pola wymagane przez API od 09.04.2026.
    assert payload["type"] == "PHYSICAL"
    assert payload["dispatchCountry"] == "PL"
    assert payload["rates"][0]["firstItemRate"] == {
        "amount": "14.99",
        "currency": "PLN",
    }


def test_create_shipping_rate_bez_zastosuj_nic_nie_tworzy(klient):
    klient.get.return_value = {
        "deliveryMethods": [{"id": "M-KURIER", "name": "Kurier DPD"}]
    }

    wynik = server.create_shipping_rate(
        "nowy cennik", metody=[{"delivery_method_id": "M-KURIER"}]
    )

    assert wynik["wykonano"] is False
    assert zapytania_zapisujace(klient) == 0
    assert wynik["cennik_do_utworzenia"]["metody"] == ["Kurier DPD"]


def test_create_shipping_rate_domyslnie_towar_fizyczny_z_polski(klient):
    klient.post.return_value = {"id": "NOWY"}
    server.create_shipping_rate(
        "nowy", metody=[{"delivery_method_id": "M"}], zastosuj=True
    )
    payload = klient.post.call_args.kwargs["json"]
    assert payload["type"] == "PHYSICAL"
    assert payload["dispatchCountry"] == "PL"


# --- pozostałe --------------------------------------------------------------

def test_search_categories_pyta_wlasciwy_endpoint(klient):
    """Poprzednia wersja pytała /sale/categories, co ignorowało frazę."""
    server.search_categories("taśma pakowa")
    klient.get.assert_called_once_with(
        "/sale/matching-categories", params={"name": "taśma pakowa"}
    )


def test_get_shipment_label_nie_zwraca_tresci_pdf(klient, tmp_path, monkeypatch):
    """Zwracamy ścieżkę, nie base64: PDF w odpowiedzi zapycha kontekst."""
    monkeypatch.setattr(server, "KATALOG_ETYKIET", tmp_path / "etykiety")
    klient.post.return_value = b"%PDF-1.4 udawany plik"

    wynik = server.get_shipment_label("SHIP-1")

    assert set(wynik) == {"zapisano_do", "rozmiar_bajtow"}
    assert "base64" not in wynik
    assert wynik["rozmiar_bajtow"] == len(b"%PDF-1.4 udawany plik")
    # Plik ma wylądować w katalogu projektu, nie w katalogu roboczym procesu.
    assert (tmp_path / "etykiety").exists()


def test_update_offer_idzie_od_razu(klient):
    """Zmiana ceny jest odwracalna, więc nie ma powodu jej hamować."""
    klient.patch.return_value = {"ok": True}
    server.update_offer("123", {"stock": {"available": 5}})
    klient.patch.assert_called_once()
