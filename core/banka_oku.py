# -*- coding: utf-8 -*-
"""
Banka ekstresi / ERP banka defteri (102) okuyucu.

Esnek baslik: tarih, aciklama, tutar (ya da borc/alacak / giren/cikan) sutunlarini
basliktan bulur. .xls -> xlrd, .xlsx -> openpyxl (mizan_oku katmani).

Isaret kurali (her iki kaynak da ayni): + = hesaba GIREN, - = hesaptan CIKAN.
  Banka ekstresi : ALACAK/GIREN = +,  BORC/CIKAN = -
  ERP 102 defteri: BORC = +,          ALACAK = -   (102 aktif hesap)
Eslestirme mutlak tutar + tarih ile yapilir; isaret yalniz gosterim/yon icindir.

Cikti: {tarih, aciklama, tutar, _id, _eslesti}
"""
from datetime import datetime, date
from core.mizan_oku import _ham_satirlar, _nrm, _sayi


def _baslik_bul(satirlar):
    for i, r in enumerate(satirlar[:40]):
        nrm = [_nrm(c) for c in r]
        has_tarih = any("TARIH" in c for c in nrm)
        has_para = any(c in ("TUTAR", "ISLEMTUTARI", "BORC", "ALACAK")
                       or "TUTAR" in c or c in ("GIREN", "CIKAN", "GIRIS", "CIKIS") for c in nrm)
        if has_tarih and has_para:
            return i, nrm
    return None, None


def _harita(nrm):
    def bul(pred):
        for j, c in enumerate(nrm):
            if pred(c):
                return j
        return None
    return {
        "tarih": bul(lambda c: c in ("TARIH", "ISLEMTARIHI", "VALORTARIHI") or "TARIH" in c),
        "aciklama": bul(lambda c: "ACIKLAMA" in c or c in ("DETAY", "ISLEM")),
        "tutar": bul(lambda c: c in ("TUTAR", "ISLEMTUTARI")),
        "borc": bul(lambda c: c == "BORC" or c in ("CIKAN", "CIKIS")),
        "alacak": bul(lambda c: c == "ALACAK" or c in ("GIREN", "GIRIS")),
    }


def _hucre(r, j):
    return r[j] if (j is not None and j < len(r)) else None


def _tarih(v):
    if isinstance(v, (datetime, date)):
        return v
    # Metin tarihleri date'e cevir ("15.05.2026", "2026-05-15"...). Cevrilemezse
    # ham metni birak — ama o zaman gun toleransi uygulanamayacagindan eslesme
    # salt tutara kalir; bu yuzden cevirmeyi elimizden geldigince deneriz.
    from core.varlik_oku import _tarihe
    d = _tarihe(v)
    if d is not None:
        return d
    return str(v).strip() if v not in (None, "") else ""


def oku(yol, kaynak="banka"):
    satirlar = _ham_satirlar(yol)
    hi, nrm = _baslik_bul(satirlar)
    if hi is None:
        raise ValueError("Banka başlığı tanınamadı (tarih + tutar/borç/alacak sütunları yok).")
    h = _harita(nrm)
    if h["tutar"] is None and h["borc"] is None and h["alacak"] is None:
        raise ValueError("Tutar veya borç/alacak sütunu bulunamadı.")

    kayitlar = []
    for r in satirlar[hi + 1:]:
        tutar = _sayi(_hucre(r, h["tutar"])) if h["tutar"] is not None else None
        if tutar is None:
            b = _sayi(_hucre(r, h["borc"])) or 0.0
            a = _sayi(_hucre(r, h["alacak"])) or 0.0
            if b == 0 and a == 0:
                continue
            # banka: alacak(+) giren, borc(-) cikan ; defter(102): borc(+) giren
            if kaynak == "defter":
                tutar = b - a
            else:
                tutar = a - b
        if tutar is None:
            continue
        kayitlar.append({
            "tarih": _tarih(_hucre(r, h["tarih"])),
            "aciklama": (str(_hucre(r, h["aciklama"])).strip()
                         if h["aciklama"] is not None and _hucre(r, h["aciklama"]) else ""),
            "tutar": round(tutar, 2),
            "_id": len(kayitlar),
            "_eslesti": False,
        })
    return kayitlar
