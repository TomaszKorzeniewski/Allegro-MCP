#!/usr/bin/env python3
"""Poprawia nazwy (tytuły) zestawów: pełna nazwa produktu + ' N szt.' na końcu,
bez prefiksu 'Zestaw Nx', bez ucinania w połowie słowa, <=75 znaków.
Nazwę bazową bierze z żywej oferty pojedynczej (wierne SEO)."""
import sys, json, time
sys.path.insert(0, "/Users/tomasz/Desktop/allegro-buypack")
from allegro_client import AllegroClient, AllegroAPIError

client = AllegroClient()

SINGLE = {
    "TP/0001": "18748619896", "TP/0002": "18734683435", "TP/0003": "18732815640",
    "TP/0004": "18734683525", "TP/0005": "18732829075", "TP/0006": "18735303719",
    "TP/0007": "18734683580", "TP/0008": "18732829273", "TP/0009": "18729289736",
    "TP/0010": "18734683657", "TP/0012": "18732829345", "TP/0013": "18734683710",
    "TP/0014": "18732816516", "TP/0015": "18735303774", "TP/0016": "18735303831",
    "TP/0017": "18735303892", "TP/0018": "18735303947", "TP/0019": "18734683779",
    "TP/0024": "18732829425", "TP/0030": "18735304061",
}
FILLER = {"do", "i", "na", "z", "w", "klejąca", "pakowanie", "pakowania"}


def clean_name(base, n):
    suffix = f" {n} szt."
    if len(base) + len(suffix) <= 75:
        return base + suffix
    words = base.split()
    while words and len(" ".join(words)) + len(suffix) > 75:
        words.pop()
    while words and words[-1].lower().strip(".,") in FILLER:
        words.pop()
    return " ".join(words) + suffix


def main():
    with open("/Users/tomasz/Desktop/allegro-buypack/create_zestawy_results.json", encoding="utf-8") as f:
        results = json.load(f)
    jobs = [(r["sku"], r["n"], r["offer_id"]) for r in results if r.get("offer_id")]
    # dołóż test 0009-12 (poza results); 0009-6 = wzorzec, zostawiamy
    jobs.append(("TP/0009", 12, "18764910333"))

    base_cache = {}
    def base_of(sku):
        if sku not in base_cache:
            base_cache[sku] = client.get(f"/sale/product-offers/{SINGLE[sku]}")["name"]
        return base_cache[sku]

    changed = []
    for sku, n, oid in jobs:
        new_name = clean_name(base_of(sku), n)
        try:
            client.patch(f"/sale/product-offers/{oid}", json={"name": new_name})
            print(f"  [OK] {oid} {sku}-{n} -> {new_name!r} ({len(new_name)})")
            changed.append({"offer_id": oid, "sku": sku, "n": n, "name": new_name})
        except AllegroAPIError as e:
            print(f"  [ERR] {oid} {sku}-{n}: {str(e)[:200]}")
        time.sleep(1.0)

    with open("/Users/tomasz/Desktop/allegro-buypack/fix_titles_results.json", "w", encoding="utf-8") as f:
        json.dump(changed, f, ensure_ascii=False, indent=2)
    print(f"\nGotowe: {len(changed)}/{len(jobs)} nazw poprawionych.")


if __name__ == "__main__":
    main()
