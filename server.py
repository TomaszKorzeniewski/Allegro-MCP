"""Serwer MCP dla Allegro REST API (PRODUKCJA).

Uruchomienie:
    python server.py          (transport stdio — do konfiguracji klienta MCP)
"""

import base64
import logging
from typing import Any

from fastmcp import FastMCP

from allegro_client import AllegroClient

logging.basicConfig(level=logging.INFO)

mcp = FastMCP("allegro")
client = AllegroClient()


# ---------------------------------------------------------------------------
# Oferty (allegro:api:sale:offers:read/write)
# ---------------------------------------------------------------------------

@mcp.tool()
def list_offers(status: str = "", limit: int = 20, offset: int = 0) -> dict:
    """Lista ofert sprzedawcy. status: ACTIVE, INACTIVE, ACTIVATING lub ENDED
    (puste = wszystkie)."""
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
    category_id: str,
    description: str,
    image_url: str,
    stock: int,
    price: str,
    status: str = "INACTIVE",
) -> dict:
    """Tworzy nową ofertę produktową.

    price w formacie "123.45" (PLN). status: ACTIVE (publikuj od razu)
    lub INACTIVE (szkic). description to tekst — zostanie opakowany
    w standardową sekcję opisu Allegro.
    """
    payload = {
        "name": name,
        "productSet": [
            {
                "product": {
                    "name": name,
                    "category": {"id": category_id},
                    "images": [image_url] if image_url else [],
                }
            }
        ],
        "description": {
            "sections": [
                {"items": [{"type": "TEXT", "content": f"<p>{description}</p>"}]}
            ]
        },
        "images": [image_url] if image_url else [],
        "sellingMode": {
            "format": "BUY_NOW",
            "price": {"amount": price, "currency": "PLN"},
        },
        "stock": {"available": stock, "unit": "UNIT"},
        "publication": {"status": status},
    }
    return client.post("/sale/product-offers", json=payload)


@mcp.tool()
def update_offer(offer_id: str, fields_to_update: dict) -> dict:
    """Aktualizuje ofertę (PATCH). fields_to_update to fragment struktury oferty,
    np. {"sellingMode": {"price": {"amount": "99.00", "currency": "PLN"}}}
    albo {"stock": {"available": 5}}."""
    return client.patch(f"/sale/product-offers/{offer_id}", json=fields_to_update)


@mcp.tool()
def end_offer(offer_id: str) -> dict:
    """Zakańcza (usuwa) ofertę."""
    return client.delete(f"/sale/offers/{offer_id}")


@mcp.tool()
def search_categories(phrase: str) -> dict:
    """Wyszukuje kategorie Allegro po frazie."""
    return client.get("/sale/categories", params={"phrase": phrase})


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
    return client.get(
        "/sale/user-ratings", params={"limit": limit, "offset": offset}
    )


# ---------------------------------------------------------------------------
# Spory (allegro:api:disputes)
# ---------------------------------------------------------------------------

BETA_CONTENT_TYPE = "application/vnd.allegro.beta.v1+json"


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
    """Pobiera szczegóły sporu/reklamacji po ID (issue ID)."""
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

    Uwaga: API Allegro nie ma endpointu listującego przesyłki — ID przesyłki
    znajdziesz w zamówieniu (get_order) lub w odpowiedzi na utworzenie
    przesyłki."""
    return client.get(f"/shipment-management/shipments/{shipment_id}")


@mcp.tool()
def get_shipment_label(shipment_id: str, page_size: str = "A6") -> dict:
    """Pobiera etykietę przesyłki (PDF/ZPL). page_size: A4 lub A6.
    Zapisuje plik w folderze projektu i zwraca ścieżkę oraz base64."""
    content = client.post(
        "/shipment-management/label",
        json={"shipmentIds": [shipment_id], "pageSize": page_size},
        accept="application/octet-stream",
        raw=True,
    )
    path = f"label_{shipment_id}.pdf"
    with open(path, "wb") as f:
        f.write(content)
    return {
        "saved_to": path,
        "size_bytes": len(content),
        "base64": base64.b64encode(content).decode(),
    }


# ---------------------------------------------------------------------------
# Reklamy (allegro:api:ads, allegro:api:campaigns)
# ---------------------------------------------------------------------------

@mcp.tool()
def list_promotions(promotion_type: str = "") -> dict:
    """Lista promocji i rabatów sprzedawcy (Allegro Loyalty).

    promotion_type: MULTIPACK, CROSS_MULTIPACK, LARGE_ORDER_DISCOUNT
    lub WHOLESALE_PRICE_LIST. Puste = pobiera wszystkie typy.

    Uwaga: kampanie Allegro Ads nie są dostępne w publicznym REST API —
    to narzędzie obejmuje promocje/rabaty konta sprzedawcy."""
    types = (
        [promotion_type]
        if promotion_type
        else ["MULTIPACK", "CROSS_MULTIPACK", "LARGE_ORDER_DISCOUNT",
              "WHOLESALE_PRICE_LIST"]
    )
    result: dict[str, Any] = {}
    for t in types:
        try:
            result[t] = client.get(
                "/sale/loyalty/promotions", params={"promotionType": t}
            )
        except Exception as e:
            result[t] = {"error": str(e)}
    return result


# ---------------------------------------------------------------------------
# Ustawienia (allegro:api:sale:settings:read)
# ---------------------------------------------------------------------------

@mcp.tool()
def get_sale_settings() -> dict:
    """Ustawienia sprzedaży konta: darmowa dostawa, cenniki dostawy,
    polityki zwrotów i warunki reklamacji (zebrane z kilku endpointów,
    bo API nie ma jednego /sale/settings)."""
    result: dict[str, Any] = {}
    for key, path in [
        ("delivery_settings", "/sale/delivery-settings"),
        ("shipping_rates", "/sale/shipping-rates"),
        ("return_policies", "/after-sales-service-conditions/return-policies"),
        ("implied_warranties", "/after-sales-service-conditions/implied-warranties"),
    ]:
        try:
            result[key] = client.get(path)
        except Exception as e:
            result[key] = {"error": str(e)}
    return result


if __name__ == "__main__":
    mcp.run()
