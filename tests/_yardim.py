# -*- coding: utf-8 -*-
"""Test yardimcilari: bellekte mizan/hesap sozlugu kurar (Excel I/O yok).

mizan_oku.oku()'nun urettigi sekille birebir ayni yapiyi taklit eder:
    mizan = {kaynak, format, aylar, guncel_ay, hesap_sayisi, satir_sayisi, hesaplar}
    hesaplar[ana] = {ana, ad, toplam, acilis, aylik:{ay:net}, detay_sayisi}
Isaret: pozitif = borc, negatif = alacak (TDHP).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

AYLAR = ["OCAK", "SUBAT", "MART", "NISAN", "MAYIS"]


def hesap(ana, ad="", toplam=None, acilis=0.0, aylik=None):
    """Tek bir ana hesap sozlugu. toplam verilmezse acilis+sum(aylik)."""
    ayl = {}
    if aylik is not None:
        if isinstance(aylik, dict):
            ayl = dict(aylik)
        else:  # liste -> AYLAR ile zip
            ayl = {a: v for a, v in zip(AYLAR, aylik)}
    if toplam is None:
        toplam = acilis + sum(ayl.values())
    return {"ana": str(ana), "ad": ad, "toplam": float(toplam),
            "acilis": float(acilis), "aylik": ayl, "detay_sayisi": 1}


def mizan(*hesaplar, aylar=None, guncel="MAYIS", kaynak="TEST", format="kumule"):
    aylar = list(aylar) if aylar is not None else list(AYLAR)
    h = {x["ana"]: x for x in hesaplar}
    return {"kaynak": kaynak, "format": format, "aylar": aylar,
            "guncel_ay": guncel, "hesap_sayisi": len(h),
            "satir_sayisi": len(h), "hesaplar": h}
