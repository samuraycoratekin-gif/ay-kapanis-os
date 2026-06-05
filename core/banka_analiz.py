# -*- coding: utf-8 -*-
"""
Banka ekstresi <-> ERP 102 banka defteri eslestirme.

Eslestirme: mutlak tutar (tolerans) + tarih yakinligi (gun tolerans). Once ayni gun,
sonra tolerans icinde en yakin tarih. Eslesmeyenler iki yonlu raporlanir + komisyon/
masraf hareketleri icin gider fisi onerisi uretilir.

Isaret: + = hesaba giren, - = hesaptan cikan (banka_oku ile ayni).
"""
import itertools
from datetime import datetime, date
from core.metin import tr_upper as _tr_upper

TUTAR_TOL = 0.01
GUN_TOL = 3
ALTKUME_MAX = 4      # bir toplu hareket en fazla kac kalemden olusabilir (1:N / N:1)
ALTKUME_HAVUZ = 14   # kombinasyon patlamasini onlemek icin aday havuz siniri
ALTKUME_GUN_TOL = 7  # toplu hareket kalemleri tarih penceresi (gun)

KOMISYON_ANAHTAR = ["KOMISYON", "MASRAF", "ISLEM UCRETI", "ISLEM ÜCRETI", "EFT UCRET",
                    "HAVALE UCRET", "BSMV", "HESAP ISLETIM", "POS", "KART UCRET",
                    "VIRMAN UCRET", "GECIKME FAIZ", "DAMGA"]


def _gun_farki(a, b):
    if isinstance(a, datetime):
        a = a.date()
    if isinstance(b, datetime):
        b = b.date()
    if isinstance(a, date) and isinstance(b, date):
        return abs((a - b).days)
    return None


def _gun_uygun(a, b, tol):
    """Tarih farki tolerans icinde mi (tarih yoksa serbest)."""
    gf = _gun_farki(a, b)
    return gf is None or gf <= tol


def _altkume_bul(hedef_abs, adaylar, gun_hedef):
    """adaylar (eslesmemis kayitlar) arasindan |toplam| ~ hedef_abs olan en kucuk
    altkumeyi bulur. Kalemler kendi aralarinda AYNI yonde (hepsi giren / hepsi cikan)
    ve tarih penceresi icinde olmali. Bulunamazsa None."""
    if hedef_abs <= TUTAR_TOL:
        return None
    for isaret_poz in (True, False):
        havuz = [d for d in adaylar
                 if (d["tutar"] >= 0) == isaret_poz
                 and abs(d["tutar"]) > TUTAR_TOL
                 and _gun_uygun(gun_hedef, d["tarih"], ALTKUME_GUN_TOL)]
        havuz = havuz[:ALTKUME_HAVUZ]
        for n in range(2, min(ALTKUME_MAX, len(havuz)) + 1):
            for komb in itertools.combinations(havuz, n):
                if abs(sum(abs(d["tutar"]) for d in komb) - hedef_abs) <= TUTAR_TOL:
                    return list(komb)
    return None


def _tl(v):
    return f"{v:,.2f} TL".replace(",", "X").replace(".", ",").replace("X", ".")


def _komisyon_mu(aciklama):
    a = _tr_upper(aciklama)
    return any(k in a for k in KOMISYON_ANAHTAR)


def _fis_oneri(hareket):
    """Eslesmeyen banka hareketi icin yevmiye fisi onerisi (metin)."""
    t = hareket["tutar"]
    ac = hareket["aciklama"] or "Açıklama yok"
    if _komisyon_mu(ac):
        return {"tip": "komisyon",
                "ac": f"Banka masrafı/komisyonu — {_tl(abs(t))}: 770/780 Gider (B) / 102 Banka (A) fişi önerilir.",
                "kalem": ac}
    if t > 0:
        return {"tip": "giren",
                "ac": f"Kaydı olmayan PARA GİRİŞİ {_tl(t)} — 102 Banka (B) / ilgili cari-gelir (A). Kaynağı belirleyin.",
                "kalem": ac}
    return {"tip": "cikan",
            "ac": f"Kaydı olmayan PARA ÇIKIŞI {_tl(abs(t))} — ilgili cari-gider (B) / 102 Banka (A). Kaynağı belirleyin.",
            "kalem": ac}


def esle(banka, defter):
    defter = [dict(d) for d in defter]
    for d in defter:
        d["_eslesti"] = False

    eslesen = 0
    for b in banka:
        b["_eslesti"] = False

    for b in banka:
        adaylar = [d for d in defter if not d["_eslesti"]
                   and abs(abs(d["tutar"]) - abs(b["tutar"])) <= TUTAR_TOL]
        if not adaylar:
            continue
        # tarih yakinligina gore sirala (gun farki yoksa sona)
        def anahtar(d):
            gf = _gun_farki(b["tarih"], d["tarih"])
            return (999 if gf is None else gf)
        adaylar.sort(key=anahtar)
        en = adaylar[0]
        gf = _gun_farki(b["tarih"], en["tarih"])
        if gf is None or gf <= GUN_TOL:
            en["_eslesti"] = True
            b["_eslesti"] = True
            eslesen += 1

    # 2) Altkume (toplu hareket) eslesme: tek satir <-> birden cok satir.
    #    Fazla olarak raporlamadan ONCE denenir (yanlis "eksik kayit" alarmini onler).
    coklu = []
    for b in banka:                       # 1:N -> bir banka satiri = N defter satiri
        if b["_eslesti"]:
            continue
        kalan = [d for d in defter if not d["_eslesti"]]
        alt = _altkume_bul(abs(b["tutar"]), kalan, b["tarih"])
        if alt:
            for d in alt:
                d["_eslesti"] = True
            b["_eslesti"] = True
            eslesen += 1
            coklu.append({"yon": "1:N", "tek": b, "cok": alt,
                          "tutar": abs(b["tutar"]), "adet": len(alt)})
    for d in defter:                      # N:1 -> N banka satiri = bir defter satiri
        if d["_eslesti"]:
            continue
        kalan = [b for b in banka if not b["_eslesti"]]
        alt = _altkume_bul(abs(d["tutar"]), kalan, d["tarih"])
        if alt:
            for b in alt:
                b["_eslesti"] = True
            d["_eslesti"] = True
            eslesen += 1
            coklu.append({"yon": "N:1", "tek": d, "cok": alt,
                          "tutar": abs(d["tutar"]), "adet": len(alt)})

    banka_fazla = [b for b in banka if not b["_eslesti"]]
    defter_fazla = [d for d in defter if not d["_eslesti"]]

    komisyon = [b for b in banka_fazla if _komisyon_mu(b["aciklama"])]
    diger_banka = [b for b in banka_fazla if not _komisyon_mu(b["aciklama"])]

    oneriler = [dict(_fis_oneri(b), tarih=str(b["tarih"]), tutar=b["tutar"]) for b in banka_fazla]

    sorunlu = len(banka_fazla) + len(defter_fazla)
    return {
        "banka_sayisi": len(banka), "defter_sayisi": len(defter),
        "eslesen": eslesen,
        "coklu": coklu, "coklu_sayisi": len(coklu),
        "banka_fazla": diger_banka, "komisyon": komisyon,
        "defter_fazla": defter_fazla,
        "oneriler": oneriler,
        "sorunlu": sorunlu,
        "fis_sayisi": len(oneriler),
    }
