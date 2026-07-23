#!/usr/bin/env python3
"""Sumuje sprzedaż konta: paginuje zamówienia (checkout-forms), grupuje po miesiącu."""
import sys, json
from collections import defaultdict
sys.path.insert(0, "/Users/tomasz/Desktop/allegro-buypack")
from allegro_client import AllegroClient

client = AllegroClient()

def fetch_all():
    forms = []
    offset = 0
    while True:
        r = client.get("/order/checkout-forms", params={"limit": 100, "offset": offset})
        batch = r.get("checkoutForms", [])
        forms.extend(batch)
        total = r.get("totalCount", 0)
        offset += 100
        if offset >= total or not batch:
            break
    return forms, total

forms, total = fetch_all()
by_month = defaultdict(lambda: {"count": 0, "sum": 0.0})
grand = 0.0
gcount = 0
cancelled = 0
for f in forms:
    status = f.get("status", "")
    amt = float(((f.get("summary") or {}).get("totalToPay") or {}).get("amount", 0) or 0)
    when = f.get("boughtAt") or f.get("updatedAt") or ""
    if status == "CANCELLED":
        cancelled += 1
        continue
    ym = when[:7] if when else "????-??"
    by_month[ym]["count"] += 1
    by_month[ym]["sum"] += amt
    grand += amt
    gcount += 1

print(f"totalCount(API)={total}  pobrano={len(forms)}  anulowane={cancelled}")
print(f"ZAMÓWIENIA (nie-anulowane): {gcount}  OBRÓT: {grand:.2f} PLN")
print("MIESIĄCE:")
for ym in sorted(by_month):
    d = by_month[ym]
    print(f"  {ym}: {d['count']} zam. | {d['sum']:.2f} PLN")

json.dump({"total_orders": gcount, "gmv": round(grand, 2),
           "by_month": {k: {"count": v["count"], "sum": round(v["sum"], 2)} for k, v in by_month.items()}},
          open("/Users/tomasz/Desktop/allegro-buypack/sales_summary.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
