# -*- coding: utf-8 -*-
"""Turkiye banka/resmi tatil takvimi.

Senet-cek vadeleri hafta sonu veya resmi tatile denk geldiginde tahsilat/odeme
fiilen SONRAKI is gununde gerceklesir. Nakit akis ongorusu bu kaymayi dikkate
alir; boylece "bu hafta tahsil edilir" sanilan bir senet aslinda gelecek haftaya
kayabilir.

Dini bayram tarihleri ay takvimine bagli oldugundan resmi (Diyanet/idari) ilan
edilen tarihler yil bazinda elle tutulur. Listede olmayan yillar icin yalnizca
sabit tatiller + hafta sonu uygulanir (dini bayramlar atlanir) — bu durumda
sonuc "yaklasik" sayilmalidir; YENI YIL EKLENDIKCE guncelleyin.
"""
from datetime import date, timedelta

# Sabit (her yil ayni) resmi tatiller — (ay, gun). Banka kapali.
SABIT_TATILLER = {
    (1, 1),    # Yilbasi
    (4, 23),   # Ulusal Egemenlik ve Cocuk Bayrami
    (5, 1),    # Emek ve Dayanisma Gunu
    (5, 19),   # Ataturk'u Anma, Genclik ve Spor Bayrami
    (7, 15),   # Demokrasi ve Milli Birlik Gunu
    (8, 30),   # Zafer Bayrami
    (10, 29),  # Cumhuriyet Bayrami
}

# Dini bayramlar (resmi tam gun tatiller, ISO tarih). Diyanet/idari ilanlara gore.
# NOT: ait oldugu yil listede yoksa dini bayramlar dikkate ALINMAZ.
DINI_TATILLER = {
    "2025": [
        # Ramazan Bayrami
        "2025-03-30", "2025-03-31", "2025-04-01",
        # Kurban Bayrami
        "2025-06-06", "2025-06-07", "2025-06-08", "2025-06-09",
    ],
    "2026": [
        # Ramazan Bayrami
        "2026-03-20", "2026-03-21", "2026-03-22",
        # Kurban Bayrami
        "2026-05-27", "2026-05-28", "2026-05-29", "2026-05-30",
    ],
    "2027": [
        # Ramazan Bayrami
        "2027-03-10", "2027-03-11", "2027-03-12",
        # Kurban Bayrami
        "2027-05-16", "2027-05-17", "2027-05-18", "2027-05-19",
    ],
}

_DINI_SET = {g for yil in DINI_TATILLER.values() for g in yil}


def dini_kapsam_var(d):
    """Verilen tarihin yili dini-bayram listesinde tanimli mi? Degilse dini
    bayramlar atlanir; cagiran taraf sonucu 'yaklasik' isaretleyebilir."""
    return str(d.year) in DINI_TATILLER


def is_tatil(d):
    """Hafta sonu (Cmt/Pzr) veya resmi/dini tatil ise True."""
    if d.weekday() >= 5:        # 5=Cumartesi, 6=Pazar
        return True
    if (d.month, d.day) in SABIT_TATILLER:
        return True
    return d.isoformat() in _DINI_SET


def is_isgunu(d):
    return not is_tatil(d)


def sonraki_isgunu(d):
    """d dahil ilk is gunu. d zaten is gunuyse d'yi doner."""
    g = d
    for _ in range(15):         # en uzun bayram+hafta sonu zinciri 15 gunu gecmez
        if is_isgunu(g):
            return g
        g = g + timedelta(days=1)
    return g


def kaydir(d):
    """Vade tarihini fiili tahsilat/odeme is gunune kaydirir; (efektif, kaydi_mi)."""
    ef = sonraki_isgunu(d)
    return ef, (ef != d)
