"""Serwer MCP dla Allegro REST API, konto buy-pack (PRODUKCJA).

Uruchomienie:
    python server.py          (transport stdio, do konfiguracji klienta MCP)

Zabezpieczenie operacji zapisu
------------------------------
To jest konto produkcyjne z ponad setką aktywnych ofert, a narzędzia wywołuje
model. Dlatego operacje nieodwracalne i masowe mają hamulec:

    potwierdzam=True   wymagane tam, gdzie zmiany nie da się cofnąć
                       (zakończenie oferty)
    zastosuj=True      wymagane przy operacjach masowych; bez tego narzędzie
                       pokazuje, co ZAMIERZA zrobić, i nic nie wysyła

Pojedyncza zmiana ceny albo stanu idzie od razu, bo jest odwracalna.
Parametry sterujące są po polsku celowo: mają rzucać się w oczy pośród
pól technicznych zapożyczonych z API Allegro.
"""

import logging
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

import config
import offers as oferty_lib
from allegro_client import (
    BETA_CONTENT_TYPE,
    AllegroAPIError,
    AllegroClient,
    czekaj_na_kolejke,
)

logging.basicConfig(level=logging.INFO)

mcp = FastMCP("allegro")
client = AllegroClient()

# Etykiety przesyłek lądują tutaj, a nie w katalogu roboczym procesu.
KATALOG_ETYKIET = Path(__file__).parent / "etykiety"


# ---------------------------------------------------------------------------
# Oferty (allegro:api:sale:offers:read/write)
# ---------------------------------------------------------------------------

@mcp.tool()
def list_offers(status: str = "", limit: int = 20, offset: int = 0) -> dict:
    """Lista ofert sprzedawcy. status: ACTIVE, INACTIVE, ACTIVATING lub ENDED
    (puste = wszystkie).

    Uwaga: świeżo wystawiona oferta potrafi kilkadziesiąt minut wisieć jako
    INACTIVE, mimo że ma ustawione ACTIVE. Licząc stany, pobieraj oba statusy.
    """
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if status:
        params["publication.status"] = status
    return client.get("/sale/offers", params=params)


@mcp.tool()
def get_offer(offer_id: str) -> dict:
    """Pobiera pełne dane oferty po jej ID."""
    return client.get(f"/sale/product-offers/{offer_id}")


@mcp.tool()
def create_offer(
    name: str,
    sku: str,
    description_html: str,
    image_urls: list[str],
    price: str,
    stock: int = 0,
    status: str = "INACTIVE",
    category_id: str = "",
) -> dict:
    """Tworzy ofertę produktową z kompletem pól wymaganych przez Allegro.

    Domyślnie powstaje szkic (INACTIVE) z zerowym stanem, żeby dało się ją
    obejrzeć przed sprzedażą. Stan ustawisz potem przez `update_offer`.

    price w formacie "123.45" (brutto, PLN). sku trafia do `external.id`.
    Zasada z projektu: bez przyrostka "-1" dla ofert pojedynczych.

    Czego to narzędzie NIE zrobi:
    - zestawów wielosztukowych, od tego jest `create_offer_set`
      (kategoria 64541 odbija ręcznie budowany productSet błędem 422),
    - obejścia konfliktu EAN. Przy takim błędzie zatrzyma się i wypisze
      cztery możliwe decyzje, zamiast próbować w kółko innych danych.
    """
    if not image_urls:
        raise ValueError("Oferta wymaga co najmniej jednego zdjęcia.")

    payload = oferty_lib.zbuduj_payload_oferty(
        tytul=oferty_lib.skroc_nazwe(name),
        sku=sku,
        cena=price,
        opis={
            "sections": [
                {"items": [{"type": "TEXT", "content": description_html}]}
            ]
        },
        zdjecia=image_urls,
        parametry_produktu=[],
        stan=stock,
        status=status,
        category_id=category_id or None,
    )
    try:
        return oferty_lib.utworz_oferte(client, payload)
    except oferty_lib.KonfliktKatalogu as e:
        return {"blad": "konflikt_katalogu", "opis": str(e)}


@mcp.tool()
def create_offer_set(
    offer_id_pojedynczej: str,
    sztuk: int,
    price: str,
    sku: str = "",
) -> dict:
    """Tworzy ofertę zestawu N sztuk na bazie istniejącej oferty pojedynczej.

    Kopiuje kartę produktu z żywej oferty (Allegro już ją zaakceptowało)
    i zmienia tylko liczbę sztuk. Bez tego kategoria taśm odbija zestaw
    błędem 422. Zestaw dostaje własny cennik dostawy, inny niż sztuka.
    """
    payload = oferty_lib.zbuduj_payload_zestawu(
        client, offer_id_pojedynczej, sztuk, cena=price, sku=sku or None
    )
    parametry = oferty_lib.strip_params(
        client.get(f"/sale/product-offers/{offer_id_pojedynczej}")
        .get("productSet", [{}])[0]
        .get("product", {})
        .get("parameters")
    )
    try:
        return oferty_lib.utworz_oferte(
            client, payload, parametry_zapasowe=parametry
        )
    except oferty_lib.KonfliktKatalogu as e:
        return {"blad": "konflikt_katalogu", "opis": str(e)}


@mcp.tool()
def recreate_detached_offer(offer_id_martwej: str, offer_id_siostry: str) -> dict:
    """Odtwarza ofertę zakończoną przez PRODUCT_DETACHMENT.

    Gdy Allegro scali lub usunie kartę produktu, odpina od niej ofertę
    i ją kończy (publication.endedBy = PRODUCT_DETACHMENT, product.id = null).
    Takiej oferty nie da się wznowić, trzeba wystawić nową. To narzędzie
    kopiuje payload martwej oferty i bierze kartę produktu z żywej oferty
    siostrzanej tego samego SKU.
    """
    payload = oferty_lib.zbuduj_payload_odtworzenia(
        client, offer_id_martwej, offer_id_siostry
    )
    try:
        return oferty_lib.utworz_oferte(client, payload)
    except oferty_lib.KonfliktKatalogu as e:
        return {"blad": "konflikt_katalogu", "opis": str(e)}


@mcp.tool()
def update_offer(offer_id: str, fields_to_update: dict) -> dict:
    """Aktualizuje ofertę (PATCH). fields_to_update to fragment struktury oferty,
    na przykład {"sellingMode": {"price": {"amount": "99.00", "currency": "PLN"}}}
    albo {"stock": {"available": 5}}.

    Zmiana ceny czy stanu jest odwracalna, więc idzie od razu, bez potwierdzania.
    """
    return client.patch(f"/sale/product-offers/{offer_id}", json=fields_to_update)


@mcp.tool()
def end_offer(offer_id: str, potwierdzam: bool = False) -> dict:
    """Kończy ofertę. NIEODWRACALNE: zakończonej oferty nie da się wznowić.

    Wymaga potwierdzam=True. Bez tego zwraca podgląd oferty, która miałaby
    zostać zakończona, żeby dało się sprawdzić, czy to na pewno ta właściwa.

    Używa polecenia publikacji (a nie DELETE, które działa tylko na szkicach),
    więc kończy również oferty aktywne.
    """
    oferta = client.get(f"/sale/product-offers/{offer_id}")
    opis = {
        "offer_id": offer_id,
        "nazwa": oferta.get("name"),
        "sku": (oferta.get("external") or {}).get("id"),
        "status": (oferta.get("publication") or {}).get("status"),
        "stan": (oferta.get("stock") or {}).get("available"),
        "cena": (oferta.get("sellingMode") or {}).get("price", {}).get("amount"),
    }

    if not potwierdzam:
        return {
            "wykonano": False,
            "powod": "Operacja nieodwracalna, wymaga potwierdzam=True.",
            "oferta_do_zakonczenia": opis,
        }

    import uuid

    command_id = str(uuid.uuid4())
    wynik = czekaj_na_kolejke(
        lambda: client.put(
            f"/sale/offer-publication-commands/{command_id}",
            json={
                "publication": {"action": "END"},
                "offerCriteria": [
                    {"offers": [{"id": offer_id}], "type": "CONTAINS_OFFERS"}
                ],
            },
        )
    )
    return {"wykonano": True, "zakonczona": opis, "polecenie": wynik}


@mcp.tool()
def activate_offer(offer_id: str) -> dict:
    """Dopycha publikację oferty wiszącej w kolejce Allegro.

    Allegro kolejkuje zmiany statusu i odrzuca kolejne polecenie błędem
    InProgressTaskLimitReachedException, dopóki poprzednie się nie przemieli.
    To znaczy „czekaj i ponów", nie „popsute". Narzędzie ponawia za Ciebie.
    """
    import uuid

    command_id = str(uuid.uuid4())
    return czekaj_na_kolejke(
        lambda: client.put(
            f"/sale/offer-publication-commands/{command_id}",
            json={
                "publication": {"action": "ACTIVATE"},
                "offerCriteria": [
                    {"offers": [{"id": offer_id}], "type": "CONTAINS_OFFERS"}
                ],
            },
        ),
        prob=5,
        odstep=30.0,
    )


@mcp.tool()
def search_categories(phrase: str) -> dict:
    """Wyszukuje kategorie Allegro pasujące do nazwy produktu.

    Używa /sale/matching-categories. Wcześniejsza wersja pytała
    /sale/categories?phrase=, co po cichu ignorowało frazę i zwracało
    kategorie główne (Dom i Ogród, Dziecko, Elektronika).
    """
    return client.get("/sale/matching-categories", params={"name": phrase})


# ---------------------------------------------------------------------------
# Cenniki dostaw (allegro:api:sale:settings:read/write)
# ---------------------------------------------------------------------------

def _mapa_metod_dostawy() -> dict[str, str]:
    """Identyfikator metody dostawy -> jej nazwa."""
    dane = client.get("/sale/delivery-methods")
    return {m["id"]: m.get("name", "?") for m in dane.get("deliveryMethods", [])}


@mcp.tool()
def list_shipping_rates(nazwa_zawiera: str = "") -> dict:
    """Lista cenników dostawy na koncie (nazwa + ID + liczba metod).

    Cennik decyduje o tym, jakie metody dostawy zobaczy kupujący, więc to on
    odpowiada za dopasowanie sposobu wysyłki do gabarytu towaru.

    nazwa_zawiera zawęża wynik po fragmencie nazwy (bez rozróżniania wielkości).
    """
    dane = client.get("/sale/shipping-rates")
    cenniki = dane.get("shippingRates", [])
    if nazwa_zawiera:
        szukane = nazwa_zawiera.lower()
        cenniki = [c for c in cenniki if szukane in (c.get("name") or "").lower()]
    return {
        "liczba": len(cenniki),
        "cenniki": [
            {"id": c.get("id"), "nazwa": c.get("name"), "typ": c.get("type")}
            for c in cenniki
        ],
    }


@mcp.tool()
def get_shipping_rate(shipping_rate_id: str) -> dict:
    """Szczegóły cennika wraz z NAZWAMI metod dostawy.

    Samo API zwraca w cenniku wyłącznie identyfikatory metod, więc narzędzie
    dokłada nazwy. Bez nich nie da się stwierdzić, czy w cenniku dużego
    gabarytu nie siedzi przypadkiem paczkomat.
    """
    cennik = client.get(f"/sale/shipping-rates/{shipping_rate_id}")
    nazwy = _mapa_metod_dostawy()
    return {
        "id": cennik.get("id"),
        "nazwa": cennik.get("name"),
        "typ": cennik.get("type"),
        "dispatchCountry": cennik.get("dispatchCountry"),
        "metody": [
            {
                "delivery_method_id": r["deliveryMethod"]["id"],
                "nazwa": nazwy.get(r["deliveryMethod"]["id"], "(nieznana)"),
                "max_sztuk_w_paczce": r.get("maxQuantityPerPackage"),
                "pierwsza_sztuka": (r.get("firstItemRate") or {}).get("amount"),
                "kolejna_sztuka": (r.get("nextItemRate") or {}).get("amount"),
            }
            for r in cennik.get("rates", [])
        ],
    }


@mcp.tool()
def list_delivery_methods(nazwa_zawiera: str = "") -> dict:
    """Metody dostawy dostępne na koncie (do budowania cenników).

    Konto ma ich kilkaset, więc bez zawężenia zwracamy tylko pierwsze 50.
    """
    dane = client.get("/sale/delivery-methods")
    metody = dane.get("deliveryMethods", [])
    if nazwa_zawiera:
        szukane = nazwa_zawiera.lower()
        metody = [m for m in metody if szukane in (m.get("name") or "").lower()]
    return {
        "liczba_wszystkich": len(metody),
        "metody": [
            {
                "id": m.get("id"),
                "nazwa": m.get("name"),
                "platnosc": m.get("paymentPolicy"),
            }
            for m in metody[:50]
        ],
    }


@mcp.tool()
def update_shipping_rate(
    shipping_rate_id: str,
    metody: list[dict],
    nazwa: str = "",
    zastosuj: bool = False,
) -> dict:
    """Nadpisuje metody dostawy w cenniku (PUT, podmienia całą listę).

    To jest narzędzie do naprawiania dopasowania wysyłki do gabarytu, na
    przykład usunięcia paczkomatu z cennika towaru dłuższego niż skrytka.

    metody to lista pozycji w formacie:
        {"delivery_method_id": "...", "max_sztuk_w_paczce": 10,
         "pierwsza_sztuka": "14.99", "kolejna_sztuka": "0.00"}

    Bez zastosuj=True pokazuje różnicę między stanem obecnym a docelowym
    i niczego nie wysyła. PUT podmienia CAŁĄ listę metod, więc pominięcie
    pozycji oznacza jej usunięcie z cennika.
    """
    obecny = client.get(f"/sale/shipping-rates/{shipping_rate_id}")
    nazwy = _mapa_metod_dostawy()

    docelowe = [
        {
            "deliveryMethod": {"id": m["delivery_method_id"]},
            "maxQuantityPerPackage": m.get("max_sztuk_w_paczce", 1),
            "firstItemRate": {
                "amount": str(m.get("pierwsza_sztuka", "0.00")),
                "currency": "PLN",
            },
            "nextItemRate": {
                "amount": str(m.get("kolejna_sztuka", "0.00")),
                "currency": "PLN",
            },
            "shippingTime": m.get("shippingTime"),
        }
        for m in metody
    ]

    obecne_id = {r["deliveryMethod"]["id"] for r in obecny.get("rates", [])}
    docelowe_id = {r["deliveryMethod"]["id"] for r in docelowe}

    roznica = {
        "cennik": obecny.get("name"),
        "usuwane": [nazwy.get(i, i) for i in sorted(obecne_id - docelowe_id)],
        "dodawane": [nazwy.get(i, i) for i in sorted(docelowe_id - obecne_id)],
        "pozostajace": [nazwy.get(i, i) for i in sorted(obecne_id & docelowe_id)],
    }

    if not zastosuj:
        return {
            "wykonano": False,
            "powod": "Podgląd. Wyślij ponownie z zastosuj=True, żeby zapisać.",
            "zmiany": roznica,
        }

    payload = {
        "name": nazwa or obecny.get("name"),
        # Pola wymagane przez API od 09.04.2026. Przepisujemy z obecnego cennika,
        # a gdy go tam nie ma, przyjmujemy towar fizyczny wysyłany z Polski.
        "type": obecny.get("type") or "PHYSICAL",
        "dispatchCountry": obecny.get("dispatchCountry") or "PL",
        "rates": docelowe,
    }
    wynik = client.put(f"/sale/shipping-rates/{shipping_rate_id}", json=payload)
    return {"wykonano": True, "zmiany": roznica, "cennik": wynik}


@mcp.tool()
def create_shipping_rate(
    nazwa: str,
    metody: list[dict],
    typ: str = "PHYSICAL",
    dispatch_country: str = "PL",
    zastosuj: bool = False,
) -> dict:
    """Tworzy nowy cennik dostawy.

    typ: PHYSICAL (towar fizyczny) albo ELECTRONIC. dispatch_country w formacie
    ISO 3166-1 alfa-2. Oba pola są wymagane przez API od 09.04.2026.

    Ograniczenia API, o które łatwo się potknąć: nextItemRate musi wynosić 0,
    pobranie wymaga wcześniejszej aktywacji płatności z góry, a maksymalna
    liczba sztuk musi być taka sama dla metod o tym samym sposobie doręczenia.
    """
    docelowe = [
        {
            "deliveryMethod": {"id": m["delivery_method_id"]},
            "maxQuantityPerPackage": m.get("max_sztuk_w_paczce", 1),
            "firstItemRate": {
                "amount": str(m.get("pierwsza_sztuka", "0.00")),
                "currency": "PLN",
            },
            "nextItemRate": {
                "amount": str(m.get("kolejna_sztuka", "0.00")),
                "currency": "PLN",
            },
        }
        for m in metody
    ]
    payload = {
        "name": nazwa,
        "type": typ,
        "dispatchCountry": dispatch_country,
        "rates": docelowe,
    }

    if not zastosuj:
        nazwy = _mapa_metod_dostawy()
        return {
            "wykonano": False,
            "powod": "Podgląd. Wyślij ponownie z zastosuj=True, żeby utworzyć.",
            "cennik_do_utworzenia": {
                "nazwa": nazwa,
                "typ": typ,
                "kraj_nadania": dispatch_country,
                "metody": [
                    nazwy.get(r["deliveryMethod"]["id"], r["deliveryMethod"]["id"])
                    for r in docelowe
                ],
            },
        }

    return {"wykonano": True, "cennik": client.post("/sale/shipping-rates", json=payload)}


# ---------------------------------------------------------------------------
# Zamówienia (allegro:api:orders:read)
# ---------------------------------------------------------------------------

@mcp.tool()
def list_orders(status: str = "", limit: int = 20, offset: int = 0) -> dict:
    """Lista zamówień (checkout forms). status: BOUGHT, FILLED_IN,
    READY_FOR_PROCESSING lub CANCELLED (puste = wszystkie)."""
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if status:
        params["status"] = status
    return client.get("/order/checkout-forms", params=params)


@mcp.tool()
def get_order(order_id: str) -> dict:
    """Pobiera szczegóły zamówienia po ID (checkout form)."""
    return client.get(f"/order/checkout-forms/{order_id}")


# ---------------------------------------------------------------------------
# Oceny (allegro:api:ratings)
# ---------------------------------------------------------------------------

@mcp.tool()
def list_ratings(limit: int = 20, offset: int = 0) -> dict:
    """Lista ocen wystawionych sprzedawcy."""
    return client.get("/sale/user-ratings", params={"limit": limit, "offset": offset})


# ---------------------------------------------------------------------------
# Spory (allegro:api:disputes)
# ---------------------------------------------------------------------------

@mcp.tool()
def list_disputes(limit: int = 20, offset: int = 0, status: str = "") -> dict:
    """Lista sporów i reklamacji (Dyskusje / post purchase issues).
    status: ONGOING, PENDING lub FINISHED (puste = wszystkie)."""
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if status:
        params["status"] = status
    return client.get("/sale/issues", params=params, accept=BETA_CONTENT_TYPE)


@mcp.tool()
def get_dispute(dispute_id: str) -> dict:
    """Pobiera szczegóły sporu lub reklamacji po ID (issue ID)."""
    return client.get(f"/sale/issues/{dispute_id}", accept=BETA_CONTENT_TYPE)


# ---------------------------------------------------------------------------
# Finanse (allegro:api:billing:read, allegro:api:payments:read)
# ---------------------------------------------------------------------------

@mcp.tool()
def get_billing_balance(limit: int = 50, offset: int = 0) -> dict:
    """Historia rozliczeń Allegro (opłaty, prowizje, zwroty)."""
    return client.get(
        "/billing/billing-entries", params={"limit": limit, "offset": offset}
    )


@mcp.tool()
def list_payments(limit: int = 20, offset: int = 0) -> dict:
    """Historia operacji płatniczych (wpłaty, wypłaty, zwroty)."""
    return client.get(
        "/payments/payment-operations", params={"limit": limit, "offset": offset}
    )


# ---------------------------------------------------------------------------
# Profil (allegro:api:profile:read)
# ---------------------------------------------------------------------------

@mcp.tool()
def get_profile() -> dict:
    """Dane zalogowanego użytkownika (konto sprzedawcy)."""
    return client.get("/me")


# ---------------------------------------------------------------------------
# Przesyłki (allegro:api:shipments:read/write)
# ---------------------------------------------------------------------------

@mcp.tool()
def get_shipment(shipment_id: str) -> dict:
    """Szczegóły przesyłki Wysyłam z Allegro po jej ID.

    Uwaga: API nie ma endpointu listującego przesyłki. ID znajdziesz
    w zamówieniu (get_order) albo w odpowiedzi na utworzenie przesyłki."""
    return client.get(f"/shipment-management/shipments/{shipment_id}")


@mcp.tool()
def get_shipment_label(shipment_id: str, page_size: str = "A6") -> dict:
    """Pobiera etykietę przesyłki i zapisuje ją na dysku. page_size: A4 albo A6.

    Zwraca ścieżkę do pliku, a nie jego treść: etykieta to kilkaset kilobajtów
    PDF-a, którego zawartość w odpowiedzi zapchałaby kontekst i tak nic nikomu
    nie mówiąc.
    """
    content = client.post(
        "/shipment-management/label",
        json={"shipmentIds": [shipment_id], "pageSize": page_size},
        accept="application/octet-stream",
        raw=True,
    )
    KATALOG_ETYKIET.mkdir(exist_ok=True)
    sciezka = KATALOG_ETYKIET / f"etykieta_{shipment_id}_{page_size}.pdf"
    sciezka.write_bytes(content)
    return {"zapisano_do": str(sciezka), "rozmiar_bajtow": len(content)}


# ---------------------------------------------------------------------------
# Promocje (allegro:api:sale:offers:read)
# ---------------------------------------------------------------------------

@mcp.tool()
def list_promotions(promotion_type: str = "") -> dict:
    """Lista promocji i rabatów sprzedawcy (Allegro Loyalty).

    promotion_type: MULTIPACK, CROSS_MULTIPACK, LARGE_ORDER_DISCOUNT
    lub WHOLESALE_PRICE_LIST. Puste = pobiera wszystkie typy.

    Uwaga: kampanie Allegro Ads nie są dostępne w publicznym REST API."""
    typy = (
        [promotion_type]
        if promotion_type
        else [
            "MULTIPACK",
            "CROSS_MULTIPACK",
            "LARGE_ORDER_DISCOUNT",
            "WHOLESALE_PRICE_LIST",
        ]
    )
    wynik: dict[str, Any] = {}
    for t in typy:
        try:
            wynik[t] = client.get(
                "/sale/loyalty/promotions", params={"promotionType": t}
            )
        except AllegroAPIError as e:
            wynik[t] = {"error": str(e)}
    return wynik


# ---------------------------------------------------------------------------
# Ustawienia (allegro:api:sale:settings:read)
# ---------------------------------------------------------------------------

@mcp.tool()
def get_sale_settings() -> dict:
    """Ustawienia sprzedaży konta: darmowa dostawa, cenniki dostawy,
    polityki zwrotów i warunki reklamacji (zebrane z kilku endpointów,
    bo API nie ma jednego /sale/settings)."""
    wynik: dict[str, Any] = {}
    for klucz, sciezka in [
        ("delivery_settings", "/sale/delivery-settings"),
        ("shipping_rates", "/sale/shipping-rates"),
        ("return_policies", "/after-sales-service-conditions/return-policies"),
        ("implied_warranties", "/after-sales-service-conditions/implied-warranties"),
    ]:
        try:
            wynik[klucz] = client.get(sciezka)
        except AllegroAPIError as e:
            wynik[klucz] = {"error": str(e)}
    return wynik


if __name__ == "__main__":
    mcp.run()
