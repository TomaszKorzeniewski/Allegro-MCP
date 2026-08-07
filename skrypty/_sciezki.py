"""Ścieżki projektu dla skryptów pomocniczych.

Skrypty leżą w podkatalogu, a importują moduły z korzenia projektu
(`allegro_client`, `auth`, `config`, `offers`). Wcześniej każdy z nich miał
wpisaną na sztywno ścieżkę `/Users/tomasz/Desktop/allegro-buypack`, więc po
przeniesieniu projektu na inny komputer żaden nie startował.

Wyliczamy ją teraz z położenia pliku, więc projekt można przenieść gdziekolwiek.

Użycie w skrypcie:
    from _sciezki import KORZEN, WYNIKI
"""

import sys
from pathlib import Path

KORZEN = Path(__file__).resolve().parent.parent
WYNIKI = KORZEN / "wyniki"

# Import modułów z korzenia projektu.
if str(KORZEN) not in sys.path:
    sys.path.insert(0, str(KORZEN))

WYNIKI.mkdir(exist_ok=True)
