# allegro-buypack — serwer MCP dla Allegro REST API

Serwer MCP (Python, `fastmcp`) dający Claude'owi dostęp do konta sprzedawcy
Allegro: oferty, zestawy, cenniki dostawy, zamówienia, oceny, spory, finanse,
przesyłki i ustawienia sprzedaży.

**Środowisko: PRODUKCJA**, `https://api.allegro.pl`. Narzędzia zapisujące
działają na żywym koncie, dlatego operacje nieodwracalne i masowe wymagają
jawnego potwierdzenia (patrz „Hamulce" niżej).

## Instalacja

Wymagany Python 3.10 lub nowszy. Sprawdzone na 3.14 (Homebrew).

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Autoryzacja (OAuth 2.0 device flow)

Wymaga `ALLEGRO_CLIENT_ID` i `ALLEGRO_CLIENT_SECRET` w `.env`
(aplikacja typu „device" zarejestrowana na https://apps.developer.allegro.pl/).

```bash
.venv/bin/python auth.py
```

Skrypt otworzy przeglądarkę i wyświetli kod. Po zatwierdzeniu tokeny zapisują
się w `.env` wraz z momentem wygaśnięcia. Access token żyje 12 godzin
i odświeża się sam, z pięciominutowym wyprzedzeniem.

⚠️ **Refresh token Allegro jest jednorazowy.** Odświeżenie go z dwóch procesów
naraz unieważnia autoryzację konta. Dlatego rotacja idzie pod blokadą pliku
(`.env.lock`). Jeśli piszesz własny kod czytający `.env`, korzystaj z `auth.py`,
zamiast wołać endpoint tokenów samodzielnie.

## Uruchomienie

```bash
.venv/bin/python server.py
```

Rejestracja w Claude Code (podmień ścieżkę na swoją):

```bash
claude mcp add allegro --scope user -- /ścieżka/do/.venv/bin/python /ścieżka/do/server.py
```

Bez CLI `claude` (na przykład w aplikacji desktopowej) wpis idzie do
`~/.claude.json`, do klucza `mcpServers`. Zmiany widać po restarcie aplikacji.

## Narzędzia

### Oferty
| Narzędzie | Uwagi |
|---|---|
| `list_offers(status, limit, offset)` | Świeża oferta potrafi wisieć jako INACTIVE, licz oba statusy |
| `get_offer(offer_id)` | |
| `create_offer(name, sku, description_html, image_urls, price, stock, status)` | Domyślnie szkic z zerowym stanem |
| `create_offer_set(offer_id_pojedynczej, sztuk, price, sku)` | Zestawy, kopiuje kartę produktu (inaczej 422) |
| `recreate_detached_offer(offer_id_martwej, offer_id_siostry)` | Po PRODUCT_DETACHMENT |
| `update_offer(offer_id, fields_to_update)` | PATCH fragmentem struktury |
| `end_offer(offer_id, potwierdzam)` | **Nieodwracalne**, wymaga `potwierdzam=True` |
| `activate_offer(offer_id)` | Dopycha publikację wiszącą w kolejce |
| `search_categories(phrase)` | `/sale/matching-categories` |

### Cenniki dostawy
| Narzędzie | Uwagi |
|---|---|
| `list_shipping_rates(nazwa_zawiera)` | |
| `get_shipping_rate(shipping_rate_id)` | Dokłada **nazwy** metod, API zwraca same UUID-y |
| `list_delivery_methods(nazwa_zawiera)` | Konto ma ich kilkaset |
| `update_shipping_rate(..., zastosuj)` | PUT podmienia **całą** listę metod |
| `create_shipping_rate(..., zastosuj)` | Wymaga `type` i `dispatchCountry` (API od 09.04.2026) |

### Reszta
`list_orders`, `get_order`, `list_ratings`, `list_disputes`, `get_dispute`,
`get_billing_balance`, `list_payments`, `get_profile`, `get_shipment`,
`get_shipment_label`, `list_promotions`, `get_sale_settings`.

## Hamulce

| Rodzaj operacji | Zachowanie |
|---|---|
| Nieodwracalna (`end_offer`) | Bez `potwierdzam=True` zwraca podgląd oferty, nic nie kończy |
| Masowa (cenniki) | Bez `zastosuj=True` zwraca różnicę „usuwane / dodawane / pozostające" |
| Odwracalna (cena, stan) | Wykonuje się od razu |

## Ograniczenia API Allegro

- `/sale/disputes` nie istnieje, zastąpione przez `/sale/issues`
  (nagłówek `Accept: application/vnd.allegro.beta.v1+json`).
- Nie ma endpointu listującego przesyłki, tylko pobranie pojedynczej po ID.
- Kampanie Allegro Ads nie są dostępne w publicznym REST API.
- `/sale/settings` nie istnieje, `get_sale_settings` agreguje cztery endpointy.
- Pole „Marża netto" z Seller Center nie jest dostępne przez API.

## Testy

```bash
.venv/bin/python -m pytest
```

Testy nie dotykają produkcji: cała warstwa HTTP jest podstawiana atrapą.
Sprawdzają między innymi, że przy braku potwierdzenia nie idzie żadne
zapytanie zapisujące, oraz że blokada tokenu faktycznie wyklucza drugi proces.

## Struktura

```
allegro-buypack/
├── .env                # klucze i tokeny (w .gitignore)
├── server.py           # narzędzia MCP
├── allegro_client.py   # HTTP: ponawianie, paginacja, błędy
├── auth.py             # OAuth device flow, rotacja pod blokadą
├── config.py           # identyfikatory konta, GPSR, lokalizacja
├── offers.py           # payload, zestawy, odtwarzanie odpiętych ofert
├── descriptions.py     # generator opisu
├── plugin/             # paczka dla Cowork
├── skrypty/            # przebiegi jednorazowe (uwaga: działają przy imporcie)
├── wyniki/             # wyniki przebiegów, ślad audytowy
└── tests/
```

⚠️ Skrypty w `skrypty/` wykonują operacje na produkcji już przy imporcie.
Nie uruchamiaj ich, żeby sprawdzić, czy działają. Od tego jest `pytest`.
