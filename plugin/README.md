# Plugin Allegro Buy-Pack

Podpina serwer MCP `allegro` do Cowork.

## Zbudowanie paczki

```bash
cd plugin && zip -r ../wyniki/allegro-buypack.plugin . -x "*.DS_Store"
```

Powstały plik instalujesz w Cowork przez Settings → Plugins.

## Uwaga o ścieżkach

`.mcp.json` zawiera **bezwzględne ścieżki do tego komputera**. Poprzednia wersja
pluginu wskazywała na `/Users/tomasz/...` (konto na starym Macu) i przez to nie
działała nigdzie indziej. Po przeniesieniu projektu na inny komputer przebuduj
`.mcp.json`, zamiast kopiować paczkę.

## Otwarta kwestia: dostęp sieciowy z Cowork

Notatka `Blokady i otwarte pytania` w vaulcie mówi, że z sandboxa Cowork
`api.allegro.pl` był nieosiągalny (proxy zwracało 403 Tunnel connection failed,
zweryfikowane 2026-07-15). Z Claude Code na tym komputerze API odpowiada
normalnie, ale **to nie jest dowód, że z Cowork też zadziała**: to inne
środowisko sieciowe. Sprawdź to pierwszym wywołaniem `get_profile` po instalacji.

Jeśli blokada nadal jest, sam plugin jej nie zdejmie: potrzebny byłby relay
na allowliście, a nie zmiana konfiguracji MCP.

## Serwer

Katalog projektu: `Desktop/Claude/projekty/allegro-buypack/`
(FastMCP, Python 3.14, 26 narzędzi).

Tokeny siedzą w `.env` w katalogu projektu i odświeżają się same.
Gdy refresh token wygaśnie: `.venv/bin/python auth.py`.
