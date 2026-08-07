#!/usr/bin/env python3
"""Odtwarza oferty zakończone przez PRODUCT_DETACHMENT.

Allegro odpięło te oferty od karty produktu w katalogu i przez to je zakończyło
(`publication.endedBy = PRODUCT_DETACHMENT`, `productSet[0].product.id = null`).
Oferty ENDED nie da się wznowić — trzeba wystawić nową.

Metoda: bierzemy CAŁY payload z martwej oferty (nazwa, opis, zdjęcia, parametry,
cena) i podmieniamy tylko to, co jest zepsute — `product.id` na identyfikator
karty z żywej oferty siostrzanej tego samego SKU.

Użycie:
  python recreate_detached.py            # dry-run, pokazuje payload
  python recreate_detached.py --apply    # wystawia
"""
import json
import sys
import time

sys.path.insert(0, "/Users/tomasz/Desktop/allegro-buypack")
from allegro_client import AllegroClient, AllegroAPIError

client = AllegroClient()
DRY_RUN = "--apply" not in sys.argv

WARRANTY_ID = "c6bd41ce-bc1c-41a6-be3c-651dd035dc43"
RETURN_POLICY_ID = "3af930f6-631c-420f-ab59-23582f9288ff"
SINGLE_SHIPPING_ID = "fcf29f15-4038-4046-be17-f047d8f56f89"
ZESTAW_SHIPPING_ID = "98c51ddb-13d6-419f-94cb-57c68bd8f8b7"
LOCATION = {"countryCode": "PL", "province": "SLASKIE", "city": "Cieszyn",
            "postCode": "43-400"}

JOBS = [
    {
        "opis": "TP/0015 pojedyncza",
        "martwa": "18735303774",      # źródło nazwy/opisu/zdjęć/ceny
        "zywa_siostra": "18764921802",  # TP/0015 - 6 szt., dawca product.id
        "quantity": 1,
        "shipping": SINGLE_SHIPPING_ID,
        "stock_startowy": 60,          # prowizorka — update_stany.py przeliczy
    },
    {
        "opis": "TP/0017 - 12 szt.",
        "martwa": "18764922620",
        "zywa_siostra": "18764922433",  # TP/0017 - 6 szt.
        "quantity": 12,
        "shipping": ZESTAW_SHIPPING_ID,
        "stock_startowy": 10,
    },
]


def strip_params(params):
    """Parametry w POST przyjmują tylko id + valuesIds/values."""
    out = []
    for p in params or []:
        e = {"id": p["id"]}
        if p.get("valuesIds"):
            e["valuesIds"] = p["valuesIds"]
        elif p.get("values"):
            e["values"] = p["values"]
        out.append(e)
    return out


def build(job):
    dead = client.get(f"/sale/product-offers/{job['martwa']}")
    sis = client.get(f"/sale/product-offers/{job['zywa_siostra']}")

    prod_id = sis["productSet"][0]["product"]["id"]
    if not prod_id:
        raise RuntimeError(
            f"Oferta siostrzana {job['zywa_siostra']} też jest odpięta od karty "
            f"— nie ma skąd wziąć product.id")

    ps_dead = dead["productSet"][0]
    ps_entry = {
        "product": {"id": prod_id},
        "quantity": {"value": job["quantity"]},
        "marketedBeforeGPSRObligation": ps_dead.get(
            "marketedBeforeGPSRObligation", False),
    }
    if ps_dead.get("responsibleProducer"):
        ps_entry["responsibleProducer"] = {"id": ps_dead["responsibleProducer"]["id"]}
    if ps_dead.get("safetyInformation"):
        ps_entry["safetyInformation"] = {
            "description": ps_dead["safetyInformation"]["description"],
            "type": ps_dead["safetyInformation"].get("type", "TEXT"),
        }

    payload = {
        "name": dead["name"],
        "category": {"id": dead["category"]["id"]},
        "external": dict(dead["external"]),
        "productSet": [ps_entry],
        "images": (dead.get("images") or [])[:8],
        "description": dead["description"],
        "parameters": strip_params(dead.get("parameters")),
        "sellingMode": {"format": "BUY_NOW",
                        "price": dead["sellingMode"]["price"]},
        "stock": {"available": job["stock_startowy"], "unit": "UNIT"},
        "publication": {"status": "ACTIVE"},
        "afterSalesServices": {
            "impliedWarranty": {"id": WARRANTY_ID},
            "returnPolicy": {"id": RETURN_POLICY_ID},
        },
        "delivery": {"shippingRates": {"id": job["shipping"]},
                     "handlingTime": "PT24H"},
        "location": LOCATION,
        "payments": {"invoice": "VAT"},
    }
    if dead.get("taxSettings"):
        payload["taxSettings"] = dead["taxSettings"]

    prod_params = strip_params(ps_dead["product"].get("parameters"))
    return payload, prod_params


def main():
    results = []
    for job in JOBS:
        payload, prod_params = build(job)
        print(f"\n=== {job['opis']}")
        print(f"  nazwa:   {payload['name']}")
        print(f"  external:{payload['external']}  qty={job['quantity']}")
        print(f"  produkt: {payload['productSet'][0]['product']['id']}")
        print(f"  cena:    {payload['sellingMode']['price']}")
        print(f"  zdjęcia: {len(payload['images'])}  "
              f"sekcje opisu: {len(payload['description']['sections'])}")

        if DRY_RUN:
            continue

        try:
            try:
                resp = client.post("/sale/product-offers", json=payload)
            except AllegroAPIError as e:
                if "parametr" in str(e).lower() and prod_params:
                    payload["productSet"][0]["product"]["parameters"] = prod_params
                    resp = client.post("/sale/product-offers", json=payload)
                else:
                    raise
            oid = resp.get("id", "?")
            print(f"  [OK] nowa oferta: {oid}")
            results.append({**{k: job[k] for k in ("opis", "martwa")},
                            "nowa": oid, "status": "ACTIVE"})
        except AllegroAPIError as e:
            print(f"  [ERR] {str(e)[:400]}")
            results.append({**{k: job[k] for k in ("opis", "martwa")},
                            "nowa": None, "error": str(e)[:400]})
        time.sleep(1.5)

    if DRY_RUN:
        print("\nDRY-RUN — nic nie wystawiono. Uruchom z --apply.")
        return

    with open("/Users/tomasz/Desktop/allegro-buypack/recreate_detached_results.json",
              "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nGotowe: {sum(1 for r in results if r.get('nowa'))}/{len(results)} OK")


if __name__ == "__main__":
    main()
