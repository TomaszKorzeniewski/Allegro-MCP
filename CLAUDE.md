# Allegro Buy-Pack MCP — instrukcje dla Claude

Serwer MCP (FastMCP, 18 narzędzi) do konta Allegro **buy-pack**. Tokeny w `.env` (w `.gitignore`, auto-refresh przy 401). Jedyne źródło prawdy o projekcie biznesowym: vault Obsidian `Allegro Buy-Pack/MASTER — Allegro Buy-Pack.md`.

## Graphify — graf wiedzy kodu (JEST, używaj)

Repo ma zbudowany graf Graphify (`graphify-out/`, lokalny, w `.gitignore`). Zanim czytasz pliki na oślep:
- `/graphify query "..."`, `/graphify explain "AllegroClient"`, `/graphify path "AllegroClient" "auth"`.
- Hub = **`AllegroClient`** (klient REST API), serce autoryzacji = **`auth.py`** (OAuth device flow, rotacja tokenów). Brak cykli importów.
- ⚠️ Odświeżaj po większych zmianach: `graphify . --code-only` (100% lokalnie, 0 tokenów). Setup: vault `Narzędzia/Graphify — graf wiedzy kodu (setup i użycie).md`.

## Pułapki (skrót — detale w MASTER / pamięci)

- **Refresh token rotuje jednorazowo** — NIE odpalać serwera z dwóch klientów naraz (Code + Cowork) bez file-locka (krok 3, jeszcze niewdrożony, rekomendowany).
- MCP `create_offer` **NIE** robi zestawów (kat. 64541 wymaga `productSet` → 422) — zestawy przez `create_zestawy.py` (quantity=N).
- POST product-offers zwraca **202 = sukces** (async). Tokeny w `.env` bywają w apostrofach — parsery robią `.strip("'\"")`.
