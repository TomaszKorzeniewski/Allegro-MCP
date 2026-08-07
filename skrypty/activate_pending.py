#!/usr/bin/env python3
"""Dopycha publikację ofert wiszących w kolejce Allegro.

Allegro kolejkuje zmiany statusu publikacji i odrzuca kolejne polecenie
błędem `InProgressTaskLimitReachedException`, dopóki poprzednie się nie
przemieli — potrafi to trwać kilkadziesiąt minut. Skrypt cyklicznie ponawia
ACTIVATE aż do skutku.
"""
import sys
import time
import uuid

from _sciezki import KORZEN, WYNIKI  # ustawia sys.path na korzeń projektu
from allegro_client import AllegroClient, AllegroAPIError

OFERTY = ["18791551973", "18791552054"]   # TP/0015 poj., TP/0017 - 12 szt.
INTERWAL = 180        # 3 min
MAX_PROB = 16         # ~48 min

c = AllegroClient()


def statusy():
    return {o: c.get(f"/sale/product-offers/{o}")["publication"]["status"]
            for o in OFERTY}


def sprobuj_aktywowac(oferty):
    cid = str(uuid.uuid4())
    c.request("PUT", f"/sale/offer-publication-commands/{cid}", json={
        "publication": {"action": "ACTIVATE"},
        "offerCriteria": [{"offers": [{"id": o} for o in oferty],
                           "type": "CONTAINS_OFFERS"}],
    })
    time.sleep(15)
    r = c.get(f"/sale/offer-publication-commands/{cid}/tasks")
    return [(t["offer"]["id"], t["status"],
             (t.get("errors") or [{}])[0].get("code", ""))
            for t in r.get("tasks", [])]


for proba in range(1, MAX_PROB + 1):
    st = statusy()
    czekajace = [o for o, s in st.items() if s != "ACTIVE"]
    if not czekajace:
        print(f"[{proba}] Wszystkie ACTIVE: {st}")
        print("GOTOWE")
        break

    print(f"[{proba}] status={st} — ponawiam ACTIVATE dla {czekajace}", flush=True)
    try:
        for oid, status, code in sprobuj_aktywowac(czekajace):
            print(f"     {oid}: {status} {code}", flush=True)
    except AllegroAPIError as e:
        print(f"     błąd polecenia: {str(e)[:200]}", flush=True)

    time.sleep(INTERWAL)
else:
    print(f"LIMIT PRÓB — końcowy status: {statusy()}")
    print("Zostały w kolejce. Można dopchnąć ręcznie w panelu sprzedawcy.")
