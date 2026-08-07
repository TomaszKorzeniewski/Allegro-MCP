"""Budowanie i tworzenie ofert: wiedza wyciągnięta z jednorazowych skryptów.

Skrypty w `skrypty/` wypracowały przez kilka sesji na produkcji to, czego API
faktycznie wymaga i jak reaguje na błędy. Ta wiedza siedziała rozsypana
w kilku kopiach; tutaj jest raz.

Trzy mechanizmy, które są tu najcenniejsze:

1. **Zestawy** nie powstają od zera. Kategoria 64541 wymaga pełnego opisu
   produktu i odbija budowany ręcznie `productSet` błędem 422. Bierzemy więc
   `productSet` z żywej oferty pojedynczej (Allegro już go zaakceptowało)
   i zmieniamy tylko `quantity.value`.
2. **Odtwarzanie po PRODUCT_DETACHMENT.** Gdy Allegro scali lub usunie kartę
   produktu, odpina od niej ofertę i ją kończy. Takiej oferty nie da się
   wznowić. Kopiujemy cały payload martwej oferty i podmieniamy `product.id`
   na kartę z żywej oferty siostrzanej.
3. **Zatrzymanie przy konflikcie katalogu.** Gdy 422 dotyczy EAN lub karty
   produktu, NIE próbujemy kolejnych wariantów danych. Taka iteracja nic nie
   daje, a zaśmieca konto. Zgłaszamy błąd z opisem decyzji do podjęcia.
"""

import logging
from typing import Any, Sequence

import requests

import config
from allegro_client import AllegroAPIError, AllegroClient

logger = logging.getLogger(__name__)


class KonfliktKatalogu(Exception):
    """EAN albo karta produktu kolidują z katalogiem Allegro.

    Świadomie nie ponawiamy takiej operacji z innymi danymi. Decyzja należy
    do Tomka i sprowadza się do jednej z czterech opcji opisanych w wiadomości.
    """


def strip_params(parametry: Sequence[dict] | None) -> list[dict]:
    """Sprowadza parametry do postaci przyjmowanej przy zapisie.

    Odpowiedź GET niesie nazwy i metadane, których POST nie przyjmuje:
    zostają tylko `id` oraz `valuesIds` albo `values`.
    """
    wynik = []
    for p in parametry or []:
        okrojony: dict[str, Any] = {"id": p["id"]}
        if p.get("valuesIds"):
            okrojony["valuesIds"] = p["valuesIds"]
        elif p.get("values"):
            okrojony["values"] = p["values"]
        else:
            continue
        wynik.append(okrojony)
    return wynik


def pobierz_zdjecia_dostawcy(slug: str) -> list[str]:
    """Zdjęcia produktu ze sklepu dostawcy (Shopify JSON).

    Zwraca pustą listę zamiast rzucać wyjątkiem, bo brak zdjęć ma zatrzymać
    tworzenie oferty w miejscu wywołania, a nie wysadzić cały przebieg.
    """
    try:
        r = requests.get(
            config.DALPO_PRODUCT_URL.format(slug=slug),
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
        r.raise_for_status()
        return [img["src"] for img in r.json()["product"]["images"] if img.get("src")]
    except Exception as e:
        logger.warning("Nie udało się pobrać zdjęć dla '%s': %s", slug, e)
        return []


def skroc_nazwe(nazwa: str, przyrostek: str = "", limit: int | None = None) -> str:
    """Dopasowuje nazwę oferty do limitu Allegro, ucinając na granicy słowa.

    Przyrostek (na przykład „6 szt.") jest nienaruszalny: to on niesie
    informację odróżniającą zestaw od sztuki pojedynczej.
    """
    limit = limit or config.MAX_DLUGOSC_NAZWY
    przyrostek = przyrostek.strip()
    if not przyrostek:
        return nazwa[:limit].strip()

    miejsce = limit - len(przyrostek) - 1
    if miejsce <= 0:
        return przyrostek[:limit]
    if len(nazwa) <= miejsce:
        return f"{nazwa} {przyrostek}"

    skrocona = nazwa[:miejsce]
    if " " in skrocona:
        skrocona = skrocona.rsplit(" ", 1)[0]
    return f"{skrocona.strip()} {przyrostek}"


def _blok_gpsr(
    responsible_producer_id: str | None = None,
    safety_text: str | None = None,
) -> dict:
    """Pola GPSR wymagane wewnątrz elementu `productSet`.

    Uwaga: na najwyższym poziomie payloadu zwracają 422 UnknownJSONProperty.
    """
    return {
        "responsibleProducer": {
            "id": responsible_producer_id or config.RESPONSIBLE_PRODUCER_ID
        },
        "safetyInformation": {
            "description": safety_text or config.SAFETY_TEXT,
            "type": "TEXT",
        },
        "marketedBeforeGPSRObligation": False,
    }


def zbuduj_payload_oferty(
    *,
    tytul: str,
    sku: str,
    cena: str,
    opis: dict,
    zdjecia: Sequence[str],
    parametry_produktu: Sequence[dict],
    stan: int = 0,
    status: str = "INACTIVE",
    category_id: str | None = None,
    shipping_rates_id: str | None = None,
) -> dict:
    """Składa pełny payload oferty produktowej.

    Wzorzec pochodzi z `skrypty/publish_singles.py`, czyli z wersji, która
    faktycznie przeszła na produkcji. Wcześniejszy `create_offer` w serwerze
    pomijał `location`, `delivery`, `afterSalesServices` i `payments`,
    przez co odbijał się od API.

    Domyślny `stan=0` jest celowy: oferta powstaje bez dostępnych sztuk, żeby
    nie sprzedać czegoś, zanim potwierdzisz jej poprawność. Stan ustawiasz
    osobnym PATCH-em po weryfikacji.
    """
    return {
        "name": tytul,
        "category": {"id": category_id or config.CATEGORY_ID},
        "external": {"id": sku},
        "productSet": [
            {
                "product": {
                    "name": tytul,
                    "category": {"id": category_id or config.CATEGORY_ID},
                    "images": list(zdjecia[:4]),  # zwykłe stringi, nie obiekty
                    "parameters": list(parametry_produktu),
                },
                "quantity": {"value": 1},  # bez "unit", inaczej 422
                **_blok_gpsr(),
            }
        ],
        "images": list(zdjecia[:8]),
        "description": opis,
        "parameters": [
            {"id": config.PARAM_STAN, "values": ["Nowy"], "valuesIds": ["11323_1"]}
        ],
        "sellingMode": {
            "format": "BUY_NOW",
            "price": {"amount": cena, "currency": "PLN"},
        },
        "stock": {"available": stan, "unit": "UNIT"},
        "publication": {"status": status},
        "afterSalesServices": {
            "impliedWarranty": {"id": config.WARRANTY_ID},
            "returnPolicy": {"id": config.RETURN_POLICY_ID},
        },
        "delivery": {
            "shippingRates": {"id": shipping_rates_id or config.SHIPPING_RATES_ID},
            "handlingTime": config.HANDLING_TIME,
        },
        "location": config.LOCATION,
        "payments": {"invoice": "VAT"},
    }


def utworz_oferte(
    client: AllegroClient,
    payload: dict,
    *,
    parametry_zapasowe: Sequence[dict] | None = None,
    pozwol_na_szkic: bool = True,
) -> dict:
    """Wysyła ofertę, obsługując dwa znane sposoby, w jakie API potrafi odmówić.

    1. „Uzupełnij parametry obowiązkowe": ponawiamy raz, dokładając parametry
       produktu (wzorzec z `create_zestawy.py` i `recreate_detached.py`).
    2. Odmowa publikacji ACTIVE: zapisujemy jako INACTIVE, czyli szkic do
       ręcznego opublikowania, zamiast tracić całą pracę.

    Konflikt katalogu (EAN lub karta produktu) przerywa działanie wyjątkiem
    `KonfliktKatalogu`. To celowe: iterowanie kolejnymi wariantami danych
    nie pomaga, a zostawia śmieci na koncie.

    Uwaga: POST zwraca 202, i to jest sukces. Operacja jest asynchroniczna,
    a identyfikator oferty siedzi w treści odpowiedzi.
    """

    def wyslij(pl: dict) -> dict:
        return client.post("/sale/product-offers", json=pl)

    try:
        return wyslij(payload)
    except AllegroAPIError as e:
        if e.to_konflikt_katalogu:
            raise KonfliktKatalogu(
                f"Konflikt z katalogiem Allegro ({e.status_code}): {e.message}\n"
                "Zatrzymuję się zgodnie z ustaloną zasadą. Do wyboru: "
                "(A) podpiąć istniejącą kartę katalogową, "
                "(B) zgłosić korektę katalogu do Allegro, "
                "(C) wystąpić o nowe EAN w GS1, "
                "(D) potwierdzić EAN u dostawcy."
            ) from e

        # Brakujące parametry obowiązkowe: jedna dokładka i koniec.
        if "parametr" in str(e).lower() and parametry_zapasowe:
            logger.info("API prosi o parametry produktu, ponawiam z kompletem.")
            payload = dict(payload)
            payload["productSet"][0]["product"]["parameters"] = list(
                parametry_zapasowe
            )
            try:
                return wyslij(payload)
            except AllegroAPIError as e2:
                e = e2

        # Publikacja odrzucona: zejdź do szkicu, żeby nie stracić roboty.
        if pozwol_na_szkic and payload.get("publication", {}).get("status") == "ACTIVE":
            logger.warning("Publikacja ACTIVE odrzucona (%s), zapisuję jako szkic.", e)
            payload = dict(payload)
            payload["publication"] = {"status": "INACTIVE"}
            wynik = wyslij(payload)
            wynik["_uwaga"] = f"Zapisano jako szkic INACTIVE, bo ACTIVE odrzucone: {e}"
            return wynik

        raise


def zbuduj_payload_zestawu(
    client: AllegroClient,
    offer_id_pojedynczej: str,
    sztuk: int,
    *,
    cena: str,
    sku: str | None = None,
    shipping_rates_id: str | None = None,
) -> dict:
    """Buduje zestaw N sztuk na bazie żywej oferty pojedynczej.

    Klucz do obejścia 422: `productSet[0].product` to sama referencja
    `{"id": ...}` do karty katalogowej, którą Allegro już zaakceptowało,
    a nie zbudowany od nowa opis produktu.
    """
    pojedyncza = client.get(f"/sale/product-offers/{offer_id_pojedynczej}")
    ps = pojedyncza["productSet"][0]
    product_id = ps["product"].get("id")
    if not product_id:
        raise ValueError(
            f"Oferta {offer_id_pojedynczej} nie ma karty produktu "
            "(prawdopodobnie została odpięta) — nie ma z czego zbudować zestawu."
        )

    stan_pojedynczej = (pojedyncza.get("stock") or {}).get("available", 0) or 0

    element = {
        "product": {"id": product_id},
        "quantity": {"value": sztuk},
        "marketedBeforeGPSRObligation": ps.get("marketedBeforeGPSRObligation", False),
    }
    if ps.get("responsibleProducer"):
        element["responsibleProducer"] = {"id": ps["responsibleProducer"]["id"]}
    if ps.get("safetyInformation"):
        element["safetyInformation"] = {
            "description": ps["safetyInformation"]["description"],
            "type": ps["safetyInformation"].get("type", "TEXT"),
        }

    payload = {
        "name": skroc_nazwe(pojedyncza["name"], f"{sztuk} szt."),
        "category": {"id": config.CATEGORY_ID},
        "external": {"id": sku or f"{pojedyncza.get('external', {}).get('id', '')} - {sztuk} szt."},
        "productSet": [element],
        "images": pojedyncza.get("images", [])[:8],
        "description": pojedyncza["description"],
        "parameters": strip_params(pojedyncza.get("parameters")),
        "sellingMode": {
            "format": "BUY_NOW",
            "price": {"amount": cena, "currency": "PLN"},
        },
        "stock": {"available": max(1, stan_pojedynczej // sztuk), "unit": "UNIT"},
        "publication": {"status": "ACTIVE"},
        "afterSalesServices": {
            "impliedWarranty": {"id": config.WARRANTY_ID},
            "returnPolicy": {"id": config.RETURN_POLICY_ID},
        },
        "delivery": {
            "shippingRates": {
                "id": shipping_rates_id or config.ZESTAW_SHIPPING_ID
            },
            "handlingTime": config.HANDLING_TIME,
        },
        "location": config.LOCATION,
        "payments": {"invoice": "VAT"},
    }
    if pojedyncza.get("taxSettings"):
        payload["taxSettings"] = pojedyncza["taxSettings"]
    return payload


def zbuduj_payload_odtworzenia(
    client: AllegroClient, offer_id_martwej: str, offer_id_siostry: str
) -> dict:
    """Odtwarza ofertę zakończoną przez PRODUCT_DETACHMENT.

    Bierze cały payload martwej oferty i podmienia wyłącznie to, co jest
    zepsute: `product.id` na kartę z żywej oferty siostrzanej tego samego SKU.
    """
    martwa = client.get(f"/sale/product-offers/{offer_id_martwej}")
    siostra = client.get(f"/sale/product-offers/{offer_id_siostry}")

    product_id = (siostra["productSet"][0].get("product") or {}).get("id")
    if not product_id:
        raise ValueError(
            f"Oferta siostrzana {offer_id_siostry} też jest odpięta od karty, "
            "nie ma skąd wziąć product.id."
        )

    ps_martwej = martwa["productSet"][0]
    element = {
        "product": {"id": product_id},
        "quantity": ps_martwej.get("quantity", {"value": 1}),
        "marketedBeforeGPSRObligation": ps_martwej.get(
            "marketedBeforeGPSRObligation", False
        ),
    }
    if ps_martwej.get("responsibleProducer"):
        element["responsibleProducer"] = {
            "id": ps_martwej["responsibleProducer"]["id"]
        }
    if ps_martwej.get("safetyInformation"):
        element["safetyInformation"] = {
            "description": ps_martwej["safetyInformation"]["description"],
            "type": ps_martwej["safetyInformation"].get("type", "TEXT"),
        }

    payload = {
        "name": martwa["name"],
        "category": martwa["category"],
        "external": martwa.get("external", {}),
        "productSet": [element],
        "images": martwa.get("images", [])[:8],
        "description": martwa["description"],
        "parameters": strip_params(martwa.get("parameters")),
        "sellingMode": martwa["sellingMode"],
        "stock": {
            "available": (martwa.get("stock") or {}).get("available", 0),
            "unit": "UNIT",
        },
        "publication": {"status": "ACTIVE"},
        "afterSalesServices": martwa.get("afterSalesServices", {}),
        "delivery": martwa.get("delivery", {}),
        "location": martwa.get("location", config.LOCATION),
        "payments": martwa.get("payments", {"invoice": "VAT"}),
    }
    if martwa.get("taxSettings"):
        payload["taxSettings"] = martwa["taxSettings"]
    return payload
