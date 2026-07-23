#!/usr/bin/env python3
"""
Opcja A — 7 zablokowanych SKU (catalog-mismatch)
Linkuje do istniejącego catalog product ID zamiast tworzyć nowy produkt inline.
Próbuje ACTIVE; jeśli błąd → INACTIVE (szkic do ręcznego opublikowania przez Tomasza).
"""
import sys, json, time, requests
sys.path.insert(0, '/Users/tomasz/Desktop/allegro-buypack')
from allegro_client import AllegroClient, AllegroAPIError

client = AllegroClient()

RESPONSIBLE_PRODUCER_ID = "a0e7065b-d173-4b9c-8de6-37dd0535899b"
WARRANTY_ID       = "c6bd41ce-bc1c-41a6-be3c-651dd035dc43"
RETURN_POLICY_ID  = "3af930f6-631c-420f-ab59-23582f9288ff"
SHIPPING_RATES_ID = "fcf29f15-4038-4046-be17-f047d8f56f89"
LOCATION = {"countryCode":"PL","province":"SLASKIE","city":"Cieszyn","postCode":"43-400"}
CATEGORY_ID = "64541"

SAFETY_TEXT = (
    "List of packing belt safety warnings based on the requirements of General Product Safety "
    "Regulation (EU) 2023/988 (GPSR):\n"
    "* Risk of intersection: Watch out for the sharp edges of the belt dispenser or the tape itself. "
    "You can cut yourself while cutting off.\n"
    "* Suffocation Hazard: Do not allow children to play with packing tape. "
    "There is a risk of wrapping around the neck and suffocation.\n"
    "* Skin allergies: If you experience an allergic reaction on your skin after contact with the "
    "adhesive, stop using the tape.\n"
    "* Storage: Store the tape in a dry and cool place, away from direct sunlight and heat sources.\n"
    "* Recycling: After use, dispose of it in a suitable waste container."
)

# (sku, catalog_product_id, title, dalpo_slug, price_brutto, stock, typ_opisu)
SKUS = [
  ("TP/0001",
   "36f6d01b-65a7-4445-abac-1b2eb50ea4da",
   "Taśma Pakowa Brązowa Akrylowa 48mm/30m Klejąca do Pakowania Kartonów",
   "brazowa-tasma-pakowa-akryl-basic-rozne-rozmiary",
   "4.92", 1806, "akryl"),
  ("TP/0002",
   "d17b5157-7c40-4028-ad80-846148d7a67e",
   "Taśma Pakowa Transparentna Akrylowa 48mm/30m Klejąca Pakowanie Kartonów",
   "transparentna-tasma-pakowa-akryl-basic-rozne-rozmiary",
   "5.09", 1332, "akryl"),
  ("TP/0004",
   "997e7e84-6ed6-4b9a-bb8c-08f13405f13b",
   "Taśma Pakowa Transparentna Akrylowa 48mm/45m Klejąca Pakowanie Kartonów",
   "transparentna-tasma-pakowa-akryl-basic-rozne-rozmiary",
   "5.90", 1392, "akryl"),
  ("TP/0007",
   "2eade502-ffee-4947-866e-e38eefc8ac03",
   "Taśma Pakowa Brązowa Akrylowa Cicha 48mm/50m Klejąca do Kartonów Pakowanie",
   "brazowa-tasma-pakowa-akryl-cicha-48mm-54m",
   "8.63", 1084, "akryl_cichy"),
  ("TP/0010",
   "c757c364-f78e-4c33-9f1b-ae1fa115a542",
   "Taśma Pakowa Transparentna Hot-melt 48mm/45m Klejąca do Kartonów Pakowanie",
   "transparentna-tasma-pakowa-hot-melt-rozne-rozmiary",
   "6.59", 1436, "hot_melt"),
  ("TP/0013",
   "e2b0a9ea-1af2-401c-b410-07825734412d",
   "Taśma Pakowa Transparentna Solvent Mocna 48mm/45m Klejąca do Kartonów",
   "transparentna-tasma-pakowa-mocna-solvent-rozne-rozmiary",
   "5.93", 1852, "solvent"),
  ("TP/0019",
   "a166de1b-15a1-4e86-95c7-8ca4b485695f",
   "Taśma z Nadrukiem Ostrożnie Szkło Hot-melt 48mm/45m Klejąca do Paczek",
   "tasma-z-nadrukiem-ostroznie-szklo-48mm-x-45-m",
   "7.77", 3760, "nadruk"),
]

def get_dalpo_images(slug):
    try:
        r = requests.get(f"https://sklep.dalpo.pl/products/{slug}.json",
                         headers={"User-Agent":"Mozilla/5.0"}, timeout=15)
        return [img["src"] for img in r.json()["product"]["images"] if img.get("src")]
    except Exception as e:
        print(f"  [WARN] images fetch failed: {e}")
        return []

def build_description(title, t, imgs):
    n = len(imgs)
    i1 = imgs[0]; i2 = imgs[min(1,n-1)]; i3 = imgs[min(2,n-1)]; i4 = imgs[min(3,n-1)]

    # Extract length from title for display
    dl_str = ""
    for part in title.split("/"):
        if part.endswith("m"):
            dl_str = part.replace("m","") + "m"
            break

    if t == "akryl_cichy":
        h1s = "✳️ Cicha taśma akrylowa – mocne sklejenie bez hałasu dyspensera"
        lead = "Hałas rozwijającej się taśmy w biurze lub magazynie potrafi być naprawdę uciążliwy. Wersja cicha eliminuje ten problem — zachowując całą wytrzymałość standardowego akrylu."
        zalety = (
            "<p><b>✅ Cicha praca</b> – odwija się bez zgrzytania – pracownicy mogą skupić się na pracy.</p>"
            "<p><b>✳️ Wytrzymałość akrylu</b> – mocne i trwałe sklejenie kartonów.</p>"
            "<p><b>⭐ Odporność na UV i temperaturę</b> – nie żółknie, trzyma latem jak zimą.</p>"
            "<p><b>🛡️ Rolka gotowa do pracy</b> – komfort codziennego użytku.</p>")
        li_extra = "<li>wszędzie tam, gdzie hałas dyspensera taśmy jest uciążliwy.</li>"
    elif t == "hot_melt":
        h1s = "✳️ Taśma hot-melt – błyskawiczne klejenie kauczukiem, wysoka przyczepność"
        lead = "Taśma hot-melt z klejem kauczukowym — wyjątkowo szybkie klejenie i duża siła przyczepności do kartonów."
        zalety = (
            "<p><b>✅ Błyskawiczne klejenie</b> – klej kauczukowy wiąże natychmiast po przyłożeniu.</p>"
            "<p><b>✳️ Mocna przyczepność</b> – utrzymuje szczelność nawet przy cięższych paczkach.</p>"
            "<p><b>⭐ Odporność na wilgoć i mróz</b> – nie traci właściwości w niskich temperaturach.</p>"
            "<p><b>🛡️ Rolka gotowa do pracy</b> – wysoka wydajność na dyspensera.</p>")
        li_extra = "<li>środowiskach z niższą temperaturą – magazyn chłodniczy, transport zimowy.</li>"
    elif t == "solvent":
        h1s = "✳️ Taśma solvent – najsilniejsze klejenie do wymagających warunków"
        lead = "Taśma solvent z klejem rozpuszczalnikowym — najsilniejsza klasa taśm pakowych, niezastąpiona tam, gdzie standardowy akryl zawodzi."
        zalety = (
            "<p><b>✅ Ekstremalnie mocna przyczepność</b> – najsilniejszy klej w klasie taśm pakowych.</p>"
            "<p><b>✳️ Odporność na trudne warunki</b> – trzyma na chropowatych i trudnych powierzchniach.</p>"
            "<p><b>⭐ Trwałość klejenia</b> – nie odkleją się nawet po dłuższym przechowywaniu.</p>"
            "<p><b>🛡️ Rolka gotowa do pracy</b> – wysoka wydajność na dyspensera.</p>")
        li_extra = "<li>aplikacjach wymagających najwyższej siły klejenia – ciężkie kartony, trudne powierzchnie.</li>"
    elif t == "nadruk":
        h1s = "✳️ Taśma z nadrukiem Ostrożnie Szkło – hot-melt, natychmiastowe klejenie"
        lead = "Taśma pakowa z czytelnym nadrukiem ostrzegawczym \"Ostrożnie szkło\" — klej hot-melt, natychmiastowe i mocne klejenie."
        zalety = (
            "<p><b>✅ Czytelny nadruk ostrzegawczy</b> – kurier i magazynier widzą, że paczka wymaga ostrożności.</p>"
            "<p><b>✳️ Klej hot-melt (kauczuk)</b> – natychmiastowe i mocne klejenie.</p>"
            "<p><b>⭐ Biała taśma z czerwonym nadrukiem</b> – wyraźnie widoczna na tle kartonu.</p>"
            "<p><b>🛡️ Rolka gotowa do pracy</b> – rzadziej wymieniasz rolkę.</p>")
        li_extra = "<li>wysyłkach zawierających szkło, ceramikę, elektronikę i inne kruche przedmioty.</li>"
    else:  # akryl
        h1s = "✳️ Taśma akrylowa – mocne klejenie, odporność na UV i temperaturę"
        lead = "Sprawdzona taśma akrylowa do pakowania kartonów — mocne i stabilne klejenie, niezawodna jakość w codziennej pracy."
        zalety = (
            "<p><b>✅ Mocne i stabilne klejenie</b> – paczka dotrze do klienta szczelna, bez ryzyka otwarcia.</p>"
            "<p><b>✳️ Odporność na UV i temperaturę</b> – nie żółknie, trzyma latem i zimą.</p>"
            "<p><b>⭐ Ekonomiczna cena</b> – dobry stosunek jakości do kosztów codziennego pakowania.</p>"
            "<p><b>🛡️ Rolka gotowa do pracy</b> – wygodna i wydajna.</p>")
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

for sku, catalog_id, title, dalpo_slug, price, stock, t in SKUS:
    print(f"\n{'='*55}")
    print(f"{sku} — {title[:50]}...")

    imgs = get_dalpo_images(dalpo_slug)
    if not imgs:
        print(f"  [SKIP] No images from Dalpo")
        results.append({"sku":sku,"status":"SKIP_NO_IMAGES","offer_id":None})
        continue
    print(f"  Images: {len(imgs)}")

    desc = build_description(title, t, imgs)

    # Opcja A: link do istniejącego produktu katalogowego przez ID
    payload = {
        "name": title,
        "category": {"id": CATEGORY_ID},
        "external": {"id": f"{sku}-1"},
        "productSet": [{
            "product": {"id": catalog_id},
            "quantity": {"value": 1},
            "responsibleProducer": {"id": RESPONSIBLE_PRODUCER_ID},
            "safetyInformation": {"description": SAFETY_TEXT, "type": "TEXT"},
            "marketedBeforeGPSRObligation": False,
        }],
        "images": imgs[:8],
        "description": desc,
        "parameters": [{"id":"11323","values":["Nowy"],"valuesIds":["11323_1"]}],
        "sellingMode": {"format":"BUY_NOW","price":{"amount":price,"currency":"PLN"}},
        "stock": {"available": 0, "unit": "UNIT"},
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
        print(f"  [OK ACTIVE] offer_id={new_id} | {price} PLN")
        client.patch(f"/sale/product-offers/{new_id}", json={"stock":{"available": stock}})
        print(f"  [OK] stock set to {stock}")
        results.append({"sku":sku,"status":"ACTIVE","offer_id":new_id,"price":price,"stock":stock})
    except AllegroAPIError as e:
        err_msg = str(e)
        print(f"  [ERR ACTIVE] {err_msg[:200]}")
        print(f"  Próbuję INACTIVE (szkic)...")

        payload["publication"] = {"status": "INACTIVE"}
        try:
            resp2 = client.post("/sale/product-offers", json=payload)
            new_id2 = resp2.get("id","?")
            print(f"  [OK INACTIVE/SZKIC] offer_id={new_id2} | {price} PLN")
            results.append({"sku":sku,"status":"INACTIVE","offer_id":new_id2,"price":price,"stock":stock,"active_error":err_msg[:200]})
        except AllegroAPIError as e2:
            err2 = str(e2)
            print(f"  [ERR INACTIVE] {err2[:200]}")
            print(f"  Próbuję bez productSet (sama oferta)...")

            # Ostatnia próba: oferta bez powiązania z produktem
            payload_no_product = {
                "name": title,
                "category": {"id": CATEGORY_ID},
                "external": {"id": f"{sku}-1"},
                "images": imgs[:8],
                "description": desc,
                "parameters": [{"id":"11323","values":["Nowy"],"valuesIds":["11323_1"]}],
                "sellingMode": {"format":"BUY_NOW","price":{"amount":price,"currency":"PLN"}},
                "stock": {"available": stock, "unit": "UNIT"},
                "publication": {"status": "INACTIVE"},
                "afterSalesServices": {
                    "impliedWarranty": {"id": WARRANTY_ID},
                    "returnPolicy": {"id": RETURN_POLICY_ID},
                },
                "delivery": {"shippingRates":{"id":SHIPPING_RATES_ID},"handlingTime":"PT24H"},
                "location": LOCATION,
                "payments": {"invoice": "VAT"},
            }
            try:
                resp3 = client.post("/sale/product-offers", json=payload_no_product)
                new_id3 = resp3.get("id","?")
                print(f"  [OK SZKIC BEZ PRODUKTU] offer_id={new_id3}")
                results.append({"sku":sku,"status":"INACTIVE_NO_PRODUCT","offer_id":new_id3,"price":price,"stock":stock})
            except AllegroAPIError as e3:
                print(f"  [FAIL] {str(e3)[:200]}")
                results.append({"sku":sku,"status":"FAIL","offer_id":None,"error":str(e3)[:300]})

    time.sleep(1.2)

print(f"\n{'='*55}")
print("WYNIKI:")
for r in results:
    print(f"  {r['sku']} | {r['status']} | {r.get('offer_id','—')} | {r.get('price','')} PLN")

with open("/Users/tomasz/Desktop/allegro-buypack/publish_blocked_a_results.json","w",encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print("\nZapisano do publish_blocked_a_results.json")
