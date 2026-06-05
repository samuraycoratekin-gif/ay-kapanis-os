# -*- coding: utf-8 -*-
"""
Faz B fis ureticilerini besleyen liste okuyuculari:
  - demirbas_oku   : sabit kiymet (amortisman) listesi
  - dovizli_oku    : dovizli hesap bakiyeleri + kur (kur farki degerleme)
  - senet_oku      : vadeli senet/cek listesi (reeskont)

Hepsi mizan_oku'nun ham satir/normalize/sayi katmanini kullanir; esnek baslik
tanima ile sutun adlarini bulur. .xls/.xlsx desteklenir.
"""
from datetime import datetime, date
from core.mizan_oku import _ham_satirlar, _nrm, _sayi


def _bul(nrm, pred):
    for j, c in enumerate(nrm):
        if pred(c):
            return j
    return None


def _baslik_bul(satirlar, gerekli):
    """En az 'gerekli' adet kolon eslesen ilk satiri (index, normalize) doner."""
    for i, r in enumerate(satirlar[:40]):
        nrm = [_nrm(c) for c in r]
        if sum(1 for p in gerekli if _bul(nrm, p) is not None) >= len(gerekli):
            return i, nrm
    return None, None


def _hucre(r, j):
    return r[j] if (j is not None and j < len(r)) else None


def _metin(v):
    return str(v).strip() if v not in (None, "") else ""


def _tarihe(v):
    """datetime/date veya 'YYYY-MM-DD' / 'DD.MM.YYYY' metnini date'e cevirir; olmazsa None."""
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = _metin(v)
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y.%m.%d"):
        try:
            return datetime.strptime(s[:10], fmt).date()
        except ValueError:
            continue
    return None


# --------------------------------------------------------------------------- #
# Demirbas (sabit kiymet / amortisman) listesi
# Beklenen kolonlar: ad, maliyet (tutar), oran(%) veya faydali omur (yil),
#   istege bagli: birikmis, gider_hesap, birikmis_hesap, yontem
# --------------------------------------------------------------------------- #
def demirbas_oku(yol):
    satirlar = _ham_satirlar(yol)
    gerekli = [lambda c: "MALIYET" in c or c in ("TUTAR", "TUTARI", "DEGER"),
               lambda c: "ORAN" in c or "OMUR" in c or "AMORTISMAN" in c]
    hi, nrm = _baslik_bul(satirlar, gerekli)
    if hi is None:
        raise ValueError("Demirbas listesi basligi taninamadi (maliyet + oran/omur sutunlari yok).")
    h = {
        "ad": _bul(nrm, lambda c: c in ("AD", "ADI", "VARLIK", "KIYMET") or "ACIKLAMA" in c or "DEMIRBAS" in c),
        "maliyet": _bul(nrm, lambda c: "MALIYET" in c or c in ("TUTAR", "TUTARI", "DEGER")),
        "oran": _bul(nrm, lambda c: "ORAN" in c),
        "omur": _bul(nrm, lambda c: "OMUR" in c),
        "aylik": _bul(nrm, lambda c: "AYLIK" in c and "AMORTISMAN" in c),
        "birikmis": _bul(nrm, lambda c: "BIRIKMIS" in c),
        "gider_hesap": _bul(nrm, lambda c: "GIDER" in c and "HESAP" in c),
        "birikmis_hesap": _bul(nrm, lambda c: "BIRIKMIS" in c and "HESAP" in c),
    }
    kayitlar = []
    for r in satirlar[hi + 1:]:
        maliyet = _sayi(_hucre(r, h["maliyet"]))
        if maliyet is None or maliyet <= 0:
            continue
        oran = _sayi(_hucre(r, h["oran"]))
        omur = _sayi(_hucre(r, h["omur"]))
        if oran is None and omur:
            oran = 100.0 / omur
        aylik = _sayi(_hucre(r, h["aylik"]))
        if aylik is None:
            aylik = (maliyet * (oran or 0) / 100.0) / 12.0
        kayitlar.append({
            "ad": _metin(_hucre(r, h["ad"])) or "Sabit kıymet",
            "maliyet": round(maliyet, 2),
            "oran": round(oran, 2) if oran else None,
            "aylik": round(aylik, 2),
            "birikmis": round(_sayi(_hucre(r, h["birikmis"])) or 0, 2),
            "gider_hesap": _metin(_hucre(r, h["gider_hesap"])) or "770",
            "birikmis_hesap": _metin(_hucre(r, h["birikmis_hesap"])) or "257",
        })
    return kayitlar


# --------------------------------------------------------------------------- #
# Dovizli hesap listesi (kur farki degerleme)
# Beklenen kolonlar: hesap, doviz_tutar, defter_kur, guncel_kur
#   (alternatif: defter_tl + guncel_tl)
# --------------------------------------------------------------------------- #
def dovizli_oku(yol):
    satirlar = _ham_satirlar(yol)
    gerekli = [lambda c: "HESAP" in c,
               lambda c: "KUR" in c or "TL" in c or "DEGER" in c]
    hi, nrm = _baslik_bul(satirlar, gerekli)
    if hi is None:
        raise ValueError("Dövizli liste başlığı tanınamadı (hesap + kur/değer sütunları yok).")
    h = {
        "hesap": _bul(nrm, lambda c: c in ("HESAP", "HESAPKODU", "HESAPNO") or ("HESAP" in c and "KOD" in c)),
        "ad": _bul(nrm, lambda c: "ACIKLAMA" in c or c in ("AD", "ADI", "UNVAN")),
        "doviz": _bul(nrm, lambda c: c in ("DOVIZ", "DOVIZCINSI", "PARABIRIMI", "CINS")),
        "doviz_tutar": _bul(nrm, lambda c: ("DOVIZ" in c and "TUTAR" in c) or c in ("DOVIZTUTAR", "DOVIZBAKIYE")),
        "defter_kur": _bul(nrm, lambda c: "DEFTER" in c and "KUR" in c),
        "guncel_kur": _bul(nrm, lambda c: ("GUNCEL" in c or "TCMB" in c or "DONEMSONU" in c) and "KUR" in c),
        "defter_tl": _bul(nrm, lambda c: "DEFTER" in c and ("TL" in c or "DEGER" in c)),
        "guncel_tl": _bul(nrm, lambda c: ("GUNCEL" in c or "TCMB" in c or "DONEMSONU" in c) and ("TL" in c or "DEGER" in c)),
    }
    kayitlar = []
    for r in satirlar[hi + 1:]:
        hesap = _metin(_hucre(r, h["hesap"]))
        if not hesap or not hesap[0].isdigit():
            continue
        dt = _sayi(_hucre(r, h["doviz_tutar"]))
        dk = _sayi(_hucre(r, h["defter_kur"]))
        gk = _sayi(_hucre(r, h["guncel_kur"]))
        defter_tl = _sayi(_hucre(r, h["defter_tl"]))
        guncel_tl = _sayi(_hucre(r, h["guncel_tl"]))
        if defter_tl is not None and guncel_tl is not None:
            fark = guncel_tl - defter_tl
        elif dt is not None and dk is not None and gk is not None:
            defter_tl = dt * dk
            guncel_tl = dt * gk
            fark = guncel_tl - defter_tl
        else:
            continue
        kayitlar.append({
            "hesap": hesap,
            "ad": _metin(_hucre(r, h["ad"])),
            "doviz": _metin(_hucre(r, h["doviz"])),
            "doviz_tutar": round(dt, 2) if dt is not None else None,
            "defter_tl": round(defter_tl, 2),
            "guncel_tl": round(guncel_tl, 2),
            "fark": round(fark, 2),
        })
    return kayitlar


# --------------------------------------------------------------------------- #
# Vadeli senet/cek listesi (reeskont)
# Beklenen kolonlar: tip (alacak/borc), tutar (nominal), vade (tarih),
#   istege bagli: faiz_orani (yillik %)
# --------------------------------------------------------------------------- #
def senet_oku(yol):
    satirlar = _ham_satirlar(yol)
    gerekli = [lambda c: c in ("TUTAR", "TUTARI", "NOMINAL") or "NOMINAL" in c,
               lambda c: "VADE" in c]
    hi, nrm = _baslik_bul(satirlar, gerekli)
    if hi is None:
        raise ValueError("Senet listesi başlığı tanınamadı (tutar + vade sütunları yok).")
    h = {
        "tip": _bul(nrm, lambda c: c == "TIP" or "TUR" in c or "CINS" in c),
        "tutar": _bul(nrm, lambda c: c in ("TUTAR", "TUTARI", "NOMINAL") or "NOMINAL" in c),
        "vade": _bul(nrm, lambda c: "VADE" in c),
        "faiz": _bul(nrm, lambda c: "FAIZ" in c or "ORAN" in c),
        "aciklama": _bul(nrm, lambda c: "ACIKLAMA" in c or c in ("AD", "ADI")),
    }
    kayitlar = []
    for r in satirlar[hi + 1:]:
        tutar = _sayi(_hucre(r, h["tutar"]))
        vade = _tarihe(_hucre(r, h["vade"]))
        if tutar is None or tutar <= 0 or vade is None:
            continue
        tip_ham = _nrm(_hucre(r, h["tip"]))
        tip = "borc" if ("BORC" in tip_ham or "ODENECEK" in tip_ham) else "alacak"
        kayitlar.append({
            "tip": tip,
            "tutar": round(tutar, 2),
            "vade": vade.isoformat(),
            "faiz": _sayi(_hucre(r, h["faiz"])),
            "aciklama": _metin(_hucre(r, h["aciklama"])),
        })
    return kayitlar


# --------------------------------------------------------------------------- #
# KDV Tevkifat listesi (kismi tevkifat — alici sorumlu sifatiyla)
# Beklenen kolonlar: islem turu, matrah
#   istege bagli: tevkifat orani (2/10, 9/10, %90, 0.9...), kdv orani (%20)
# --------------------------------------------------------------------------- #
def tevkifat_oku(yol):
    satirlar = _ham_satirlar(yol)
    gerekli = [lambda c: "MATRAH" in c or c in ("TUTAR", "TUTARI", "BEDEL"),
               lambda c: "ISLEM" in c or "HIZMET" in c or "TUR" in c or "ACIKLAMA" in c]
    hi, nrm = _baslik_bul(satirlar, gerekli)
    if hi is None:
        raise ValueError("Tevkifat listesi başlığı tanınamadı (işlem türü + matrah sütunları yok).")
    h = {
        "islem": _bul(nrm, lambda c: "ISLEM" in c or "HIZMET" in c or
                      (("TUR" in c or "ACIKLAMA" in c) and "ORAN" not in c)),
        "matrah": _bul(nrm, lambda c: "MATRAH" in c or c in ("TUTAR", "TUTARI", "BEDEL")),
        "kdv_oran": _bul(nrm, lambda c: "KDV" in c and "ORAN" in c),
        "tevkifat_oran": _bul(nrm, lambda c: "TEVKIFAT" in c or
                              ("ORAN" in c and "KDV" not in c) or "PAY" in c),
    }
    kayitlar = []
    for r in satirlar[hi + 1:]:
        matrah = _sayi(_hucre(r, h["matrah"]))
        if matrah is None or matrah <= 0:
            continue
        ko = _sayi(_hucre(r, h["kdv_oran"]))
        if ko is not None and ko > 1:   # "20" -> 0.20
            ko = ko / 100.0
        kayitlar.append({
            "islem": _metin(_hucre(r, h["islem"])) or "Belirtilmemiş hizmet",
            "matrah": round(matrah, 2),
            "kdv_orani": ko,
            "oran_ham": _metin(_hucre(r, h["tevkifat_oran"])),
        })
    return kayitlar


# --------------------------------------------------------------------------- #
# KDV matrah dokumu (matrah/oran tutarlilik denetimi icin)
# Beklenen kolonlar: tur (satis/alis), matrah, oran (KDV %)
#   istege bagli: kdv tutari, belge no, aciklama
# --------------------------------------------------------------------------- #
def kdv_matrah_oku(yol):
    satirlar = _ham_satirlar(yol)
    gerekli = [lambda c: "MATRAH" in c or c in ("TUTAR", "TUTARI", "BEDEL"),
               lambda c: "ORAN" in c or c == "KDV"]
    hi, nrm = _baslik_bul(satirlar, gerekli)
    if hi is None:
        raise ValueError("KDV matrah dökümü başlığı tanınamadı (matrah + oran sütunları yok).")
    h = {
        "tur": _bul(nrm, lambda c: c in ("TUR", "TIP", "CINS") or "TURU" in c or
                    "YON" in c or "ISLEM" in c),
        "matrah": _bul(nrm, lambda c: "MATRAH" in c or c in ("TUTAR", "TUTARI", "BEDEL")),
        "oran": _bul(nrm, lambda c: "ORAN" in c or c == "KDV"),
        "kdv": _bul(nrm, lambda c: ("KDV" in c and ("TUTAR" in c or "TUTARI" in c))
                    or c in ("KDVTUTARI", "HESAPLANANKDV")),
        "belge": _bul(nrm, lambda c: "BELGE" in c or "FATURA" in c or c in ("NO", "FISNO")),
        "aciklama": _bul(nrm, lambda c: "ACIKLAMA" in c or c in ("AD", "ADI")),
    }
    kayitlar = []
    for r in satirlar[hi + 1:]:
        matrah = _sayi(_hucre(r, h["matrah"]))
        if matrah is None or matrah <= 0:
            continue
        oran = _sayi(_hucre(r, h["oran"]))
        if oran is not None and 0 < oran < 1:   # 0.20 -> 20
            oran = oran * 100.0
        tur_ham = _nrm(_hucre(r, h["tur"]))
        if "ALIS" in tur_ham or "INDIR" in tur_ham or "GELEN" in tur_ham:
            tur = "alis"
        else:
            tur = "satis"   # varsayilan: satis (hesaplanan)
        kayitlar.append({
            "tur": tur,
            "matrah": round(matrah, 2),
            "oran": round(oran, 2) if oran is not None else None,
            "kdv": _sayi(_hucre(r, h["kdv"])),
            "belge": _metin(_hucre(r, h["belge"])),
            "aciklama": _metin(_hucre(r, h["aciklama"])),
        })
    return kayitlar
