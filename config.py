"""Stałe konta buy-pack: identyfikatory, lokalizacja, teksty wymagane przez API.

Do 2026-08-07 te same wartości siedziały skopiowane w siedmiu skryptach naraz
(publish_singles, publish_remaining, publish_blocked_a, fix_and_drafts,
create_single_offers, create_zestawy, recreate_detached). Rozjazd między kopiami
oznaczał ofertę wystawioną na złych warunkach zwrotu albo złym cenniku dostawy,
więc źródło jest teraz jedno.

Wartości pochodzą z konta produkcyjnego. Sprawdzisz je narzędziami MCP:
cenniki przez `list_shipping_rates`, warunki zwrotów i gwarancji przez
`get_sale_settings`.
"""

# --- Identyfikatory konta (produkcja) --------------------------------------
# Podmiot odpowiedzialny za produkt w rozumieniu GPSR.
RESPONSIBLE_PRODUCER_ID = "a0e7065b-d173-4b9c-8de6-37dd0535899b"
# Warunki reklamacji (rękojmia) przypisywane nowym ofertom.
WARRANTY_ID = "c6bd41ce-bc1c-41a6-be3c-651dd035dc43"
# Polityka zwrotów przypisywana nowym ofertom.
RETURN_POLICY_ID = "3af930f6-631c-420f-ab59-23582f9288ff"

# --- Cenniki dostawy --------------------------------------------------------
# Uwaga: cennik decyduje o tym, jakie metody dostawy widzi kupujący. Zły cennik
# to realny problem gabarytowy (karton 140 cm dopuszczony do paczkomatu 64 cm),
# dlatego zestawy mają własny cennik, inny niż sztuki pojedyncze.
SHIPPING_RATES_ID = "fcf29f15-4038-4046-be17-f047d8f56f89"  # "taśma pojedyncza"
ZESTAW_SHIPPING_ID = "98c51ddb-13d6-419f-94cb-57c68bd8f8b7"  # "taśmy pakowe 6 szt"

# --- Miejsce wysyłki i kategoria -------------------------------------------
LOCATION = {
    "countryCode": "PL",
    "province": "SLASKIE",
    "city": "Cieszyn",
    "postCode": "43-400",
}
CATEGORY_ID = "64541"  # Taśmy pakowe

# Czas wysyłki w formacie ISO 8601 (PT24H = 24 godziny).
HANDLING_TIME = "PT24H"

# --- Parametry katalogowe Allegro ------------------------------------------
# Identyfikatory wartości słownikowych. Nazwa parametru jest po lewej, bo samo
# "236026_1647664" nie mówi nic przy czytaniu payloadu.
MATERIAL_BOPP = "236026_1647664"
KOLOR_BRAZOWY = "10906_2"
KOLOR_BEZBARWNY = "10906_1"
KOLOR_BIALY = "10906_1121139"
KLEJ_AKRYL = "10905_1"
KLEJ_HOT_MELT = "10905_1648206"
KLEJ_SOLVENT = "10905_1648207"
NADRUK_BRAK = "249936_1784793"
NADRUK_OSTRZEGAWCZY = "249936_1784794"

# Identyfikatory samych parametrów (klucze w payloadzie product.parameters).
PARAM_MARKA = "248811"
PARAM_MARKA_DALPO = "248811_1131943"
PARAM_MATERIAL = "236026"
PARAM_KOLOR = "10906"
PARAM_KLEJ = "10905"
PARAM_SZEROKOSC = "227381"
PARAM_DLUGOSC = "203949"
PARAM_LICZBA_SZTUK = "233101"
PARAM_EAN = "225693"
PARAM_NADRUK = "249936"
PARAM_WAGA = "17448"
PARAM_KOD_TARYFY = "250792"
PARAM_STAN = "11323"  # stan opakowania, zawsze "Nowy"

KOD_TARYFY_CELNEJ = "39211900"

# --- GPSR -------------------------------------------------------------------
# Tekst wymagany rozporządzeniem (UE) 2023/988. Allegro przyjmuje go po angielsku
# i tak został zatwierdzony na koncie, więc nie tłumaczymy go na polski.
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

# --- Ograniczenia API (zweryfikowane na produkcji) --------------------------
# <strong> zwraca 422, <b> przechodzi. Reszta dozwolonych: h1, h2, p, ul, li.
HTML_DOZWOLONY = ("h1", "h2", "p", "ul", "li", "b")

# Allegro tnie nazwę oferty powyżej tego limitu.
MAX_DLUGOSC_NAZWY = 75

# Źródło zdjęć produktowych (sklep dostawcy, Shopify JSON).
DALPO_PRODUCT_URL = "https://sklep.dalpo.pl/products/{slug}.json"
