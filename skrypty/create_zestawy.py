#!/usr/bin/env python3
"""Tworzy zestawy 6/12/36 szt. dla taśm pojedynczych.

Metoda: GET żywej oferty pojedynczej -> kopiuje productSet (ten sam produkt
katalogowy) -> ustawia quantity.value=N -> zestawowy cennik dostawy -> opis
dziedziczony + "Zestaw N szt." / "N rolek" -> POST /sale/product-offers ACTIVE.

Użycie:
  python create_zestawy.py 0009:12        # jeden zestaw (test)
  python create_zestawy.py all            # wszystkie 59 (pomija 0009-6, już istnieje)
"""
import sys, json, time, re, copy
from _sciezki import KORZEN, WYNIKI  # ustawia sys.path na korzeń projektu
from allegro_client import AllegroClient, AllegroAPIError
from config import CATEGORY_ID, LOCATION, RETURN_POLICY_ID, WARRANTY_ID

client = AllegroClient()

ZESTAW_SHIPPING_ID = "98c51ddb-13d6-419f-94cb-57c68bd8f8b7"  # cennik dostawy zestawów (z wzorca 0009-6szt)

# sku -> live single offer_id
SINGLE = {
    "TP/0001": "18748619896", "TP/0002": "18734683435", "TP/0003": "18732815640",
    "TP/0004": "18734683525", "TP/0005": "18732829075", "TP/0006": "18735303719",
    "TP/0007": "18734683580", "TP/0008": "18732829273", "TP/0009": "18729289736",
    "TP/0010": "18734683657", "TP/0012": "18732829345", "TP/0013": "18734683710",
    "TP/0014": "18732816516", "TP/0015": "18735303774", "TP/0016": "18735303831",
    "TP/0017": "18735303892", "TP/0018": "18735303947", "TP/0019": "18734683779",
    "TP/0024": "18732829425", "TP/0030": "18735304061",
}

# sku -> {N: cena brutto} (zaakceptowane, pełne zł, wzorzec 0009 x0.87)
PRICE = {
    "TP/0001": {6: 26, 12: 51, 36: 154}, "TP/0002": {6: 27, 12: 53, 36: 159},
    "TP/0003": {6: 19, 12: 38, 36: 113}, "TP/0004": {6: 19, 12: 38, 36: 113},
    "TP/0005": {6: 14, 12: 29, 36: 86},  "TP/0006": {6: 26, 12: 52, 36: 155},
    "TP/0007": {6: 31, 12: 62, 36: 185}, "TP/0008": {6: 33, 12: 66, 36: 197},
    "TP/0009": {6: 36, 12: 72, 36: 216}, "TP/0010": {6: 22, 12: 44, 36: 132},
    "TP/0012": {6: 30, 12: 60, 36: 179}, "TP/0013": {6: 18, 12: 37, 36: 110},
    "TP/0014": {6: 36, 12: 72, 36: 216}, "TP/0015": {6: 26, 12: 51, 36: 153},
    "TP/0016": {6: 26, 12: 51, 36: 153}, "TP/0017": {6: 34, 12: 68, 36: 204},
    "TP/0018": {6: 52, 12: 104, 36: 312}, "TP/0019": {6: 26, 12: 51, 36: 153},
    "TP/0024": {6: 21, 12: 42, 36: 125}, "TP/0030": {6: 49, 12: 99, 36: 296},
}

SKIP = {("TP/0009", 6), ("TP/0009", 12)}  # 6szt=18733056059, 12szt=18764910333 (test) już istnieją


def build_name(base, n):
    name = f"Zestaw {n}x {base}"
    if len(name) <= 75:
        return name
    words = base.split()
    while words and len(f"Zestaw {n}x " + " ".join(words)) > 75:
        words.pop()
    return f"Zestaw {n}x " + " ".join(words)


def transform_desc(sections, n):
    secs = copy.deepcopy(sections)
    for si, sec in enumerate(secs):
        for item in sec.get("items", []):
            if item.get("type") != "TEXT":
                continue
            c = item["content"]
            if si == 0:
                c = c.replace("</h1>", f" | Zestaw {n} szt.</h1>", 1)
            c = re.sub(r"(Wariant:</b>\s*)1 rolka \(sztuka\)",
                       lambda m: m.group(1) + f"{n} rolek (sztuk)", c)
            c = re.sub(r"<h2>.*?</h2>",
                       "<h2>✔️ Sprzedajemy hurtowo – sprawdź nasze zestawy</h2>", c)
            item["content"] = c
    return secs


def strip_params(params):
    out = []
    for p in params or []:
        e = {"id": p["id"]}
        if p.get("valuesIds"):
            e["valuesIds"] = p["valuesIds"]
        elif p.get("values"):
            e["values"] = p["values"]
        out.append(e)
    return out


def make_zestaw(sku, n):
    single = client.get(f"/sale/product-offers/{SINGLE[sku]}")
    base_name = single["name"]
    ps = single["productSet"][0]
    prod_id = ps["product"]["id"]
    resp_prod = ps.get("responsibleProducer")
    safety = ps.get("safetyInformation")
    images = single.get("images", [])[:8]
    single_stock = (single.get("stock") or {}).get("available", 0) or 0
    stock = max(1, single_stock // n)
    price = f"{PRICE[sku][n]:.2f}"

    product_block = {"id": prod_id}
    prod_params = strip_params(ps["product"].get("parameters"))

    ps_entry = {
        "product": product_block,
        "quantity": {"value": n},
        "marketedBeforeGPSRObligation": ps.get("marketedBeforeGPSRObligation", False),
    }
    if resp_prod:
        ps_entry["responsibleProducer"] = {"id": resp_prod["id"]}
    if safety:
        ps_entry["safetyInformation"] = {"description": safety["description"], "type": safety.get("type", "TEXT")}

    payload = {
        "name": build_name(base_name, n),
        "category": {"id": CATEGORY_ID},
        "external": {"id": f"{sku} - {n} szt."},
        "productSet": [ps_entry],
        "images": images,
        "description": {"sections": transform_desc(single["description"]["sections"], n)},
        "parameters": strip_params(single.get("parameters")),
        "sellingMode": {"format": "BUY_NOW", "price": {"amount": price, "currency": "PLN"}},
        "stock": {"available": stock, "unit": "UNIT"},
        "publication": {"status": "ACTIVE"},
        "afterSalesServices": {
            "impliedWarranty": {"id": WARRANTY_ID},
            "returnPolicy": {"id": RETURN_POLICY_ID},
        },
        "delivery": {"shippingRates": {"id": ZESTAW_SHIPPING_ID}, "handlingTime": "PT24H"},
        "location": LOCATION,
        "payments": {"invoice": "VAT"},
    }
    if single.get("taxSettings"):
        payload["taxSettings"] = single["taxSettings"]

    def attempt(pl):
        return client.post("/sale/product-offers", json=pl)

    try:
        resp = attempt(payload)
    except AllegroAPIError as e:
        # retry z parametrami produktu, jeśli API ich żąda
        if "parametr" in str(e).lower() and prod_params:
            payload["productSet"][0]["product"]["parameters"] = prod_params
            resp = attempt(payload)
        else:
            raise
    return resp.get("id", "?"), price, stock


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    jobs = []
    if arg == "all":
        for sku in SINGLE:
            for n in (6, 12, 36):
                if (sku, n) not in SKIP:
                    jobs.append((sku, n))
    elif ":" in arg:
        s, n = arg.split(":")
        sku = s if s.startswith("TP/") else f"TP/{s}"
        jobs.append((sku, int(n)))
    else:
        print("Użycie: create_zestawy.py 0009:12 | all")
        return

    results = []
    for sku, n in jobs:
        try:
            oid, price, stock = make_zestaw(sku, n)
            print(f"  [OK] {sku} - {n} szt. -> {oid} | {price} PLN | stock {stock}")
            results.append({"sku": sku, "n": n, "offer_id": oid, "price": price, "stock": stock, "status": "ACTIVE"})
        except AllegroAPIError as e:
            print(f"  [ERR] {sku} - {n} szt.: {str(e)[:300]}")
            results.append({"sku": sku, "n": n, "offer_id": None, "error": str(e)[:300]})
        time.sleep(1.3)

    with open(str(WYNIKI / "create_zestawy_results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    ok = sum(1 for r in results if r.get("offer_id"))
    print(f"\nGotowe: {ok}/{len(results)} OK. Zapisano create_zestawy_results.json")


if __name__ == "__main__":
    main()
