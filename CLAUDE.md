# Allegro Buy-Pack MCP — instrukcje dla Claude

Serwer MCP (FastMCP, 26 narzędzi) do konta Allegro **buy-pack**, produkcja.
Tokeny w `.env` (w `.gitignore`, odświeżanie automatyczne).
Źródło prawdy o stronie biznesowej: vault Obsidian
`Allegro Buy-Pack/MASTER — Allegro Buy-Pack.md`.

## Układ projektu

| Miejsce | Co |
|---|---|
| `server.py` | Narzędzia MCP, cienka warstwa nad modułami niżej |
| `allegro_client.py` | HTTP: ponawianie, paginacja, rozpoznawanie błędów Allegro |
| `auth.py` | OAuth device flow, rotacja tokenów pod blokadą pliku |
| `config.py` | Identyfikatory konta, lokalizacja, tekst GPSR |
| `offers.py` | Payload oferty, zestawy, odtwarzanie odpiętych ofert |
| `descriptions.py` | Generator opisu (5 sekcji) |
| `skrypty/` | Przebiegi jednorazowe z kolejnych sesji, zapis tego, co realnie poszło |
| `wyniki/` | Wyniki tych przebiegów, ślad audytowy |
| `tests/` | `pytest` (bez dotykania produkcji) |

⚠️ **Skrypty w `skrypty/` wykonują operacje przy samym imporcie.** Część z nich
wystawia oferty na produkcji od razu po uruchomieniu. Nie odpalaj ich, żeby
„sprawdzić, czy działają". Do sprawdzenia jest `pytest`.

## Pułapki API (zweryfikowane na produkcji)

- **Refresh token rotuje jednorazowo.** Dwa procesy odświeżające naraz
  unieważniają autoryzację. Rozwiązane blokadą `.env.lock` w `auth.py`,
  ale nie obchodź jej własnym kodem czytającym `.env`.
- **POST /sale/product-offers zwraca 202 i to jest SUKCES** (operacja
  asynchroniczna). Skrypt traktujący 202 jako błąd gubi utworzone oferty.
- **Kategoria 64541 odbija ręcznie budowany `productSet` błędem 422.**
  Zestawy powstają przez skopiowanie karty produktu z żywej oferty
  (`create_offer_set`), nie przez budowanie od zera.
- **`InProgressTaskLimitReachedException` znaczy „czekaj i ponów", nie „popsute".**
  Allegro kolejkuje zmiany statusu; świeża oferta potrafi wisieć jako INACTIVE
  kilkadziesiąt minut. Licząc stany, pobieraj ACTIVE **i** INACTIVE.
- **PRODUCT_DETACHMENT**: gdy Allegro scali kartę produktu, kończy ofertę
  i nie da się jej wznowić. Od tego jest `recreate_detached_offer`.
- **HTML w opisach**: `<b>` przechodzi, `<strong>` zwraca 422.
  Dozwolone: h1, h2, p, ul, li, b.
- **Zdjęcia**: w `images` zwykłe stringi; obiekt `{"url": ...}` to format legacy.
  W sekcjach opisu odwrotnie: `{"type": "IMAGE", "url": ...}`.
- **GPSR** (`responsibleProducer`, `safetyInformation`,
  `marketedBeforeGPSRObligation`) siedzi **wewnątrz** elementu `productSet`.
  Na najwyższym poziomie zwraca 422 UnknownJSONProperty.
- **`productSet[].quantity` to samo `{"value": N}`**, bez `unit`.
- **Ceny w API są brutto.**
- **Marża netto nie istnieje w API.** Uzupełniasz ręcznie w Seller Center.
- **Nie ma endpointu listującego przesyłki.** Tylko pojedyncza po ID z zamówienia.
- **Kampanie Allegro Ads nie są dostępne w publicznym REST API.**

## Konflikt EAN: zatrzymaj się, nie iteruj

Gdy POST zwróci 422 dotyczące EAN albo karty produktu, `offers.py` rzuca
`KonfliktKatalogu` i **przerywa**. To jest celowe. Kolejne próby z innymi danymi
nie pomagają, a zostawiają śmieci na koncie. Decyzja należy do Tomka:
(A) podpiąć istniejącą kartę, (B) zgłosić korektę katalogu do Allegro,
(C) nowe EAN z GS1, (D) potwierdzić EAN u dostawcy.

## Hamulce na zapisie

Konto jest produkcyjne, ma ponad 100 aktywnych ofert, a narzędzia wywołuje model.

- `potwierdzam=True` przy `end_offer` (nieodwracalne).
- `zastosuj=True` przy narzędziach cenników (masowe). Bez tego zwracają podgląd.
- Pojedyncza zmiana ceny albo stanu (`update_offer`) idzie od razu, bo jest odwracalna.

Nie usuwaj tych hamulców „dla wygody". Podgląd wyłapał już wywołanie, które
usunęłoby 32 z 33 metod dostawy w cenniku.

## Nie scrapuj Allegro

Danych ofert nie pobieramy przeglądarką ani `web_fetch`. Od tego jest ten serwer.
