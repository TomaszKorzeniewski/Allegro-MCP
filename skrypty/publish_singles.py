#!/usr/bin/env python3
"""
Delete 13 old INACTIVE offers (no product link) and recreate properly:
- Full productSet with inline product (images, params, safety, responsibleProducer)
- Correct description sections (5-section image+text layout)
- Price at 50% margin + 2 PLN (brutto)
- Status ACTIVE — published immediately
"""
import sys, json, time, requests
from _sciezki import KORZEN, WYNIKI  # ustawia sys.path na korzeń projektu
from allegro_client import AllegroClient, AllegroAPIError
from config import CATEGORY_ID, LOCATION, RESPONSIBLE_PRODUCER_ID, RETURN_POLICY_ID, SAFETY_TEXT, SHIPPING_RATES_ID, WARRANTY_ID

client = AllegroClient()



# ─── SKU data ─────────────────────────────────────────────────────────────────
# (sku, old_offer_id, title, kolor_id, klej_id, sz, dl, EAN, dalpo_slug, price_brutto, nadruk_id)
BOPP="236026_1647664"; BRAZ="10906_2"; BEZB="10906_1"; BIALY="10906_1121139"
AKR="10905_1"; HM="10905_1648206"; SOL="10905_1648207"
BRAK="249936_1784793"; OSTRZEG="249936_1784794"

SKUS = [
  ("TP/0001","18732779802",
   "Taśma Pakowa Brązowa Akrylowa 48mm/30m Klejąca do Pakowania Kartonów",
   BRAZ, AKR, 48, 30, "5905833094019",
   "brazowa-tasma-pakowa-akryl-basic-rozne-rozmiary", "4.92", BRAK, "akryl"),
  ("TP/0002","18732779959",
   "Taśma Pakowa Transparentna Akrylowa 48mm/30m Klejąca Pakowanie Kartonów",
   BEZB, AKR, 48, 30, "5905833093982",
   "transparentna-tasma-pakowa-akryl-basic-rozne-rozmiary", "5.09", BRAK, "akryl"),
  ("TP/0003","18732780009",
   "Taśma Pakowa Brązowa Akrylowa 48mm/45m Klejąca do Pakowania Kartonów",
   BRAZ, AKR, 48, 45, "5905833094026",
   "brazowa-tasma-pakowa-akryl-basic-rozne-rozmiary", "5.90", BRAK, "akryl"),
  ("TP/0004","18732780118",
   "Taśma Pakowa Transparentna Akrylowa 48mm/45m Klejąca Pakowanie Kartonów",
   BEZB, AKR, 48, 45, "5905833094040",
   "transparentna-tasma-pakowa-akryl-basic-rozne-rozmiary", "5.90", BRAK, "akryl"),
  ("TP/0005","18732780177",
   "Taśma Pakowa Brązowa Akrylowa 48mm/54m Klejąca do Pakowania Kartonów",
   BRAZ, AKR, 48, 54, "5905833094088",
   "brazowa-tasma-pakowa-akryl-basic-rozne-rozmiary", "5.04", BRAK, "akryl"),
  ("TP/0007","18732780220",
   "Taśma Pakowa Brązowa Akrylowa Cicha 48mm/50m Klejąca do Kartonów Pakowanie",
   BRAZ, AKR, 48, 50, "5905833094125",
   "brazowa-tasma-pakowa-akryl-cicha-48mm-54m", "8.63", BRAK, "akryl_cichy"),
  ("TP/0008","18732780312",
   "Taśma Pakowa Transparentna Akrylowa Cicha 48mm/50m Klejąca do Kartonów",
   BEZB, AKR, 48, 50, "5905833094149",
   "transparentna-tasma-pakowa-akryl-cicha-48-54m", "8.63", BRAK, "akryl_cichy"),
  ("TP/0010","18732780421",
   "Taśma Pakowa Transparentna Hot-melt 48mm/45m Klejąca do Kartonów Pakowanie",
   BEZB, HM, 48, 45, "5905833092633",
   "transparentna-tasma-pakowa-hot-melt-rozne-rozmiary", "6.59", BRAK, "hot_melt"),
  ("TP/0012","18732780524",
   "Taśma Pakowa Brązowa Solvent Mocna 48mm/45m Klejąca do Kartonów Pakowanie",
   BRAZ, SOL, 48, 45, "5905833093852",
   "brazowa-tasma-pakowa-mocna-solvent-rozne-rozmiary", "7.06", BRAK, "solvent"),
  ("TP/0013","18732780636",
   "Taśma Pakowa Transparentna Solvent Mocna 48mm/45m Klejąca do Kartonów",
   BEZB, SOL, 48, 45, "5905833093876",
   "transparentna-tasma-pakowa-mocna-solvent-rozne-rozmiary", "5.93", BRAK, "solvent"),
  ("TP/0014","18732780739",
   "Taśma Pakowa Transparentna Solvent Mocna 48mm/60m Klejąca do Kartonów",
   BEZB, SOL, 48, 60, "5905833093920",
   "transparentna-tasma-pakowa-mocna-solvent-rozne-rozmiary", "10.38", BRAK, "solvent"),
  ("TP/0019","18732780879",
   "Taśma z Nadrukiem Ostrożnie Szkło Hot-melt 48mm/45m Klejąca do Paczek",
   BIALY, HM, 48, 45, "5905833093227",
   "tasma-z-nadrukiem-ostroznie-szklo-48mm-x-45-m", "7.77", OSTRZEG, "nadruk"),
  ("TP/0024","18732781021",
   "Taśma Pakowa Transparentna Hot-melt 48mm/60m Klejąca do Kartonów Pakowanie",
   BEZB, HM, 48, 60, "5905833092633",
   "transparentna-tasma-pakowa-hot-melt-rozne-rozmiary", "6.32", BRAK, "hot_melt"),
]

def get_dalpo_images(slug):
    try:
        r = requests.get(f"https://sklep.dalpo.pl/products/{slug}.json",
                         headers={"User-Agent":"Mozilla/5.0"}, timeout=15)
        return [img["src"] for img in r.json()["product"]["images"] if img.get("src")]
    except Exception as e:
        print(f"  [WARN] images fetch failed: {e}")
        return []

def build_description(title, dl, t, imgs):
    n = len(imgs)
    i1 = imgs[0]; i2 = imgs[min(1,n-1)]; i3 = imgs[min(2,n-1)]; i4 = imgs[min(3,n-1)]

    if t == "akryl_cichy":
        h1s = "✳️ Cicha taśma akrylowa – mocne sklejenie bez hałasu dyspensera"
        lead = "Hałas rozwijającej się taśmy w biurze lub magazynie potrafi być naprawdę uciążliwy. Wersja cicha eliminuje ten problem — zachowując całą wytrzymałość standardowego akrylu."
        zalety = (
            "<p><b>✅ Cicha praca</b> – odwija się bez zgrzytania – pracownicy mogą skupić się na pracy.</p>"
            "<p><b>✳️ Wytrzymałość akrylu</b> – mocne i trwałe sklejenie kartonów.</p>"
            f"<p><b>⭐ Odporność na UV i temperaturę</b> – nie żółknie, trzyma latem jak zimą.</p>"
            f"<p><b>🛡️ Długość {dl}m na rolce</b> – rzadziej wymieniasz rolkę, mniej przestojów.</p>")
        li_extra = "<li>wszędzie tam, gdzie hałas dyspensera taśmy jest uciążliwy.</li>"
    elif t == "hot_melt":
        h1s = "✳️ Taśma hot-melt – błyskawiczne klejenie kauczukiem, wysoka przyczepność"
        lead = "Taśma hot-melt z klejem kauczukowym — wyjątkowo szybkie klejenie i duża siła przyczepności do kartonów."
        zalety = (
            "<p><b>✅ Błyskawiczne klejenie</b> – klej kauczukowy wiąże natychmiast po przyłożeniu.</p>"
            "<p><b>✳️ Mocna przyczepność</b> – utrzymuje szczelność nawet przy cięższych paczkach.</p>"
            "<p><b>⭐ Odporność na wilgoć i mróz</b> – nie traci właściwości w niskich temperaturach.</p>"
            f"<p><b>🛡️ Długość {dl}m na rolce</b> – rzadziej wymieniasz rolkę, mniej przestojów.</p>")
        li_extra = "<li>środowiskach z niższą temperaturą – magazyn chłodniczy, transport zimowy.</li>"
    elif t == "solvent":
        h1s = "✳️ Taśma solvent – najsilniejsze klejenie do wymagających warunków"
        lead = "Taśma solvent z klejem rozpuszczalnikowym — najsilniejsza klasa taśm pakowych, niezastąpiona tam, gdzie standardowy akryl zawodzi."
        zalety = (
            "<p><b>✅ Ekstremalnie mocna przyczepność</b> – najsilniejszy klej w klasie taśm pakowych.</p>"
            "<p><b>✳️ Odporność na trudne warunki</b> – trzyma na chropowatych i trudnych powierzchniach.</p>"
            "<p><b>⭐ Trwałość klejenia</b> – nie odkleją się nawet po dłuższym przechowywaniu.</p>"
            f"<p><b>🛡️ Długość {dl}m na rolce</b> – rzadziej wymieniasz rolkę, mniej przestojów.</p>")
        li_extra = "<li>aplikacjach wymagających najwyższej siły klejenia – ciężkie kartony, trudne powierzchnie.</li>"
    elif t == "nadruk":
        h1s = "✳️ Taśma z nadrukiem Ostrożnie Szkło – hot-melt, natychmiastowe klejenie"
        lead = "Taśma pakowa z czytelnym nadrukiem ostrzegawczym \"Ostrożnie szkło\" — klej hot-melt, natychmiastowe i mocne klejenie."
        zalety = (
            "<p><b>✅ Czytelny nadruk ostrzegawczy</b> – kurier i magazynier widzą, że paczka wymaga ostrożności.</p>"
            "<p><b>✳️ Klej hot-melt (kauczuk)</b> – natychmiastowe i mocne klejenie.</p>"
            "<p><b>⭐ Biała taśma z czerwonym nadrukiem</b> – wyraźnie widoczna na tle kartonu.</p>"
            f"<p><b>🛡️ Długość {dl}m na rolce</b> – rzadziej wymieniasz rolkę.</p>")
        li_extra = "<li>wysyłkach zawierających szkło, ceramikę, elektronikę i inne kruche przedmioty.</li>"
    else:  # akryl
        h1s = "✳️ Taśma akrylowa – mocne klejenie, odporność na UV i temperaturę"
        lead = "Sprawdzona taśma akrylowa do pakowania kartonów — mocne i stabilne klejenie, niezawodna jakość w codziennej pracy."
        zalety = (
            "<p><b>✅ Mocne i stabilne klejenie</b> – paczka dotrze do klienta szczelna, bez ryzyka otwarcia.</p>"
            "<p><b>✳️ Odporność na UV i temperaturę</b> – nie żółknie, trzyma latem i zimą.</p>"
            "<p><b>⭐ Ekonomiczna cena</b> – dobry stosunek jakości do kosztów codziennego pakowania.</p>"
            f"<p><b>🛡️ Długość {dl}m na rolce</b> – rzadziej wymieniasz rolkę, mniej przestojów.</p>")
        li_extra = ""

    return {"sections": [
        {"items": [{"type":"TEXT","content":f"<h1>✳️ {title}</h1>"}]},
        {"items": [
            {"type":"IMAGE","url":i1},
            {"type":"TEXT","content":f"<h1>{h1s}</h1><p>{lead}</p>"},
        ]},
        {"items": [
            {"type":"IMAGE","url":i2},
            {"type":"TEXT","content":f"<h1>✳️ Zalety i właściwości</h1>{zalety}"},
        ]},
        {"items": [
            {"type":"IMAGE","url":i3},
            {"type":"TEXT","content":(
                f"<h1>✳️ Do czego się przyda?</h1>"
                f"<p><b>➡️ Sprawdzi się przy:</b></p><ul>"
                f"<li>pakowaniu kartonów i przesyłek kurierskich,</li>"
                f"<li>wysyłkach na dużą skalę – magazyn, sklep internetowy, praca zmianowa,</li>"
                f"{li_extra}</ul>"
                f"<p>⚠️ Taśma przeznaczona wyłącznie do pakowania. Nie stosować do instalacji elektrycznych ani hydraulicznych.</p>"
                f"<h2>✔️ Sprzedajemy hurtowo – sprawdź nasze zestawy 6 i 36 rolek w obniżonej cenie.</h2>"
            )},
        ]},
        {"items": [{"type":"IMAGE","url":i4}]},
    ]}

results = []

for sku, old_id, title, kolor_id, klej_id, sz, dl, ean, dalpo_slug, price, nadruk_id, t in SKUS:
    print(f"\n{'='*55}")
    print(f"{sku} — {title[:50]}...")

    # 1) Delete old offer
    try:
        client.delete(f"/sale/offers/{old_id}")
        print(f"  Deleted old offer {old_id}")
    except AllegroAPIError as e:
        print(f"  [WARN] delete: {e}")

    time.sleep(0.5)

    # 2) Get images from Dalpo
    imgs = get_dalpo_images(dalpo_slug)
    if not imgs:
        print(f"  [SKIP] No images")
        results.append({"sku":sku,"status":"SKIP_NO_IMAGES","offer_id":None})
        continue
    print(f"  Images: {len(imgs)}")

    # 3) Build description
    desc = build_description(title, dl, t, imgs)

    # 4) Create offer with full productSet + ACTIVE
    payload = {
        "name": title,
        "category": {"id": CATEGORY_ID},
        "external": {"id": f"{sku}-1"},
        "productSet": [{
            "product": {
                "name": title,
                "category": {"id": CATEGORY_ID},
                "images": imgs[:4],   # plain strings!
                "parameters": [
                    {"id":"248811","valuesIds":["248811_1131943"]},  # Marka: Dalpo
                    {"id":"236026","valuesIds":[BOPP]},              # Materiał: BOPP
                    {"id":"10906", "valuesIds":[kolor_id]},          # Kolor
                    {"id":"10905", "valuesIds":[klej_id]},           # Rodzaj kleju
                    {"id":"227381","values":[str(sz)]},              # Szerokość
                    {"id":"203949","values":[str(dl)]},              # Długość
                    {"id":"233101","values":["1"]},                  # Liczba sztuk
                    {"id":"225693","values":[ean]},                  # EAN
                    {"id":"249936","valuesIds":[nadruk_id]},         # Nadruk
                    {"id":"17448", "values":["0.1"]},                # Waga
                    {"id":"250792","values":["39211900"]},           # Kod taryfy
                ],
            },
            "quantity": {"value": 1},
            "responsibleProducer": {"id": RESPONSIBLE_PRODUCER_ID},
            "safetyInformation": {"description": SAFETY_TEXT, "type": "TEXT"},
            "marketedBeforeGPSRObligation": False,
        }],
        "images": imgs[:8],
        "description": desc,
        "parameters": [{"id":"11323","values":["Nowy"],"valuesIds":["11323_1"]}],
        "sellingMode": {"format":"BUY_NOW","price":{"amount":price,"currency":"PLN"}},
        "stock": {"available":0,"unit":"UNIT"},  # will set stock after; 0 avoids instant sale
        "publication": {"status": "ACTIVE"},
        "afterSalesServices": {
            "impliedWarranty": {"id": WARRANTY_ID},
            "returnPolicy": {"id": RETURN_POLICY_ID},
        },
        "delivery": {"shippingRates":{"id":SHIPPING_RATES_ID},"handlingTime":"PT24H"},
        "location": LOCATION,
        "payments": {"invoice": "VAT"},
    }

    try:
        resp = client.post("/sale/product-offers", json=payload)
        new_id = resp.get("id","?")
        prod_id = None
        for ps in resp.get("productSet",[]):
            prod_id = (ps.get("product") or {}).get("id")
        print(f"  [OK] New offer: {new_id} | product: {prod_id} | {price} PLN | ACTIVE")

        # 5) Set correct stock
        client.patch(f"/sale/product-offers/{new_id}", json={"stock":{"available": 9999}})

        results.append({"sku":sku,"status":"ACTIVE","offer_id":new_id,"price":price})
    except AllegroAPIError as e:
        print(f"  [ERR] {str(e)[:150]}")
        results.append({"sku":sku,"status":f"ERROR","offer_id":None})

    time.sleep(1)

print(f"\n{'='*55}")
print("RESULTS:")
for r in results:
    print(f"  {r['sku']} | {r['status']} | {r.get('offer_id','')} | {r.get('price','')} PLN")

with open(str(WYNIKI / "publish_results.json"),"w",encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print("Saved to publish_results.json")
