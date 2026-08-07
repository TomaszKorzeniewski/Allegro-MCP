"""Budowanie opisu oferty w formacie sekcji Allegro.

Do 2026-08-07 ta sama funkcja istniała w pięciu kopiach (create_single_offers,
fix_and_drafts, publish_blocked_a, publish_remaining, publish_singles), które
zdążyły się już drobno rozjechać w treści marketingowej. Źródłem tej wersji jest
`publish_singles.py`, bo jej wynik przeszedł walidację Allegro na produkcji.

Struktura opisu to pięć sekcji wymaganych przez szablon konta:
nagłówek, wprowadzenie ze zdjęciem, zalety, zastosowania, zdjęcie zamykające.

Pułapki HTML, zweryfikowane na produkcji:
    <b> przechodzi, <strong> zwraca 422.
    Dozwolone: h1, h2, p, ul, li, b.
    IMAGE w sekcji to obiekt {"type": "IMAGE", "url": ...},
    ale `images` oferty to zwykłe stringi.
"""

from typing import Sequence

# Warianty kleju obsługiwane przez generator. Klucz trafia do `build_description`.
WARIANTY = ("akryl", "akryl_cichy", "hot_melt", "solvent", "nadruk")


def _tresc_wariantu(wariant: str, dlugosc: int) -> tuple[str, str, str, str]:
    """Zwraca (nagłówek, wprowadzenie, zalety, dodatkowe zastosowanie)."""
    if wariant == "akryl_cichy":
        return (
            "✳️ Cicha taśma akrylowa – mocne sklejenie bez hałasu dyspensera",
            "Hałas rozwijającej się taśmy w biurze lub magazynie potrafi być naprawdę "
            "uciążliwy. Wersja cicha eliminuje ten problem — zachowując całą "
            "wytrzymałość standardowego akrylu.",
            "<p><b>✅ Cicha praca</b> – odwija się bez zgrzytania – pracownicy mogą skupić się na pracy.</p>"
            "<p><b>✳️ Wytrzymałość akrylu</b> – mocne i trwałe sklejenie kartonów.</p>"
            "<p><b>⭐ Odporność na UV i temperaturę</b> – nie żółknie, trzyma latem jak zimą.</p>"
            f"<p><b>🛡️ Długość {dlugosc}m na rolce</b> – rzadziej wymieniasz rolkę, mniej przestojów.</p>",
            "<li>wszędzie tam, gdzie hałas dyspensera taśmy jest uciążliwy.</li>",
        )
    if wariant == "hot_melt":
        return (
            "✳️ Taśma hot-melt – błyskawiczne klejenie kauczukiem, wysoka przyczepność",
            "Taśma hot-melt z klejem kauczukowym — wyjątkowo szybkie klejenie i duża "
            "siła przyczepności do kartonów.",
            "<p><b>✅ Błyskawiczne klejenie</b> – klej kauczukowy wiąże natychmiast po przyłożeniu.</p>"
            "<p><b>✳️ Mocna przyczepność</b> – utrzymuje szczelność nawet przy cięższych paczkach.</p>"
            "<p><b>⭐ Odporność na wilgoć i mróz</b> – nie traci właściwości w niskich temperaturach.</p>"
            f"<p><b>🛡️ Długość {dlugosc}m na rolce</b> – rzadziej wymieniasz rolkę, mniej przestojów.</p>",
            "<li>środowiskach z niższą temperaturą – magazyn chłodniczy, transport zimowy.</li>",
        )
    if wariant == "solvent":
        return (
            "✳️ Taśma solvent – najsilniejsze klejenie do wymagających warunków",
            "Taśma solvent z klejem rozpuszczalnikowym — najsilniejsza klasa taśm "
            "pakowych, niezastąpiona tam, gdzie standardowy akryl zawodzi.",
            "<p><b>✅ Ekstremalnie mocna przyczepność</b> – najsilniejszy klej w klasie taśm pakowych.</p>"
            "<p><b>✳️ Odporność na trudne warunki</b> – trzyma na chropowatych i trudnych powierzchniach.</p>"
            "<p><b>⭐ Trwałość klejenia</b> – nie odkleją się nawet po dłuższym przechowywaniu.</p>"
            f"<p><b>🛡️ Długość {dlugosc}m na rolce</b> – rzadziej wymieniasz rolkę, mniej przestojów.</p>",
            "<li>aplikacjach wymagających najwyższej siły klejenia – ciężkie kartony, trudne powierzchnie.</li>",
        )
    if wariant == "nadruk":
        return (
            "✳️ Taśma z nadrukiem Ostrożnie Szkło – hot-melt, natychmiastowe klejenie",
            'Taśma pakowa z czytelnym nadrukiem ostrzegawczym "Ostrożnie szkło" — '
            "klej hot-melt, natychmiastowe i mocne klejenie.",
            "<p><b>✅ Czytelny nadruk ostrzegawczy</b> – kurier i magazynier widzą, że paczka wymaga ostrożności.</p>"
            "<p><b>✳️ Klej hot-melt (kauczuk)</b> – natychmiastowe i mocne klejenie.</p>"
            "<p><b>⭐ Biała taśma z czerwonym nadrukiem</b> – wyraźnie widoczna na tle kartonu.</p>"
            f"<p><b>🛡️ Długość {dlugosc}m na rolce</b> – rzadziej wymieniasz rolkę.</p>",
            "<li>wysyłkach zawierających szkło, ceramikę, elektronikę i inne kruche przedmioty.</li>",
        )
    # Domyślnie: zwykły akryl.
    return (
        "✳️ Taśma akrylowa – mocne klejenie, odporność na UV i temperaturę",
        "Sprawdzona taśma akrylowa do pakowania kartonów — mocne i stabilne "
        "klejenie, niezawodna jakość w codziennej pracy.",
        "<p><b>✅ Mocne i stabilne klejenie</b> – paczka dotrze do klienta szczelna, bez ryzyka otwarcia.</p>"
        "<p><b>✳️ Odporność na UV i temperaturę</b> – nie żółknie, trzyma latem i zimą.</p>"
        "<p><b>⭐ Ekonomiczna cena</b> – dobry stosunek jakości do kosztów codziennego pakowania.</p>"
        f"<p><b>🛡️ Długość {dlugosc}m na rolce</b> – rzadziej wymieniasz rolkę, mniej przestojów.</p>",
        "",
    )


def build_description(
    tytul: str, dlugosc: int, wariant: str, zdjecia: Sequence[str]
) -> dict:
    """Składa opis oferty z pięciu sekcji.

    `zdjecia` to lista URL-i; gdy jest ich mniej niż cztery, ostatnie się powtarza,
    bo Allegro wymaga obrazu w każdej sekcji, która go deklaruje.
    """
    if not zdjecia:
        raise ValueError("Opis wymaga co najmniej jednego zdjęcia.")

    n = len(zdjecia)
    i1 = zdjecia[0]
    i2 = zdjecia[min(1, n - 1)]
    i3 = zdjecia[min(2, n - 1)]
    i4 = zdjecia[min(3, n - 1)]

    naglowek, wprowadzenie, zalety, zastosowanie_extra = _tresc_wariantu(
        wariant, dlugosc
    )

    return {
        "sections": [
            {"items": [{"type": "TEXT", "content": f"<h1>✳️ {tytul}</h1>"}]},
            {
                "items": [
                    {"type": "IMAGE", "url": i1},
                    {
                        "type": "TEXT",
                        "content": f"<h1>{naglowek}</h1><p>{wprowadzenie}</p>",
                    },
                ]
            },
            {
                "items": [
                    {"type": "IMAGE", "url": i2},
                    {
                        "type": "TEXT",
                        "content": f"<h1>✳️ Zalety i właściwości</h1>{zalety}",
                    },
                ]
            },
            {
                "items": [
                    {"type": "IMAGE", "url": i3},
                    {
                        "type": "TEXT",
                        "content": (
                            "<h1>✳️ Do czego się przyda?</h1>"
                            "<p><b>➡️ Sprawdzi się przy:</b></p><ul>"
                            "<li>pakowaniu kartonów i przesyłek kurierskich,</li>"
                            "<li>wysyłkach na dużą skalę – magazyn, sklep internetowy, praca zmianowa,</li>"
                            f"{zastosowanie_extra}</ul>"
                            "<p>⚠️ Taśma przeznaczona wyłącznie do pakowania. "
                            "Nie stosować do instalacji elektrycznych ani hydraulicznych.</p>"
                            "<h2>✔️ Sprzedajemy hurtowo – sprawdź nasze zestawy 6 i 36 rolek "
                            "w obniżonej cenie.</h2>"
                        ),
                    },
                ]
            },
            {"items": [{"type": "IMAGE", "url": i4}]},
        ]
    }
