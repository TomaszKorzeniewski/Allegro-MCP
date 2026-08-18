#!/usr/bin/env python3
"""Świeży, kompletny snapshot konta do lokalnego pliku (offers/orders/billing +
rekoncyliacja stanów z arkuszem dostawcy), żeby kolejne raporty czytały ten plik
zamiast odpytywać API Allegro od nowa. Konwencja świeżości: patrz CLAUDE.md.

Czysto odczytowy (same GET), bezpieczny do wielokrotnego odpalania ręcznie,
inaczej niż pozostałe skrypty w tym katalogu.
"""
import json
from collections import defaultdict
from datetime import datetime, timezone

from _sciezki import KORZEN, WYNIKI  # noqa: F401  (ustawia sys.path na korzeń projektu)
from allegro_client import AllegroClient
from update_stany import BUFOR, CONF, TUBY_SETS

BASELINE_DATE = "2026-07-25"
BASELINE_SOURCE = "buy pack/SKU_pojedyncze_do_weryfikacji 2.xlsx"

client = AllegroClient()


def fetch_offers() -> list[dict]:
    out = []
    for status in ("ACTIVE", "INACTIVE"):
        out += client.pobierz_wszystkie(
            "/sale/offers", "offers", params={"publication.status": status}, limit=200
        )
    return out


def fetch_orders() -> list[dict]:
    return client.pobierz_wszystkie("/order/checkout-forms", "checkoutForms", limit=100)


def pack_size(sku: str, external_id: str) -> int | None:
    """Ile fizycznych sztuk 'sku' reprezentuje jedna sztuka oferty 'external_id'.

    Ten sam schemat wariantów co w update_stany.py: pojedyncza sztuka, paczki
    6/12/36, zestawy tub (TUBY_SETS) i koszyki "x 10".
    """
    if external_id == sku:
        return 1
    for n in (6, 12, 36):
        if external_id == f"{sku} - {n} szt.":
            return n
    if sku.startswith("Koszyk") and external_id == f"{sku} x 10":
        return 10
    for n, ext in TUBY_SETS.get(sku, {}).items():
        if external_id == ext:
            return n
    return None


def build_offer_pack_index(offers: list[dict]) -> dict[str, tuple[str, int]]:
    """offer_id -> (sku_bazowe, pack_size) dla ofert należących do arkusza baseline."""
    idx = {}
    for o in offers:
        ext = (o.get("external") or {}).get("id")
        if not ext:
            continue
        for sku in CONF:
            n = pack_size(sku, ext)
            if n is not None:
                idx[o["id"]] = (sku, n)
                break
    return idx


def stock_reconciliation(offers: list[dict], orders: list[dict]) -> list[dict]:
    """Per SKU: ile zostało wg arkusza minus sprzedane od baseline (w sztukach,
    z uwzględnieniem rozmiaru paczki każdej oferty-wariantu), plus to, co
    faktycznie rozdysponowano na Allegro, jako kontrola spójności."""
    idx = build_offer_pack_index(offers)
    offer_by_id = {o["id"]: o for o in offers}

    rozdysponowane = defaultdict(int)
    for offer_id, (sku, n) in idx.items():
        stan = (offer_by_id[offer_id].get("stock") or {}).get("available", 0)
        rozdysponowane[sku] += stan * n

    sold_since = defaultdict(int)
    for f in orders:
        if f.get("status") == "CANCELLED":
            continue
        for li in f.get("lineItems", []):
            if (li.get("boughtAt") or "") < BASELINE_DATE:
                continue
            offer_id = (li.get("offer") or {}).get("id")
            if offer_id in idx:
                sku, n = idx[offer_id]
                sold_since[sku] += li.get("quantity", 0) * n

    return [
        {
            "sku": sku,
            "baseline_qty": baseline_qty,
            "sold_since_baseline_szt": sold_since.get(sku, 0),
            "estimated_current_qty": baseline_qty - sold_since.get(sku, 0),
            "allegro_rozdysponowane_szt": rozdysponowane.get(sku, 0),
            "budzet_85pct": int(baseline_qty * BUFOR),
        }
        for sku, baseline_qty in CONF.items()
    ]


def main() -> None:
    profile = client.get("/me")
    offers = fetch_offers()
    orders = fetch_orders()
    billing = client.get("/billing/billing-entries", params={"limit": 50})

    active_orders = [f for f in orders if f.get("status") != "CANCELLED"]
    gmv = sum(
        float(((f.get("summary") or {}).get("totalToPay") or {}).get("amount", 0) or 0)
        for f in active_orders
    )

    snapshot = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "profile": {
            "login": profile.get("login"),
            "company": (profile.get("company") or {}).get("name"),
        },
        "offers": {
            "active": sum(
                1 for o in offers if (o.get("publication") or {}).get("status") == "ACTIVE"
            ),
            "inactive": sum(
                1 for o in offers if (o.get("publication") or {}).get("status") == "INACTIVE"
            ),
            "total": len(offers),
        },
        "sales": {
            "orders_count": len(active_orders),
            "cancelled_count": len(orders) - len(active_orders),
            "gmv_pln": round(gmv, 2),
        },
        "billing_recent_entries_count": len(billing.get("billingEntries", [])),
        "stock_reconciliation": {
            "baseline_date": BASELINE_DATE,
            "baseline_source": BASELINE_SOURCE,
            "note": "estimated_current_qty = baseline minus sprzedane od baseline (w sztukach). "
            "allegro_rozdysponowane_szt to kontrola spójności z tym, co faktycznie "
            "wystawione na Allegro (powinno być blisko budzet_85pct pomniejszonego "
            "o sold_since_baseline_szt).",
            "per_sku": stock_reconciliation(offers, orders),
        },
    }

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    (WYNIKI / f"snapshot_{ts}.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (WYNIKI / "latest.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Snapshot zapisany: wyniki/snapshot_{ts}.json i wyniki/latest.json")
    print(f"Oferty: {snapshot['offers']}")
    print(f"Sprzedaz: {snapshot['sales']}")


if __name__ == "__main__":
    main()
