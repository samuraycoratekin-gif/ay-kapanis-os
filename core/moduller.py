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

# Faz/grup tanimlari - sol menude basliklarla gruplama icin (kapanis is akisi).
GRUPLAR = [
    ("veri", "Veri & Mutabakat"),
    ("duzeltme", "Düzeltme"),
    ("vergi", "Sonuç & Vergi"),
]
_GRUP_AD = dict(GRUPLAR)
MODUL_GRUP = {
    "m2_mizan": "veri", "m3_cari": "veri", "m5_banka": "veri",
    "m4_gib_kdv": "veri", "m13_stok": "veri", "m12_bordro": "veri",
    "m7_eksik": "veri",
    "m6_fis": "duzeltme",
    "m9_finansal": "vergi", "m10_gecici_vergi": "vergi", "m11_beyan": "vergi",
    "m8_dosya": "vergi",
}


def grup_kod(kod):
    return MODUL_GRUP.get(kod, "")


def grup_ad(kod):
    return _GRUP_AD.get(MODUL_GRUP.get(kod, ""), "")


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
