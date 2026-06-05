# -*- coding: utf-8 -*-
"""
Bordro icmal okuyucu.

Aylik bordro icmalini (puantaj ozeti) okur; personel bazli satirlari toplar.
Beklenen kolonlar (esnek baslik tanima):
  Brut Ucret | SGK Isci | Issizlik Isci | Gelir Vergisi | Damga | SGK Isveren |
  Issizlik Isveren | Net Ucret    (+ istege bagli Personel/Ad)

mizan_oku'nun ham satir/normalize/sayi katmanini kullanir. .xls/.xlsx desteklenir.
'TOPLAM/GENEL TOPLAM' satirlari cift sayim olmasin diye atlanir.
"""
from core.mizan_oku import _ham_satirlar, _nrm, _sayi
from core.varlik_oku import _bul, _baslik_bul, _hucre, _metin


def oku(yol):
    satirlar = _ham_satirlar(yol)
    gerekli = [lambda c: "BRUT" in c,
               lambda c: "NET" in c or "SGK" in c or "VERGI" in c]
    hi, nrm = _baslik_bul(satirlar, gerekli)
    if hi is None:
        raise ValueError("Bordro icmal başlığı tanınamadı (brüt + net/SGK/vergi sütunları yok).")
    h = {
        "ad": _bul(nrm, lambda c: "PERSONEL" in c or "ADSOYAD" in c or "ISIM" in c or c in ("AD", "ADI")),
        "brut": _bul(nrm, lambda c: "BRUT" in c),
        "sgk_isci": _bul(nrm, lambda c: "SGK" in c and "ISCI" in c),
        "issizlik_isci": _bul(nrm, lambda c: "ISSIZLIK" in c and "ISCI" in c),
        "gelir_vergisi": _bul(nrm, lambda c: ("GELIR" in c and "VERGI" in c) or "STOPAJ" in c),
        "damga": _bul(nrm, lambda c: "DAMGA" in c),
        "sgk_isveren": _bul(nrm, lambda c: "SGK" in c and "ISVEREN" in c),
        "issizlik_isveren": _bul(nrm, lambda c: "ISSIZLIK" in c and "ISVEREN" in c),
        "net": _bul(nrm, lambda c: "NET" in c),
    }
    alanlar = ["brut", "sgk_isci", "issizlik_isci", "gelir_vergisi",
               "damga", "sgk_isveren", "issizlik_isveren", "net"]
    toplam = {a: 0.0 for a in alanlar}
    kayitlar = []
    for r in satirlar[hi + 1:]:
        ad = _metin(_hucre(r, h["ad"]))
        if "TOPLAM" in _nrm(ad):          # toplam satiri -> cift sayma
            continue
        brut = _sayi(_hucre(r, h["brut"]))
        if brut is None or brut <= 0:
            continue
        kayit = {"ad": ad or f"Personel {len(kayitlar)+1}"}
        for a in alanlar:
            v = _sayi(_hucre(r, h[a])) or 0.0
            kayit[a] = round(v, 2)
            toplam[a] += v
        kayitlar.append(kayit)

    toplam = {a: round(v, 2) for a, v in toplam.items()}
    # Turetilenler
    toplam["sgk_toplam"] = round(toplam["sgk_isci"] + toplam["issizlik_isci"]
                                 + toplam["sgk_isveren"] + toplam["issizlik_isveren"], 2)
    toplam["vergi_toplam"] = round(toplam["gelir_vergisi"] + toplam["damga"], 2)
    toplam["personel_gider"] = round(toplam["brut"] + toplam["sgk_isveren"]
                                     + toplam["issizlik_isveren"], 2)
    toplam["net_hesap"] = round(toplam["brut"] - toplam["sgk_isci"] - toplam["issizlik_isci"]
                                - toplam["gelir_vergisi"] - toplam["damga"], 2)
    return {
        "kaynak": "Bordro İcmal",
        "personel_sayisi": len(kayitlar),
        "toplam": toplam,
        "satirlar": kayitlar,
    }
