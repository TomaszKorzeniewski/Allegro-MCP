# allegro-buypack — serwer MCP dla Allegro REST API

Serwer MCP (Python, `fastmcp`) dający Claude'owi dostęp do konta sprzedawcy
Allegro: oferty, zamówienia, oceny, spory, finanse, przesyłki, reklamy
i ustawienia sprzedaży.

**Środowisko: PRODUKCJA** — `https://api.allegro.pl` i `https://allegro.pl/auth`.

## Instalacja

Wymagany Python 3.10+ (systemowy 3.9 jest za stary dla `fastmcp`).
Projekt używa venv z Pythonem 3.12 (Homebrew):

```bash
cd ~/Desktop/allegro-buypack
/usr/local/bin/python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Autoryzacja (OAuth 2.0 device flow)

Wymaga `ALLEGRO_CLIENT_ID` i `ALLEGRO_CLIENT_SECRET` w `.env`
(aplikacja typu "device" zarejestrowana na https://apps.developer.allegro.pl/).

```bash
.venv/bin/python auth.py
```

Skrypt otworzy przeglądarkę z linkiem autoryzacyjnym i wyświetli kod.
Po zatwierdzeniu na Allegro tokeny (`ALLEGRO_ACCESS_TOKEN`,
`ALLEGRO_REFRESH_TOKEN`) zapisują się w `.env`. Access token jest ważny
12 godzin — klient odświeża go automatycznie przy 401.

## Uruchomienie serwera MCP

```bash
.venv/bin/python server.py
```

Konfiguracja w kliencie MCP (np. Claude Code / Claude Desktop):

```json
{
  "mcpServers": {
    "allegro": {
      "command": "/Users/tomasz/Desktop/allegro-buypack/.venv/bin/python",
      "args": ["/Users/tomasz/Desktop/allegro-buypack/server.py"]
    }
  }
}
```

Lub w Claude Code:

```bash
claude mcp add allegro -- ~/Desktop/allegro-buypack/.venv/bin/python ~/Desktop/allegro-buypack/server.py
```

## Dostępne narzędzia (tools)

| Obszar | Tool | Endpoint |
|---|---|---|
| Oferty | `list_offers(status, limit, offset)` | GET /sale/offers |
| | `get_offer(offer_id)` | GET /sale/product-offers/{id} |
| | `create_offer(name, category_id, description, image_url, stock, price, status)` | POST /sale/product-offers |
| | `update_offer(offer_id, fields_to_update)` | PATCH /sale/product-offers/{id} |
| | `end_offer(offer_id)` | DELETE /sale/offers/{id} |
| | `search_categories(phrase)` | GET /sale/categories |
| Zamówienia | `list_orders(status, limit, offset)` | GET /order/checkout-forms |
| | `get_order(order_id)` | GET /order/checkout-forms/{id} |
| Oceny | `list_ratings(limit, offset)` | GET /sale/user-ratings |
| Spory | `list_disputes(limit, offset, status)` | GET /sale/issues |
| | `get_dispute(dispute_id)` | GET /sale/issues/{issueId} |
| Finanse | `get_billing_balance()` | GET /billing/billing-entries |
| | `list_payments(limit, offset)` | GET /payments/payment-operations |
| Profil | `get_profile()` | GET /me |
| Przesyłki | `get_shipment(shipment_id)` | GET /shipment-management/shipments/{id} |
| | `get_shipment_label(shipment_id, page_size)` | POST /shipment-management/label |
| Promocje | `list_promotions(promotion_type)` | GET /sale/loyalty/promotions |
| Ustawienia | `get_sale_settings()` | GET /sale/delivery-settings + shipping-rates + return-policies + implied-warranties |

Uwagi względem pierwotnej specyfikacji (aktualne API Allegro):

- Spory: `/sale/disputes` już nie istnieje — zastąpione przez `/sale/issues`
  (Post Purchase Issues, nagłówek `Accept: application/vnd.allegro.beta.v1+json`).
- Przesyłki: API nie ma endpointu listującego przesyłki — jest tylko pobranie
  pojedynczej po ID (ID znajdziesz w zamówieniu). Etykiety pobiera się przez
  `POST /shipment-management/label`.
- Kampanie Allegro Ads nie są dostępne w publicznym REST API — zamiast tego
  `list_promotions` zwraca promocje/rabaty konta (Multipack, rabaty od
  wartości zamówienia, cenniki hurtowe).
- `/sale/settings` nie istnieje — `get_sale_settings` agreguje cztery
  faktyczne endpointy ustawień.

## Struktura projektu

```
allegro-buypack/
├── .env              # klucze aplikacji i tokeny (nie commituj!)
├── .gitignore
├── requirements.txt
├── auth.py           # OAuth device flow + refresh tokenów
├── allegro_client.py # klient HTTP (Bearer auth, retry przy 401)
├── server.py         # serwer MCP z narzędziami
└── README.md
```
