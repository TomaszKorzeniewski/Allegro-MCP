#!/usr/bin/env python3
"""
Publish 7 remaining single-unit offers.
- TP/0019 always INACTIVE
- 422 EAN conflict → retry as INACTIVE
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

BOPP="236026_1647664"; BRAZ="10906_2"; BEZB="10906_1"; BIALY="10906_1121139"
AKR="10905_1"; HM="10905_1648206"; SOL="10905_1648207"
BRAK="249936_1784793"; OSTRZEG="249936_1784794"

# (sku, old_id, title, kolor_id, klej_id, sz, dl, EAN, dalpo_slug, price, nadruk_id, type, force_inactive)
SKUS = [
  ("TP/0001","18732779802",
   "Taśma Pakowa Brązowa Akrylowa 48mm/30m Klejąca do Pakowania Kartonów",
   BRAZ, AKR, 48, 30, "5905833094019",
   "brazowa-tasma-pakowa-akryl-basic-rozne-rozmiary", "4.92", BRAK, "akryl", False),
  ("TP/0002","18732779959",
   "Taśma Pakowa Transparentna Akrylowa 48mm/30m Klejąca Pakowanie Kartonów",
   BEZB, AKR, 48, 30, "5905833093982",
   "transparentna-tasma-pakowa-akryl-basic-rozne-rozmiary", "5.09", BRAK, "akryl", False),
  ("TP/0004","18732780118",
   "Taśma Pakowa Transparentna Akrylowa 48mm/45m Klejąca Pakowanie Kartonów",
   BEZB, AKR, 48, 45, "5905833094040",
   "transparentna-tasma-pakowa-akryl-basic-rozne-rozmiary", "5.90", BRAK, "akryl", False),
  ("TP/0007","18732780220",
   "Taśma Pakowa Brązowa Akrylowa Cicha 48mm/50m Klejąca do Kartonów Pakowanie",
   BRAZ, AKR, 48, 50, "5905833094125",
   "brazowa-tasma-pakowa-akryl-cicha-48mm-54m", "8.63", BRAK, "akryl_cichy", False),
  ("TP/0010","18732780421",
   "Taśma Pakowa Transparentna Hot-melt 48mm/45m Klejąca do Kartonów Pakowanie",
   BEZB, HM, 48, 45, "5905833092633",
   "transparentna-tasma-pakowa-hot-melt-rozne-rozmiary", "6.59", BRAK, "hot_melt", False),
  ("TP/0013","18732780636",
   "Taśma Pakowa Transparentna Solvent Mocna 48mm/45m Klejąca do Kartonów",
   BEZB, SOL, 48, 45, "5905833093876",
   "transparentna-tasma-pakowa-mocna-solvent-rozne-rozmiary", "5.93", BRAK, "solvent", False),
  ("TP/0019","18732780879",
   "Taśma z Nadrukiem Ostrożnie Szkło Hot-melt 48mm/45m Klejąca do Paczek",
   BIALY, HM, 48, 45, "5905833093227",
   "tasma-z-nadrukiem-ostroznie-szklo-48mm-x-45-m", "7.77", OSTRZEG, "nadruk", True),
]

def upload_images_to_allegro(urls):
    allegro_urls = []
    for url in urls[:8]:
        try:
            resp = client.post("/sale/images", json={"url": url})
            allegro_url = resp.get("location") or resp.get("url") or resp.get("src")
            if allegro_url:
                allegro_urls.append(allegro_url)
                print(f"    uploaded: {allegro_url[:60]}")
            else:
                print(f"    [WARN] no URL in response: {resp}")
        except AllegroAPIError as e:
            print(f"    [WARN] upload failed for {url[:50]}: {e}")
    return allegro_urls

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

def try_post(payload):
    return client.post("/sale/product-offers", json=payload)

results = []

for sku, old_id, title, kolor_id, klej_id, sz, dl, ean, dalpo_slug, price, nadruk_id, t, force_inactive in SKUS:
    print(f"\n{'='*55}")
    print(f"{sku} — {title[:50]}...")

    # Delete old offer
    try:
        client.delete(f"/sale/offers/{old_id}")
        print(f"  Deleted old offer {old_id}")
    except AllegroAPIError as e:
        print(f"  [WARN] delete: {e}")

    time.sleep(0.5)

    imgs = get_dalpo_images(dalpo_slug)
    if not imgs:
        print(f"  [SKIP] No images")
        results.append({"sku":sku,"status":"SKIP_NO_IMAGES","offer_id":None})
        continue
    print(f"  Images: {len(imgs)}")

    desc = build_description(title, dl, t, imgs)

    status = "INACTIVE" if force_inactive else "ACTIVE"

    # Build payload for /sale/product-offers (primary attempt)
    product_payload = {
        "name": title,
        "category": {"id": CATEGORY_ID},
        "external": {"id": f"{sku}-1"},
        "productSet": [{
            "product": {
                "name": title,
                "category": {"id": CATEGORY_ID},
                "images": imgs[:4],
                "parameters": [
                    {"id":"248811","valuesIds":["248811_1131943"]},
                    {"id":"236026","valuesIds":[BOPP]},
                    {"id":"10906", "valuesIds":[kolor_id]},
                    {"id":"10905", "valuesIds":[klej_id]},
                    {"id":"227381","values":[str(sz)]},
                    {"id":"203949","values":[str(dl)]},
                    {"id":"233101","values":["1"]},
                    {"id":"225693","values":[ean]},
                    {"id":"249936","valuesIds":[nadruk_id]},
                    {"id":"17448", "values":["0.1"]},
                    {"id":"250792","values":["39211900"]},
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
        "stock": {"available":0,"unit":"UNIT"},
        "publication": {"status": status},
        "afterSalesServices": {
            "impliedWarranty": {"id": WARRANTY_ID},
            "returnPolicy": {"id": RETURN_POLICY_ID},
        },
        "delivery": {"shippingRates":{"id":SHIPPING_RATES_ID},"handlingTime":"PT24H"},
        "location": LOCATION,
        "payments": {"invoice": "VAT"},
    }

    # Legacy /sale/offers payload (no productSet, EAN at offer level)
    legacy_payload = {
        "name": title,
        "category": {"id": CATEGORY_ID},
        "external": {"id": f"{sku}-1"},
        "images": [{"url": u} for u in imgs[:8]],
        "description": desc,
        "parameters": [
            {"id":"11323","values":["Nowy"],"valuesIds":["11323_1"]},
            {"id":"248811","valuesIds":["248811_1131943"]},
            {"id":"236026","valuesIds":[BOPP]},
            {"id":"10906", "valuesIds":[kolor_id]},
            {"id":"10905", "valuesIds":[klej_id]},
            {"id":"227381","values":[str(sz)]},
            {"id":"203949","values":[str(dl)]},
            {"id":"233101","values":["1"]},
            {"id":"225693","values":[ean]},
            {"id":"249936","valuesIds":[nadruk_id]},
            {"id":"17448", "values":["0.1"]},
            {"id":"250792","values":["39211900"]},
        ],
        "sellingMode": {"format":"BUY_NOW","price":{"amount":price,"currency":"PLN"}},
        "stock": {"available":9999,"unit":"UNIT"},
        "publication": {"status": status},
        "afterSalesServices": {
            "impliedWarranty": {"id": WARRANTY_ID},
            "returnPolicy": {"id": RETURN_POLICY_ID},
        },
        "delivery": {"shippingRates":{"id":SHIPPING_RATES_ID},"handlingTime":"PT24H"},
        "location": LOCATION,
        "payments": {"invoice": "VAT"},
    }

    def patch_stock(offer_id):
        client.patch(f"/sale/product-offers/{offer_id}", json={"stock":{"available": 9999}})

    posted = False

    # 1st attempt: product-offers with ACTIVE/INACTIVE
    try:
        resp = try_post(product_payload)
        new_id = resp.get("id","?")
        prod_id = None
        for ps in resp.get("productSet",[]):
            prod_id = (ps.get("product") or {}).get("id")
        print(f"  [OK] product-offers: {new_id} | product: {prod_id} | {price} PLN | {status}")
        patch_stock(new_id)
        results.append({"sku":sku,"status":status,"offer_id":new_id,"price":price})
        posted = True
    except AllegroAPIError as e:
        err_str = str(e)
        print(f"  [422-productoffers] {err_str[:100]}")

    # 2nd attempt: product-offers INACTIVE (if not already inactive)
    if not posted and not force_inactive:
        try:
            product_payload["publication"]["status"] = "INACTIVE"
            resp = try_post(product_payload)
            new_id = resp.get("id","?")
            print(f"  [OK] product-offers INACTIVE: {new_id} | {price} PLN")
            patch_stock(new_id)
            results.append({"sku":sku,"status":"INACTIVE","offer_id":new_id,"price":price})
            posted = True
        except AllegroAPIError as e2:
            print(f"  [422-inactive] {str(e2)[:100]}")

    # 3rd attempt: legacy /sale/offers (upload images to Allegro first)
    if not posted:
        print(f"  Uploading images to Allegro...")
        allegro_imgs = upload_images_to_allegro(imgs)
        if allegro_imgs:
            legacy_payload["images"] = [{"url": u} for u in allegro_imgs]
            # Rebuild description with Allegro-hosted URLs so gallery matches description
            legacy_payload["description"] = build_description(title, dl, t, allegro_imgs)
        try:
            resp = client.post("/sale/offers", json=legacy_payload)
            new_id = resp.get("id","?")
            final_status = legacy_payload["publication"]["status"]
            print(f"  [OK] legacy /sale/offers: {new_id} | {price} PLN | {final_status}")
            results.append({"sku":sku,"status":final_status,"offer_id":new_id,"price":price,"via":"legacy"})
            posted = True
        except AllegroAPIError as e3:
            err3 = str(e3)
            print(f"  [ERR-legacy] {err3[:200]}")
            results.append({"sku":sku,"status":"ERROR","offer_id":None,"error":err3[:200]})

    time.sleep(1)

print(f"\n{'='*55}")
print("RESULTS:")
for r in results:
    print(f"  {r['sku']} | {r['status']} | {r.get('offer_id','')} | {r.get('price','')} PLN")

with open("/Users/tomasz/Desktop/allegro-buypack/publish_remaining_results.json","w",encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print("Saved to publish_remaining_results.json")
