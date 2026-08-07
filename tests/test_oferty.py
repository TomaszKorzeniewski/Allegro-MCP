"""Testy budowania ofert i hamulców bezpieczeństwa.

Hamulce sprawdzamy twardo: test ma pilnować, że przy braku potwierdzenia
NIE poszło żadne zapytanie zapisujące.
"""

from unittest import mock

import pytest

import config
import offers as oferty_lib
from allegro_client import AllegroAPIError


# --- strip_params -----------------------------------------------------------

def test_strip_params_zostawia_tylko_to_co_przyjmuje_zapis():
    wejscie = [
        {"id": "1", "name": "Marka", "valuesIds": ["1_2"], "values": ["Dalpo"]},
        {"id": "2", "name": "Szerokość", "values": ["48"]},
        {"id": "3", "name": "Puste"},
    ]
    assert oferty_lib.strip_params(wejscie) == [
        {"id": "1", "valuesIds": ["1_2"]},  # valuesIds ma pierwszeństwo
        {"id": "2", "values": ["48"]},
    ]


def test_strip_params_znosi_brak_danych():
    assert oferty_lib.strip_params(None) == []
    assert oferty_lib.strip_params([]) == []


# --- skroc_nazwe ------------------------------------------------------------

def test_skroc_nazwe_miesci_sie_w_limicie_i_chroni_przyrostek():
    dluga = "Taśma Pakowa Transparentna Akrylowa Cicha 48mm/50m Klejąca do Kartonów"
    wynik = oferty_lib.skroc_nazwe(dluga, "12 szt.")
    assert len(wynik) <= config.MAX_DLUGOSC_NAZWY
    assert wynik.endswith("12 szt."), "Liczba sztuk nie może zniknąć przy skracaniu"


def test_skroc_nazwe_tnie_na_granicy_slowa():
    wynik = oferty_lib.skroc_nazwe("Taśma Pakowa Brązowa Akrylowa Mocna", "6 szt.", limit=25)
    assert len(wynik) <= 25
    assert "  " not in wynik
    assert not wynik.replace(" 6 szt.", "").endswith(" ")


def test_skroc_nazwe_bez_przyrostka():
    assert oferty_lib.skroc_nazwe("a" * 100) == "a" * config.MAX_DLUGOSC_NAZWY


# --- payload ----------------------------------------------------------------

def _payload_przykladowy(**nadpisz):
    dane = dict(
        tytul="Taśma testowa",
        sku="TP/9999",
        cena="9.99",
        opis={"sections": []},
        zdjecia=["https://example.test/1.jpg"],
        parametry_produktu=[{"id": "1", "values": ["x"]}],
    )
    dane.update(nadpisz)
    return oferty_lib.zbuduj_payload_oferty(**dane)


def test_payload_ma_pola_ktorych_brakowalo_staremu_create_offer():
    """Stara wersja pomijała te pola i przez to odbijała się od API."""
    p = _payload_przykladowy()
    assert p["location"] == config.LOCATION
    assert p["delivery"]["shippingRates"]["id"] == config.SHIPPING_RATES_ID
    assert p["delivery"]["handlingTime"] == config.HANDLING_TIME
    assert p["afterSalesServices"]["impliedWarranty"]["id"] == config.WARRANTY_ID
    assert p["afterSalesServices"]["returnPolicy"]["id"] == config.RETURN_POLICY_ID
    assert p["payments"] == {"invoice": "VAT"}
    assert p["external"] == {"id": "TP/9999"}


def test_payload_umieszcza_gpsr_wewnatrz_productset():
    """Na najwyższym poziomie te pola zwracają 422 UnknownJSONProperty."""
    p = _payload_przykladowy()
    element = p["productSet"][0]
    assert element["responsibleProducer"]["id"] == config.RESPONSIBLE_PRODUCER_ID
    assert element["safetyInformation"]["description"] == config.SAFETY_TEXT
    assert element["marketedBeforeGPSRObligation"] is False
    for pole in ("responsibleProducer", "safetyInformation", "marketedBeforeGPSRObligation"):
        assert pole not in p, f"{pole} nie może stać na najwyższym poziomie"


def test_payload_quantity_bez_jednostki():
    """productSet[].quantity przyjmuje samo {"value": N}; z "unit" leci 422."""
    assert _payload_przykladowy()["productSet"][0]["quantity"] == {"value": 1}


def test_payload_zdjecia_to_zwykle_stringi():
    """W `images` idą stringi; obiekty {"url": ...} to format legacy."""
    p = _payload_przykladowy(zdjecia=["https://a.test/1.jpg", "https://a.test/2.jpg"])
    assert all(isinstance(u, str) for u in p["images"])
    assert all(isinstance(u, str) for u in p["productSet"][0]["product"]["images"])


def test_payload_domyslnie_szkic_z_zerowym_stanem():
    """Nowa oferta nie ma nic sprzedać, zanim ją obejrzysz."""
    p = _payload_przykladowy()
    assert p["publication"]["status"] == "INACTIVE"
    assert p["stock"]["available"] == 0


# --- tworzenie oferty i konflikt katalogu -----------------------------------

def test_konflikt_katalogu_zatrzymuje_zamiast_iterowac():
    """Zasada z projektu: przy 422 na EAN stajemy i pytamy o decyzję."""
    klient = mock.Mock()
    klient.post.side_effect = AllegroAPIError(422, "EAN conflict in catalog")

    with pytest.raises(oferty_lib.KonfliktKatalogu) as e:
        oferty_lib.utworz_oferte(klient, _payload_przykladowy())

    assert klient.post.call_count == 1, "Nie wolno próbować kolejnych wariantów"
    for opcja in ("(A)", "(B)", "(C)", "(D)"):
        assert opcja in str(e.value)


def test_brak_parametrow_ponawia_raz_z_kompletem():
    klient = mock.Mock()
    klient.post.side_effect = [
        AllegroAPIError(422, "Uzupełnij parametry obowiązkowe: Materiał"),
        {"id": "123"},
    ]
    zapasowe = [{"id": "236026", "valuesIds": ["236026_1647664"]}]

    wynik = oferty_lib.utworz_oferte(
        klient, _payload_przykladowy(), parametry_zapasowe=zapasowe
    )

    assert wynik == {"id": "123"}
    assert klient.post.call_count == 2
    drugi = klient.post.call_args_list[1].kwargs["json"]
    assert drugi["productSet"][0]["product"]["parameters"] == zapasowe


def test_odmowa_publikacji_schodzi_do_szkicu():
    klient = mock.Mock()
    klient.post.side_effect = [
        AllegroAPIError(400, "nie mogę opublikować"),
        {"id": "456"},
    ]
    wynik = oferty_lib.utworz_oferte(klient, _payload_przykladowy(status="ACTIVE"))

    assert wynik["id"] == "456"
    assert "szkic" in wynik["_uwaga"].lower()
    assert klient.post.call_args_list[1].kwargs["json"]["publication"] == {
        "status": "INACTIVE"
    }


def test_zestaw_kopiuje_karte_produktu_zamiast_budowac_od_zera():
    """Ręcznie budowany productSet odbija się od kategorii 64541 błędem 422."""
    klient = mock.Mock()
    klient.get.return_value = {
        "name": "Taśma Pakowa Brązowa Akrylowa 48mm/45m",
        "external": {"id": "TP/0003"},
        "images": ["https://a.test/1.jpg"],
        "description": {"sections": []},
        "parameters": [{"id": "1", "name": "x", "values": ["a"]}],
        "stock": {"available": 60},
        "productSet": [
            {
                "product": {"id": "KARTA-123", "parameters": []},
                "responsibleProducer": {"id": "PROD-1"},
                "safetyInformation": {"description": "tekst", "type": "TEXT"},
            }
        ],
    }

    p = oferty_lib.zbuduj_payload_zestawu(klient, "111", 6, cena="30.00")

    assert p["productSet"][0]["product"] == {"id": "KARTA-123"}
    assert p["productSet"][0]["quantity"] == {"value": 6}
    assert p["stock"]["available"] == 10  # 60 // 6
    assert p["delivery"]["shippingRates"]["id"] == config.ZESTAW_SHIPPING_ID
    assert p["name"].endswith("6 szt.")


def test_zestaw_odmawia_gdy_oferta_zrodlowa_jest_odpieta():
    klient = mock.Mock()
    klient.get.return_value = {"productSet": [{"product": {"id": None}}]}
    with pytest.raises(ValueError, match="karty produktu"):
        oferty_lib.zbuduj_payload_zestawu(klient, "111", 6, cena="30.00")


def test_odtworzenie_bierze_karte_z_siostry():
    klient = mock.Mock()
    martwa = {
        "name": "Taśma odpięta",
        "category": {"id": "64541"},
        "external": {"id": "TP/0015"},
        "images": [],
        "description": {"sections": []},
        "parameters": [],
        "sellingMode": {"format": "BUY_NOW", "price": {"amount": "4.90"}},
        "stock": {"available": 7},
        "productSet": [{"product": {"id": None}, "quantity": {"value": 1}}],
    }
    siostra = {"productSet": [{"product": {"id": "KARTA-ZYWA"}}]}
    klient.get.side_effect = [martwa, siostra]

    p = oferty_lib.zbuduj_payload_odtworzenia(klient, "martwa", "siostra")

    assert p["productSet"][0]["product"] == {"id": "KARTA-ZYWA"}
    assert p["name"] == "Taśma odpięta"
    assert p["stock"]["available"] == 7


def test_odtworzenie_odmawia_gdy_siostra_tez_odpieta():
    klient = mock.Mock()
    klient.get.side_effect = [
        {"productSet": [{"product": {"id": None}}]},
        {"productSet": [{"product": {"id": None}}]},
    ]
    with pytest.raises(ValueError, match="odpięta"):
        oferty_lib.zbuduj_payload_odtworzenia(klient, "martwa", "siostra")
