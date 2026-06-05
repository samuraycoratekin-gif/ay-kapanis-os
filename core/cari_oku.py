# -*- coding: utf-8 -*-
"""
Cari ekstre okuyucu (bizim defter veya karsi taraf ekstresi).

Esnek baslik tanima: cari kodu/adi, belge no, tutar, tip, tarih sutunlarini
basliktan bulur. .xls -> xlrd, .xlsx -> openpyxl (mizan_oku ile ayni katman).

Cikti: kayit listesi -> {cari_kodu, cari_adi, tarih, belge_no, belge_tipi,
                         tutar, tip, _id, _eslesti}
Bu sema Akilli Mutabakat motorunun bekledigi sema ile uyumludur (derin mod).
"""
from datetime import datetime, date
from core.mizan_oku import _ham_satirlar, _nrm, _sayi


def _baslik_bul(satirlar):
    """Cari kodu + tutar sutunlarini iceren ilk satiri bulur."""
    for i, r in enumerate(satirlar[:40]):
        nrm = [_nrm(c) for c in r]
        has_cari = any("CARI" in c and ("KOD" in c or "HESAP" in c) for c in nrm) \
            or any(c in ("CARIKODU", "CARIKOD", "CARI") for c in nrm)
        has_tutar = any(c in ("TUTAR", "TUTARI") or "TUTAR" in c for c in nrm)
        if has_cari and has_tutar:
            return i, nrm
    return None, None


def _harita(nrm):
    def bul(pred):
        for j, c in enumerate(nrm):
            if pred(c):
                return j
        return None
    return {
        "cari_kodu": bul(lambda c: c in ("CARIKODU", "CARIKOD", "CARI")
                         or ("CARI" in c and "KOD" in c)),
        "cari_adi": bul(lambda c: ("CARI" in c and ("ADI" in c or "UNVAN" in c))
                        or c in ("CARIADI", "UNVAN")),
        "belge_no": bul(lambda c: ("BELGE" in c and "NO" in c)
                        or ("EVRAK" in c and "NO" in c)
                        or c in ("BELGENO", "EVRAKNO", "FISNO")),
        "belge_tipi": bul(lambda c: ("BELGE" in c and ("TIP" in c or "TURU" in c))
                          or c == "BELGETIPI"),
        "tutar": bul(lambda c: c in ("TUTAR", "TUTARI")),
        "tip": bul(lambda c: c == "TIP" or c == "ISLEMTIPI"),
        "tarih": bul(lambda c: c == "TARIH" or "TARIH" in c),
    }


def _hucre(r, j):
    return r[j] if (j is not None and j < len(r)) else None


def _tarih(v):
    if isinstance(v, (datetime, date)):
        return v
    return str(v).strip() if v not in (None, "") else ""


def _tip(v):
    s = _nrm(v)
    if "ODEME" in s or "TAHSIL" in s or "DEKONT" in s:
        return "ODEME"
    return "FATURA"


def oku(yol):
    satirlar = _ham_satirlar(yol)
    hi, nrm = _baslik_bul(satirlar)
    if hi is None:
        raise ValueError("Cari ekstre basligi taninamadi (cari kodu + tutar sutunlari yok).")
    h = _harita(nrm)
    if h["cari_kodu"] is None or h["tutar"] is None:
        raise ValueError("Cari kodu veya tutar sutunu bulunamadi.")

    kayitlar = []
    for r in satirlar[hi + 1:]:
        ck = _hucre(r, h["cari_kodu"])
        tutar = _sayi(_hucre(r, h["tutar"]))
        if ck in (None, "") or tutar is None:
            continue
        kayitlar.append({
            "cari_kodu": str(ck).strip(),
            "cari_adi": (str(_hucre(r, h["cari_adi"])).strip()
                         if h["cari_adi"] is not None and _hucre(r, h["cari_adi"]) else ""),
            "tarih": _tarih(_hucre(r, h["tarih"])),
            "belge_no": (str(_hucre(r, h["belge_no"])).strip()
                         if h["belge_no"] is not None and _hucre(r, h["belge_no"]) else ""),
            "belge_tipi": (str(_hucre(r, h["belge_tipi"])).strip()
                           if h["belge_tipi"] is not None and _hucre(r, h["belge_tipi"]) else ""),
            "tutar": round(tutar, 2),
            "tip": _tip(_hucre(r, h["tip"])) if h["tip"] is not None else "FATURA",
            "_id": len(kayitlar),
            "_eslesti": False,
        })
    return kayitlar


def grupla(kayitlar):
    g = {}
    for k in kayitlar:
        g.setdefault(k["cari_kodu"], []).append(k)
    return g
