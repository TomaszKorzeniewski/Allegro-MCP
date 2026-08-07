#!/usr/bin/env python3
"""
Batch creation of 13 single-unit (wariant 1) tape offers on Allegro.
All created as INACTIVE drafts. Prices filled by Tomasz manually before publishing.
Run: .venv/bin/python3 create_single_offers.py
"""

import json, sys, time, requests
from _sciezki import KORZEN, WYNIKI  # ustawia sys.path na korzeń projektu
from allegro_client import AllegroClient, AllegroAPIError
from config import CATEGORY_ID, LOCATION, RETURN_POLICY_ID, SHIPPING_RATES_ID, WARRANTY_ID

client = AllegroClient()

# ─── Template settings from TP/0009-1 ────────────────────────────────────────


# ─── 13 clean single-unit SKUs ───────────────────────────────────────────────
SKUS = [
    {"sku":"TP/0001","type":"akryl","kolor":"brązowy","sz":48,"dl":30,"stock":1806,
     "title":"Taśma Pakowa Brązowa Akrylowa 48mm/30m Klejąca do Pakowania Kartonów",
     "dalpo":"brazowa-tasma-pakowa-akryl-basic-rozne-rozmiary"},
    {"sku":"TP/0002","type":"akryl","kolor":"transparentny","sz":48,"dl":30,"stock":1332,
     "title":"Taśma Pakowa Transparentna Akrylowa 48mm/30m Klejąca Pakowanie Kartonów",
     "dalpo":"transparentna-tasma-pakowa-akryl-basic-rozne-rozmiary"},
    {"sku":"TP/0003","type":"akryl","kolor":"brązowy","sz":48,"dl":45,"stock":3122,
     "title":"Taśma Pakowa Brązowa Akrylowa 48mm/45m Klejąca do Pakowania Kartonów",
     "dalpo":"brazowa-tasma-pakowa-akryl-basic-rozne-rozmiary"},
    {"sku":"TP/0004","type":"akryl","kolor":"transparentny","sz":48,"dl":45,"stock":1392,
     "title":"Taśma Pakowa Transparentna Akrylowa 48mm/45m Klejąca Pakowanie Kartonów",
     "dalpo":"transparentna-tasma-pakowa-akryl-basic-rozne-rozmiary"},
    {"sku":"TP/0005","type":"akryl","kolor":"brązowy","sz":48,"dl":54,"stock":2071,
     "title":"Taśma Pakowa Brązowa Akrylowa 48mm/54m Klejąca do Pakowania Kartonów",
     "dalpo":"brazowa-tasma-pakowa-akryl-basic-rozne-rozmiary"},
    {"sku":"TP/0007","type":"akryl_cichy","kolor":"brązowy","sz":48,"dl":50,"stock":1084,
     "title":"Taśma Pakowa Brązowa Akrylowa Cicha 48mm/50m Klejąca do Kartonów Pakowanie",
     "dalpo":"brazowa-tasma-pakowa-akryl-cicha-48mm-54m"},
    {"sku":"TP/0008","type":"akryl_cichy","kolor":"transparentny","sz":48,"dl":50,"stock":1824,
     "title":"Taśma Pakowa Transparentna Akrylowa Cicha 48mm/50m Klejąca do Kartonów",
     "dalpo":"transparentna-tasma-pakowa-akryl-cicha-48-54m"},
    {"sku":"TP/0010","type":"hot_melt","kolor":"transparentny","sz":48,"dl":45,"stock":1436,
     "title":"Taśma Pakowa Transparentna Hot-melt 48mm/45m Klejąca do Kartonów Pakowanie",
     "dalpo":"transparentna-tasma-pakowa-hot-melt-rozne-rozmiary"},
    {"sku":"TP/0012","type":"solvent","kolor":"brązowy","sz":48,"dl":45,"stock":1779,
     "title":"Taśma Pakowa Brązowa Solvent Mocna 48mm/45m Klejąca do Kartonów Pakowanie",
     "dalpo":"brazowa-tasma-pakowa-mocna-solvent-rozne-rozmiary"},
    {"sku":"TP/0013","type":"solvent","kolor":"transparentny","sz":48,"dl":45,"stock":1852,
     "title":"Taśma Pakowa Transparentna Solvent Mocna 48mm/45m Klejąca do Kartonów",
     "dalpo":"transparentna-tasma-pakowa-mocna-solvent-rozne-rozmiary"},
    {"sku":"TP/0014","type":"solvent","kolor":"transparentny","sz":48,"dl":60,"stock":2299,
     "title":"Taśma Pakowa Transparentna Solvent Mocna 48mm/60m Klejąca do Kartonów",
     "dalpo":"transparentna-tasma-pakowa-mocna-solvent-rozne-rozmiary"},
    {"sku":"TP/0019","type":"nadruk","kolor":"biały","sz":48,"dl":45,"stock":3760,
     "title":"Taśma z Nadrukiem Ostrożnie Szkło Hot-melt 48mm/45m Klejąca do Paczek",
     "dalpo":"tasma-z-nadrukiem-ostroznie-szklo-48mm-x-45-m"},
    {"sku":"TP/0024","type":"hot_melt","kolor":"transparentny","sz":48,"dl":60,"stock":1124,
     "title":"Taśma Pakowa Transparentna Hot-melt 48mm/60m Klejąca do Kartonów Pakowanie",
     "dalpo":"transparentna-tasma-pakowa-hot-melt-rozne-rozmiary"},
]

# ─── Fetch images from Dalpo Shopify JSON API ────────────────────────────────
def get_dalpo_images(slug: str) -> list[str]:
    url = f"https://sklep.dalpo.pl/products/{slug}.json"
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        r.raise_for_status()
        imgs = r.json().get("product", {}).get("images", [])
        return [img["src"] for img in imgs if img.get("src")]
    except Exception as e:
        print(f"  [WARN] Dalpo images failed for {slug}: {e}")
        return []

# ─── Build description sections ─────────────────────────────────────────────
def spec_content(s, klej_pl: str) -> str:
    return (
        f"<p><b>➡️ Specyfikacja produktu</b></p>"
        f"<ul>"
        f"<li><b>Szerokość:</b> {s['sz']} mm</li>"
        f"<li><b>Długość:</b> {s['dl']} m</li>"
        f"<li><b>Kolor:</b> {s['kolor']}</li>"
        f"<li><b>Rodzaj kleju:</b> {klej_pl}</li>"
        f"<li><b>Materiał nośnika:</b> BOPP</li>"
        f"<li><b>Wariant:</b> 1 rolka (sztuka)</li>"
        f"</ul>"
    )

def build_description(s, imgs: list[str]) -> dict:
    n = len(imgs)
    if n == 0:
        return None
    i1 = imgs[0]
    i2 = imgs[min(1, n-1)]
    i3 = imgs[min(2, n-1)]
    i4 = imgs[min(3, n-1)]

    t = s["type"]

    if t == "akryl_cichy":
        h1_spec = "✳️ Cicha taśma akrylowa – mocne sklejenie bez hałasu dyspensera"
        lead = "Hałas rozwijającej się taśmy w biurze lub magazynie potrafi być naprawdę uciążliwy. Wersja cicha eliminuje ten problem — zachowując całą wytrzymałość standardowego akrylu."
        klej_pl = "akryl (wytłumiony)"
        zalety = (
            "<p><b>✅ Cicha praca</b> – odwija się bez charakterystycznego zgrzytania – pracownicy mogą skupić się na pracy, nie na hałasie.</p>"
            "<p><b>✳️ Wytrzymałość akrylu</b> – mocne i trwałe sklejenie kartonów – paczka dotrze do klienta szczelna, bez ryzyka otwarcia w transporcie.</p>"
            f"<p><b>⭐ Odporność na UV i temperaturę</b> – nie żółknie i nie traci przyczepności – taśma trzyma równie dobrze latem jak zimą.</p>"
            f"<p><b>🛡️ Długość {s['dl']}m na rolce</b> – więcej metrów za tę samą cenę – rzadziej wymieniasz rolkę, mniej przestojów.</p>"
        )
        zastosowania_li = "<li>wszędzie tam, gdzie hałas dyspensera taśmy jest uciążliwy.</li>"

    elif t == "hot_melt":
        h1_spec = "✳️ Taśma hot-melt – błyskawiczne klejenie kauczukiem, wysoka przyczepność"
        lead = "Taśma hot-melt z klejem kauczukowym — wyjątkowo szybkie klejenie i duża siła przyczepności do kartonów."
        klej_pl = "kauczuk (hot-melt)"
        zalety = (
            "<p><b>✅ Błyskawiczne klejenie</b> – klej kauczukowy wiąże natychmiast po przyłożeniu – szybsza praca na stanowisku pakowania.</p>"
            "<p><b>✳️ Mocna przyczepność</b> – utrzymuje szczelność nawet przy cięższych paczkach i dłuższym transporcie.</p>"
            "<p><b>⭐ Odporność na wilgoć i mróz</b> – nie traci właściwości w niskich temperaturach i przy wilgoci.</p>"
            f"<p><b>🛡️ Długość {s['dl']}m na rolce</b> – więcej metrów za tę samą cenę – rzadziej wymieniasz rolkę, mniej przestojów.</p>"
        )
        zastosowania_li = "<li>środowiskach z niższą temperaturą – magazyn chłodniczy, transport zimowy.</li>"

    elif t == "solvent":
        h1_spec = "✳️ Taśma solvent – najsilniejsze klejenie do wymagających warunków"
        lead = "Taśma solvent z klejem rozpuszczalnikowym — najsilniejsza klasa taśm pakowych, niezastąpiona tam, gdzie standardowy akryl zawodzi."
        klej_pl = "rozpuszczalnikowy (solvent)"
        zalety = (
            "<p><b>✅ Ekstremalnie mocna przyczepność</b> – solvent to najsilniejszy klej w klasie taśm pakowych – niezawodny przy trudnych powierzchniach.</p>"
            "<p><b>✳️ Odporność na trudne warunki</b> – trzyma na chropowatych, niejednorodnych i trudnych powierzchniach.</p>"
            "<p><b>⭐ Trwałość klejenia</b> – nie odkleją się nawet po wielu dniach przechowywania w magazynie.</p>"
            f"<p><b>🛡️ Długość {s['dl']}m na rolce</b> – więcej metrów za tę samą cenę – rzadziej wymieniasz rolkę, mniej przestojów.</p>"
        )
        zastosowania_li = "<li>aplikacjach wymagających najwyższej siły klejenia — ciężkie kartony, trudne powierzchnie.</li>"

    elif t == "nadruk":
        h1_spec = "✳️ Taśma z nadrukiem Ostrożnie Szkło – klej hot-melt, natychmiastowe klejenie"
        lead = "Taśma pakowa z czytelnym nadrukiem ostrzegawczym \"Ostrożnie szkło\" — hot-melt z klejem kauczukowym, natychmiastowe i mocne klejenie."
        klej_pl = "kauczuk (hot-melt)"
        zalety = (
            "<p><b>✅ Czytelny nadruk ostrzegawczy</b> – od razu widoczne oznaczenie \"Ostrożnie szkło\" – kurier i magazynier widzą, że paczka wymaga ostrożności.</p>"
            "<p><b>✳️ Klej hot-melt (kauczuk)</b> – natychmiastowe i mocne klejenie – taśma przylega od razu po przyłożeniu.</p>"
            "<p><b>⭐ Biała taśma z czerwonym nadrukiem</b> – wyraźna i widoczna – nadruk wyróżnia się na tle kartonu.</p>"
            f"<p><b>🛡️ Długość {s['dl']}m na rolce</b> – więcej metrów za tę samą cenę – rzadziej wymieniasz rolkę.</p>"
        )
        zastosowania_li = "<li>wysyłkach zawierających szkło, ceramikę, elektronikę i inne kruche przedmioty.</li>"

    else:  # akryl standard
        h1_spec = "✳️ Taśma akrylowa – mocne klejenie, odporność na UV i temperaturę"
        lead = "Sprawdzona taśma akrylowa do pakowania kartonów — mocne i stabilne klejenie, niezawodna jakość w codziennej pracy."
        klej_pl = "akrylowy"
        zalety = (
            "<p><b>✅ Mocne i stabilne klejenie</b> – taśma przylega do kartonów bez przesuwania – paczka dotrze do klienta szczelna, bez ryzyka otwarcia.</p>"
            "<p><b>✳️ Odporność na UV i temperaturę</b> – nie żółknie i nie traci przyczepności w zmieniających się warunkach – trzyma latem i zimą.</p>"
            "<p><b>⭐ Ekonomiczna cena</b> – dobrze wyważony stosunek jakości do kosztów – dobry wybór do codziennego pakowania.</p>"
            f"<p><b>🛡️ Długość {s['dl']}m na rolce</b> – więcej metrów za tę samą cenę – rzadziej wymieniasz rolkę, mniej przestojów.</p>"
        )
        zastosowania_li = ""

    return {"sections": [
        {"items": [{"type": "TEXT", "content": f"<h1>✳️ {s['title']}</h1>"}]},
        {"items": [
            {"type": "IMAGE", "url": i1},
            {"type": "TEXT", "content": (
                f"<h1>{h1_spec}</h1><p>{lead}</p>" + spec_content(s, klej_pl)
            )},
        ]},
        {"items": [
            {"type": "IMAGE", "url": i2},
            {"type": "TEXT", "content": f"<h1>✳️ Zalety i właściwości</h1>{zalety}"},
        ]},
        {"items": [
            {"type": "IMAGE", "url": i3},
            {"type": "TEXT", "content": (
                f"<h1>✳️ Do czego się przyda?</h1>"
                f"<p><b>➡️ Sprawdzi się przy:</b></p>"
                f"<ul>"
                f"<li>pakowaniu kartonów i przesyłek kurierskich,</li>"
                f"<li>wysyłkach na dużą skalę – magazyn, sklep internetowy, praca zmianowa,</li>"
                f"{zastosowania_li}"
                f"</ul>"
                f"<p>⚠️ Taśma przeznaczona wyłącznie do pakowania. Nie stosować do instalacji elektrycznych ani hydraulicznych.</p>"
                f"<h2>✔️ Sprzedajemy hurtowo – sprawdź nasze zestawy 6 i 36 rolek w obniżonej cenie.</h2>"
            )},
        ]},
        {"items": [{"type": "IMAGE", "url": i4}]},
    ]}

# ─── Create one offer via API ─────────────────────────────────────────────────
def create_offer(s, desc, imgs):
    payload = {
        "name": s["title"],
        "category": {"id": CATEGORY_ID},
        "external": {"id": f"{s['sku']}-1"},
        "images": imgs[:8],
        "description": desc,
        "parameters": [{"id": "11323", "values": ["Nowy"], "valuesIds": ["11323_1"]}],
        "sellingMode": {"format": "BUY_NOW", "price": {"amount": "1.00", "currency": "PLN"}},
        "stock": {"available": s["stock"], "unit": "UNIT"},
        "publication": {"status": "INACTIVE"},
        "afterSalesServices": {
            "impliedWarranty": {"id": WARRANTY_ID},
            "returnPolicy": {"id": RETURN_POLICY_ID},
        },
        "delivery": {"shippingRates": {"id": SHIPPING_RATES_ID}, "handlingTime": "PT24H"},
        "location": LOCATION,
        "payments": {"invoice": "VAT"},
    }
    return client.post("/sale/product-offers", json=payload)

# ─── Main ─────────────────────────────────────────────────────────────────────
results = []

for s in SKUS:
    print(f"\n{'='*60}")
    print(f"Processing: {s['sku']} — {s['title'][:50]}...")
    print(f"  Title length: {len(s['title'])} chars")

    imgs = get_dalpo_images(s["dalpo"])
    print(f"  Dalpo images found: {len(imgs)}")
    if not imgs:
        print(f"  [SKIP] No images — skipping {s['sku']}")
        results.append({"sku": s["sku"], "status": "SKIP_NO_IMAGES", "offer_id": None})
        continue

    desc = build_description(s, imgs)
    try:
        resp = create_offer(s, desc, imgs)
        oid = resp.get("id", "?")
        print(f"  [OK] Created offer ID: {oid}")
        results.append({"sku": s["sku"], "title": s["title"], "status": "CREATED", "offer_id": oid})
    except AllegroAPIError as e:
        print(f"  [ERROR] {e}")
        results.append({"sku": s["sku"], "status": f"ERROR: {e}", "offer_id": None})

    time.sleep(1)  # rate limit buffer

print(f"\n{'='*60}")
print("RESULTS:")
for r in results:
    print(f"  {r['sku']} | {r['status']} | {r.get('offer_id','')}")

# Save results
with open(str(WYNIKI / "create_single_results.json"), "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print("\nSaved to create_single_results.json")
