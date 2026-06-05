# -*- coding: utf-8 -*-
"""
Modul kayit sistemi (registry).

Her kapanis modulu ortak bir arayuze uyar ve kendini buraya kaydeder:
    kaydet(Modul(kod, ad, ikon, sira, calistir, panel_html))

Boylece yeni modul eklemek = moduller/ icine bir dosya atip kaydet() cagirmak.
Sol menu ve kokpit otomatik dolar; iskelete dokunmak gerekmez.

calistir(musteri_id, donem) -> sonuc(dict)   # analizi yapar, bulgu uretir
panel_html(sonuc) -> str                      # sonucu HTML panel olarak doner
"""

KAYIT = {}      # kod -> Modul


class Modul:
    def __init__(self, kod, ad, ikon, sira, calistir, panel_html):
        self.kod = kod
        self.ad = ad
        self.ikon = ikon
        self.sira = sira
        self.calistir = calistir
        self.panel_html = panel_html


def kaydet(modul):
    KAYIT[modul.kod] = modul


def liste():
    """Sira'ya gore modul listesi."""
    return sorted(KAYIT.values(), key=lambda m: m.sira)


def kodlar():
    return [m.kod for m in liste()]


def getir(kod):
    return KAYIT.get(kod)


def yukle_hepsi():
    """moduller/ paketindeki tum modulleri import ederek kayit ettirir."""
    from moduller import kayitli_yukle
    kayitli_yukle()
