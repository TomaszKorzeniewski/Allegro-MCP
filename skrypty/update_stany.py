#!/usr/bin/env python3
"""Aktualizacja stanów magazynowych: rozdziela potwierdzony stan produktu
między ofertę pojedynczą i zestawy, zamiast duplikować go na każdym wariancie.

Źródło stanów: "Ilość zweryfikowana" z SKU_pojedyncze_do_weryfikacji 2.xlsx (2026-07-25).
Bufor 15% — rozdysponowujemy 85% potwierdzonego stanu.
"""
import json
import math
import sys
import time

from _sciezki import KORZEN, WYNIKI  # ustawia sys.path na korzeń projektu
from allegro_client import AllegroClient, AllegroAPIError

BUFOR = 0.85
DRY_RUN = "--apply" not in sys.argv
OUT = str(WYNIKI / "update_stany_results.json")

# SKU -> ilość zweryfikowana (kolumna G arkusza)
CONF = {
    "TP/0001": 1806, "TP/0002": 1332, "TP/0003": 3122, "TP/0004": 1392,
    "TP/0005": 2071, "TP/0006": 1466, "TP/0007": 1084, "TP/0008": 1824,
    "TP/0009": 4500, "TP/0010": 1436, "TP/0012": 1779, "TP/0013": 1852,
    "TP/0014": 2299, "TP/0015": 123, "TP/0016": 1789, "TP/0017": 1368,
    "TP/0018": 1679, "TP/0019": 3760, "TP/0024": 1124, "TP/0030": 879,
    "TPP-012T/2M": 980, "TPU-012T/2M": 790,
    "KT/0007": 493, "KT/0008": 10078, "KT/0009": 3808, "KT/0010": 5017,
    "KT/0011": 5647, "KT/0012": 4135, "KT/0013": 3600, "KT/0023": 941,
    "Koszyk na piwo 4 szt.": 10982, "Koszyk na piwo 6 szt.": 3999,
}

# Zestawy tub mają własne sygnatury, nie schemat "SKU - N szt."
TUBY_SETS = {
    "KT/0007": {10: "KT/0020", 20: "KT/0017"},
    "KT/0008": {10: "KT/0019", 20: "KT/0015"},
    "KT/0009": {10: "KT/0014", 20: "KT/0016"},
    "KT/0010": {10: "KT/0022"},
    "KT/0011": {20: "KT/0018"},
    "KT/0012": {20: "KT/0021"},
}

# dostępne rozmiary paczek -> udział w puli sztuk
WAGI = {
    (1, 6, 12, 36): {1: .60, 6: .20, 12: .12, 36: .08},
    (1, 6, 36): {1: .60, 6: .25, 36: .15},
    (6, 12, 36): {6: .50, 12: .30, 36: .20},
    (1, 6): {1: .80, 6: .20},
    (1, 10, 20): {1: .70, 10: .18, 20: .12},
    (1, 10): {1: .80, 10: .20},
    (1, 20): {1: .80, 20: .20},
    (1,): {1: 1.0},
}

c = AllegroClient()


def fetch_active():
    """ACTIVE + INACTIVE — świeżo wystawiona oferta potrafi kilkadziesiąt minut
    wisieć w kolejce publikacji jako INACTIVE, a i tak należy do puli stanu."""
    out = []
    for status in ("ACTIVE", "INACTIVE"):
        off = 0
        while True:
            r = c.get("/sale/offers", params={
                "limit": 1000, "offset": off, "publication.status": status})
            b = r.get("offers", [])
            out += b
            off += len(b)
            if off >= r.get("totalCount", 0) or not b:
                break
    return out


def build_plan(offers):
    by_ext = {}
    for o in offers:
        by_ext.setdefault((o.get("external") or {}).get("id"), []).append(o)

    groups = {}
    for sku in CONF:
        g = {}
        if sku in by_ext:
            g[1] = sku
        for n in (6, 12, 36):
            k = f"{sku} - {n} szt."
            if k in by_ext:
                g[n] = k
        for n, ext in TUBY_SETS.get(sku, {}).items():
            if ext in by_ext:
                g[n] = ext
        if sku.startswith("Koszyk") and f"{sku} x 10" in by_ext:
            g[10] = f"{sku} x 10"
        groups[sku] = g

    plan = []
    for sku, packs in groups.items():
        wagi = WAGI[tuple(sorted(packs))]
        budzet = math.floor(CONF[sku] * BUFOR)
        pula = CONF[sku] * BUFOR

        # wstępny przydział: udział w puli / rozmiar paczki, minimum 1 paczka
        wpisy = []
        for n, ext in sorted(packs.items()):
            dups = by_ext[ext]
            per_offer = pula * wagi[n] / len(dups)
            nowy = max(1, math.floor(per_offer / n))
            for o in dups:
                wpisy.append({"n": n, "ext": ext, "o": o, "stan": nowy})

        # Minimum 1 paczki potrafi przebić budżet przy małych stanach
        # (np. TP/0015: 123 szt., a samo 1× zestaw 36 szt. to 29% magazynu).
        # Nadwyżkę ścinamy zaczynając od najdrobniejszych paczek — tam
        # jedna sztuka mniej to najmniejsza strata widoczności.
        nadwyzka = sum(w["stan"] * w["n"] for w in wpisy) - budzet
        for w in sorted(wpisy, key=lambda w: w["n"]):
            if nadwyzka <= 0:
                break
            moze_oddac = (w["stan"] - 1) * w["n"]          # nigdy poniżej 1 paczki
            oddaje = min(moze_oddac, nadwyzka)
            w["stan"] -= math.ceil(oddaje / w["n"])
            nadwyzka = sum(x["stan"] * x["n"] for x in wpisy) - budzet

        for w in wpisy:
            plan.append({
                "produkt": sku, "pack": w["n"], "sku_oferty": w["ext"],
                "offer_id": w["o"]["id"], "nazwa": w["o"].get("name", ""),
                "stan_teraz": (w["o"].get("stock") or {}).get("available"),
                "stan_nowy": w["stan"], "sztuk_zarezerwowanych": w["stan"] * w["n"],
                "duplikat": len(by_ext[w["ext"]]) > 1,
            })
    return plan


def main():
    offers = fetch_active()
    plan = build_plan(offers)
    print(f"ACTIVE: {len(offers)}   w planie: {len(plan)}")

    pominiete = {o["id"] for o in offers} - {p["offer_id"] for p in plan}
    if pominiete:
        print(f"!! POMINIĘTE OFERTY: {sorted(pominiete)}")

    for sku in CONF:
        rs = [p for p in plan if p["produkt"] == sku]
        tot = sum(p["sztuk_zarezerwowanych"] for p in rs)
        print(f"{sku:24s} potw.{CONF[sku]:>6}  rozdysp.{tot:>6} "
              f"({tot / CONF[sku] * 100:.0f}%)")
        assert tot <= CONF[sku], f"PRZEKROCZONY STAN dla {sku}"

    if DRY_RUN:
        print("\nDRY-RUN — nic nie wysłano. Uruchom z --apply żeby zapisać.")
        json.dump(plan, open(OUT, "w"), ensure_ascii=False, indent=1)
        return

    ok, err, skip = [], [], []
    for i, p in enumerate(plan, 1):
        if p["stan_teraz"] == p["stan_nowy"]:
            skip.append(p["offer_id"])
            continue
        try:
            c.patch(f"/sale/product-offers/{p['offer_id']}",
                    json={"stock": {"available": p["stan_nowy"]}})
            ok.append(p)
            print(f"[{i}/{len(plan)}] OK  {p['offer_id']} "
                  f"{p['stan_teraz']} -> {p['stan_nowy']}  {p['sku_oferty']}")
        except AllegroAPIError as e:
            err.append({**p, "blad": str(e)})
            print(f"[{i}/{len(plan)}] ERR {p['offer_id']}: {e}")
        time.sleep(0.25)

    json.dump({"plan": plan, "ok": len(ok), "bez_zmian": skip, "bledy": err},
              open(OUT, "w"), ensure_ascii=False, indent=1)
    print(f"\nZaktualizowano: {len(ok)} | bez zmian: {len(skip)} | błędy: {len(err)}")
    print(f"Log: {OUT}")


if __name__ == "__main__":
    main()
