#!/usr/bin/env python3
"""
Dwie operacje:
1. PATCH opisu 5 ofert ACTIVE z dzisiaj — dodanie specyfikacji do sekcji 2
2. Tworzenie 6 szkiców INACTIVE bez EAN (TP/0006, 0015–0018, 0030)
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

def get_dalpo_images(slug):
    try:
        r = requests.get(f"https://sklep.dalpo.pl/products/{slug}.json",
                         headers={"User-Agent":"Mozilla/5.0"}, timeout=15)
        return [img["src"] for img in r.json()["product"]["images"] if img.get("src")]
    except Exception as e:
        print(f"  [WARN] images fetch failed: {e}")
        return []

def spec_text(sz, dl, kolor, klej, material="BOPP"):
    return (
        f"<h1>⚙️ Specyfikacja produktu</h1>"
        f"<p><b>📦 Szerokość:</b> {sz} mm</p>"
        f"<p><b>📏 Długość:</b> {dl} m</p>"
        f"<p><b>🎨 Kolor:</b> {kolor}</p>"
        f"<p><b>🧪 Rodzaj kleju:</b> {klej}</p>"
        f"<p><b>🏭 Materiał nośnika:</b> {material}</p>"
        f"<p><b>🔹 Wariant:</b> 1 rolka (sztuka)</p>"
    )

def build_description(title, t, imgs, sz, dl, kolor, klej, material="BOPP"):
    n = len(imgs)
    i1 = imgs[0]; i2 = imgs[min(1,n-1)]; i3 = imgs[min(2,n-1)]; i4 = imgs[min(3,n-1)]

    if t == "akryl_cichy":
        h1s = "✳️ Cicha taśma akrylowa – mocne sklejenie bez hałasu dyspensera"
        zalety = (
            "<p><b>✅ Cicha praca</b> – odwija się bez zgrzytania – pracownicy mogą skupić się na pracy.</p>"
            "<p><b>✳️ Wytrzymałość akrylu</b> – mocne i trwałe sklejenie kartonów.</p>"
            "<p><b>⭐ Odporność na UV i temperaturę</b> – nie żółknie, trzyma latem jak zimą.</p>"
            "<p><b>🛡️ Gotowa do pracy</b> – wygodna rolka na dyspenserze.</p>")
        li_extra = "<li>wszędzie tam, gdzie hałas dyspensera taśmy jest uciążliwy.</li>"
    elif t == "hot_melt":
        h1s = "✳️ Taśma hot-melt – błyskawiczne klejenie kauczukiem, wysoka przyczepność"
        zalety = (
            "<p><b>✅ Błyskawiczne klejenie</b> – klej kauczukowy wiąże natychmiast po przyłożeniu.</p>"
            "<p><b>✳️ Mocna przyczepność</b> – utrzymuje szczelność nawet przy cięższych paczkach.</p>"
            "<p><b>⭐ Odporność na wilgoć i mróz</b> – nie traci właściwości w niskich temperaturach.</p>"
            "<p><b>🛡️ Gotowa do pracy</b> – wysoka wydajność na dyspensera.</p>")
        li_extra = "<li>środowiskach z niższą temperaturą – magazyn chłodniczy, transport zimowy.</li>"
    elif t == "solvent":
        h1s = "✳️ Taśma solvent – najsilniejsze klejenie do wymagających warunków"
        zalety = (
            "<p><b>✅ Ekstremalnie mocna przyczepność</b> – najsilniejszy klej w klasie taśm pakowych.</p>"
            "<p><b>✳️ Odporność na trudne warunki</b> – trzyma na chropowatych i trudnych powierzchniach.</p>"
            "<p><b>⭐ Trwałość klejenia</b> – nie odkleją się nawet po dłuższym przechowywaniu.</p>"
            "<p><b>🛡️ Gotowa do pracy</b> – wysoka wydajność na dyspensera.</p>")
        li_extra = "<li>aplikacjach wymagających najwyższej siły klejenia – ciężkie kartony, trudne powierzchnie.</li>"
    elif t == "strong":
        h1s = "✳️ Taśma Strong – wzmocnione klejenie do trudnych kartonów i intensywnej pracy"
        zalety = (
            "<p><b>✅ Wzmocniona przyczepność</b> – mocniejsza niż standardowy akryl, pewne sklejenie ciężkich kartonów.</p>"
            "<p><b>✳️ Odporność na naprężenia</b> – taśma nie pęka przy rozciąganiu podczas pakowania.</p>"
            "<p><b>⭐ Dobra przyczepność w różnych temperaturach</b> – sprawdzi się w magazynie i transporcie.</p>"
            "<p><b>🛡️ Gotowa do pracy</b> – wygodna rolka na dyspenserze.</p>")
        li_extra = "<li>pakowaniu ciężkich i dużych kartonów wymagających mocniejszego kleju.</li>"
    elif t == "papierowa":
        h1s = "✳️ Taśma papierowa kraft – ekologiczne pakowanie, mocne klejenie hot-melt"
        zalety = (
            "<p><b>✅ Ekologiczna i biodegradowalna</b> – papierowa alternatywa dla folii plastikowej.</p>"
            "<p><b>✳️ Klej hot-melt</b> – mocne i natychmiastowe klejenie na kartonach.</p>"
            "<p><b>⭐ Estetyczny wygląd</b> – brązowy kraft pasuje do opakowań eco i premium.</p>"
            "<p><b>🛡️ Gotowa do pracy</b> – sprawdzi się na dyspenserze do taśmy papierowej.</p>")
        li_extra = "<li>sklepach i markach z filozofią eco/zero waste.</li>"
    else:  # akryl
        h1s = "✳️ Taśma akrylowa – mocne klejenie, odporność na UV i temperaturę"
        zalety = (
            "<p><b>✅ Mocne i stabilne klejenie</b> – paczka dotrze do klienta szczelna, bez ryzyka otwarcia.</p>"
            "<p><b>✳️ Odporność na UV i temperaturę</b> – nie żółknie, trzyma latem i zimą.</p>"
            "<p><b>⭐ Ekonomiczna cena</b> – dobry stosunek jakości do kosztów codziennego pakowania.</p>"
            "<p><b>🛡️ Gotowa do pracy</b> – wygodna rolka na dyspenserze.</p>")
        li_extra = ""

    return {"sections": [
        {"items": [{"type":"TEXT","content":f"<h1>✳️ {title}</h1>"}]},
        {"items": [
            {"type":"IMAGE","url":i1},
            {"type":"TEXT","content": spec_text(sz, dl, kolor, klej, material)},
        ]},
        {"items": [
            {"type":"IMAGE","url":i2},
            {"type":"TEXT","content":f"<h1>{h1s}</h1>{zalety}"},
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


# ─── CZĘŚĆ 1: PATCH 5 ACTIVE — dodanie specyfikacji do sekcji 2 ─────────────

print("="*60)
print("CZĘŚĆ 1 — PATCH: dodanie specyfikacji do sekcji 2")
print("="*60)

ACTIVE_TO_FIX = [
    # (offer_id, sku, title, dalpo_slug, sz, dl, kolor, klej, t)
    ("18734683348", "TP/0001",
     "Taśma Pakowa Brązowa Akrylowa 48mm/30m Klejąca do Pakowania Kartonów",
     "brazowa-tasma-pakowa-akryl-basic-rozne-rozmiary",
     48, 30, "Brązowa", "Akrylowy", "akryl"),
    ("18734683435", "TP/0002",
     "Taśma Pakowa Transparentna Akrylowa 48mm/30m Klejąca Pakowanie Kartonów",
     "transparentna-tasma-pakowa-akryl-basic-rozne-rozmiary",
     48, 30, "Transparentna", "Akrylowy", "akryl"),
    ("18734683580", "TP/0007",
     "Taśma Pakowa Brązowa Akrylowa Cicha 48mm/50m Klejąca do Kartonów Pakowanie",
     "brazowa-tasma-pakowa-akryl-cicha-48mm-54m",
     48, 50, "Brązowa", "Akrylowy (wytłumiony)", "akryl_cichy"),
    ("18734683657", "TP/0010",
     "Taśma Pakowa Transparentna Hot-melt 48mm/45m Klejąca do Kartonów Pakowanie",
     "transparentna-tasma-pakowa-hot-melt-rozne-rozmiary",
     48, 45, "Transparentna", "Hot-melt (kauczuk)", "hot_melt"),
    ("18734683710", "TP/0013",
     "Taśma Pakowa Transparentna Solvent Mocna 48mm/45m Klejąca do Kartonów",
     "transparentna-tasma-pakowa-mocna-solvent-rozne-rozmiary",
     48, 45, "Transparentna", "Solvent (rozpuszczalnikowy)", "solvent"),
]

fix_results = []
for offer_id, sku, title, slug, sz, dl, kolor, klej, t in ACTIVE_TO_FIX:
    print(f"\n{sku} (offer {offer_id})")
    imgs = get_dalpo_images(slug)
    if not imgs:
        print(f"  [SKIP] brak zdjęć")
        fix_results.append({"sku":sku,"offer_id":offer_id,"status":"SKIP_NO_IMAGES"})
        continue
    desc = build_description(title, t, imgs, sz, dl, kolor, klej)
    try:
        client.patch(f"/sale/product-offers/{offer_id}", json={"description": desc})
        print(f"  [OK] Sekcja 2 zaktualizowana")
        fix_results.append({"sku":sku,"offer_id":offer_id,"status":"PATCHED"})
    except AllegroAPIError as e:
        print(f"  [ERR] {str(e)[:150]}")
        fix_results.append({"sku":sku,"offer_id":offer_id,"status":"ERROR","error":str(e)[:200]})
    time.sleep(1)


# ─── CZĘŚĆ 2: 6 NOWYCH SZKICÓW INACTIVE ─────────────────────────────────────

print("\n" + "="*60)
print("CZĘŚĆ 2 — TWORZENIE 6 SZKICÓW INACTIVE")
print("="*60)

# (sku, title_seo, dalpo_slug, price, stock, sz, dl, kolor, klej, material, t)
NEW_DRAFTS = [
    ("TP/0006",
     "Taśma Pakowa Transparentna Akrylowa 48mm/60m Klejąca do Kartonów Pakowanie",
     "transparentna-tasma-pakowa-akryl-basic-rozne-rozmiary",
     "7.36", 0, 48, 60, "Transparentna", "Akrylowy", "BOPP", "akryl"),
    ("TP/0015",
     "Taśma Pakowa Transparentna Strong Wzmocniona 48mm/45m Klejąca do Kartonów",
     "transparentna-tasma-pakowa-hot-melt-rozne-rozmiary",
     "7.48", 0, 48, 45, "Transparentna", "Wzmocniony", "BOPP", "strong"),
    ("TP/0016",
     "Taśma Pakowa Transparentna Strong Wzmocniona 48mm/60m Klejąca do Kartonów",
     "transparentna-tasma-pakowa-hot-melt-rozne-rozmiary",
     "9.96", 0, 48, 60, "Transparentna", "Wzmocniony", "BOPP", "strong"),
    ("TP/0017",
     "Taśma Pakowa Transparentna Strong Wzmocniona 48mm/132m Klejąca Kartonów",
     "transparentna-tasma-pakowa-hot-melt-rozne-rozmiary",
     "12.10", 0, 48, 132, "Transparentna", "Wzmocniony", "BOPP", "strong"),
    ("TP/0018",
     "Taśma Pakowa Brązowa Strong Wzmocniona 48mm/132m Klejąca do Kartonów",
     "brazowa-tasma-pakowa-mocna-solvent-rozne-rozmiary",
     "12.10", 0, 48, 132, "Brązowa", "Wzmocniony", "BOPP", "strong"),
    ("TP/0030",
     "Taśma Pakowa Papierowa Kraft Hot-melt Brązowa 50mm/40m do Pakowania Kartonów",
     "tasma-papierowa-pakowa-hot-melt-kraft-48-mm-x-50-m",
     "11.96", 884, 50, 40, "Brązowa (kraft)", "Hot-melt", "Papierowa kraft", "papierowa"),
]

draft_results = []
for sku, title, slug, price, stock, sz, dl, kolor, klej, material, t in NEW_DRAFTS:
    print(f"\n{sku} — {title[:55]}...")
    imgs = get_dalpo_images(slug)
    if not imgs:
        print(f"  [SKIP] brak zdjęć")
        draft_results.append({"sku":sku,"status":"SKIP_NO_IMAGES","offer_id":None})
        continue
    print(f"  Images: {len(imgs)}")
    desc = build_description(title, t, imgs, sz, dl, kolor, klej, material)

    payload = {
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
        resp = client.post("/sale/product-offers", json=payload)
        new_id = resp.get("id","?")
        print(f"  [OK INACTIVE/SZKIC] offer_id={new_id} | {price} PLN")
        draft_results.append({"sku":sku,"status":"INACTIVE","offer_id":new_id,"price":price})
    except AllegroAPIError as e:
        print(f"  [ERR] {str(e)[:200]}")
        draft_results.append({"sku":sku,"status":"ERROR","offer_id":None,"error":str(e)[:300]})
    time.sleep(1.2)

# ─── PODSUMOWANIE ─────────────────────────────────────────────────────────────

print("\n" + "="*60)
print("CZĘŚĆ 1 — PATCHE:")
for r in fix_results:
    print(f"  {r['sku']} | {r['status']} | {r['offer_id']}")

print("\nCZĘŚĆ 2 — SZKICE:")
for r in draft_results:
    print(f"  {r['sku']} | {r['status']} | {r.get('offer_id','—')} | {r.get('price','')} PLN")

all_results = {"fix": fix_results, "drafts": draft_results}
with open("/Users/tomasz/Desktop/allegro-buypack/fix_and_drafts_results.json","w",encoding="utf-8") as f:
    json.dump(all_results, f, ensure_ascii=False, indent=2)
print("\nZapisano do fix_and_drafts_results.json")
