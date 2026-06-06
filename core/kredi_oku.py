# -*- coding: utf-8 -*-
"""
Banka kredisi odeme plani (amortisman tablosu) okuyucu.

Beklenen kolonlar (esnek baslik tanima):
  Taksit No | Vade/Odeme Tarihi | Taksit Tutari | Anapara | Faiz | Kalan Anapara
  (istege bagli: Kredi/Banka Adi, Doviz, Defter Kur, Guncel Kur)

Bir dosyada birden cok kredi olabilir; "Kredi/Banka" kolonu varsa krediye gore
gruplanir, yoksa tek kredi kabul edilir. mizan_oku ham satir/normalize/sayi
katmanini kullanir; .xls/.xlsx desteklenir.
"""
from core.mizan_oku import _ham_satirlar, _nrm, _sayi
from core.varlik_oku import _bul, _baslik_bul, _hucre, _metin, _tarihe


def oku(yol):
    satirlar = _ham_satirlar(yol)
    gerekli = [lambda c: "ANAPARA" in c or "TAKSIT" in c,
               lambda c: "VADE" in c or ("ODEME" in c and "TARIH" in c) or c == "TARIH"]
    hi, nrm = _baslik_bul(satirlar, gerekli)
    if hi is None:
        raise ValueError("Kredi ödeme planı başlığı tanınamadı (anapara/taksit + vade sütunları yok).")
    h = {
        "kredi": _bul(nrm, lambda c: c in ("KREDI", "BANKA") or "KREDINO" in c or
                      ("KREDI" in c and "AD" in c) or "REFERANS" in c),
        "no": _bul(nrm, lambda c: ("TAKSIT" in c and "NO" in c) or c in ("NO", "SIRA", "TAKSITNO")),
        "vade": _bul(nrm, lambda c: "VADE" in c or ("ODEME" in c and "TARIH" in c) or c == "TARIH"),
        "taksit": _bul(nrm, lambda c: ("TAKSIT" in c and "TUTAR" in c) or
                       ("ODEME" in c and "TUTAR" in c) or c == "TAKSIT"),
        "anapara": _bul(nrm, lambda c: "ANAPARA" in c),
        "faiz": _bul(nrm, lambda c: "FAIZ" in c),
        "kalan": _bul(nrm, lambda c: "KALAN" in c),
        "doviz": _bul(nrm, lambda c: c in ("DOVIZ", "CINS", "PARABIRIMI") or "PARABIRIM" in c),
        "defter_kur": _bul(nrm, lambda c: "DEFTER" in c and "KUR" in c),
        "guncel_kur": _bul(nrm, lambda c: ("GUNCEL" in c or "TCMB" in c or "DONEMSONU" in c) and "KUR" in c),
    }

    gruplar = {}   # ad -> kredi dict
    sira = []      # ekleme sirasini koru
    for r in satirlar[hi + 1:]:
        vade = _tarihe(_hucre(r, h["vade"]))
        anapara = _sayi(_hucre(r, h["anapara"]))
        taksit = _sayi(_hucre(r, h["taksit"]))
        faiz = _sayi(_hucre(r, h["faiz"]))
        # En az bir anlamli sayi + vade olmali
        if vade is None and anapara is None and taksit is None:
            continue
        if anapara is None and taksit is not None and faiz is not None:
            anapara = taksit - faiz
        if faiz is None and taksit is not None and anapara is not None:
            faiz = taksit - anapara
        if anapara is None and taksit is not None:
            anapara = taksit
        if anapara is None or anapara <= 0:
            continue

        ad = _metin(_hucre(r, h["kredi"])) or "Kredi"
        if ad not in gruplar:
            gruplar[ad] = {"ad": ad, "doviz": "TL", "defter_kur": None,
                           "guncel_kur": None, "taksitler": []}
            sira.append(ad)
        g = gruplar[ad]
        dv = _metin(_hucre(r, h["doviz"]))
        if dv and g["doviz"] == "TL":
            g["doviz"] = dv.upper()
        dk = _sayi(_hucre(r, h["defter_kur"]))
        gk = _sayi(_hucre(r, h["guncel_kur"]))
        if dk and g["defter_kur"] is None:
            g["defter_kur"] = dk
        if gk and g["guncel_kur"] is None:
            g["guncel_kur"] = gk
        g["taksitler"].append({
            "no": int(_sayi(_hucre(r, h["no"])) or len(g["taksitler"]) + 1),
            "vade": vade.isoformat() if vade else None,
            "taksit": round(taksit, 2) if taksit is not None else round((anapara + (faiz or 0)), 2),
            "anapara": round(anapara, 2),
            "faiz": round(faiz, 2) if faiz is not None else 0.0,
            "kalan": round(_sayi(_hucre(r, h["kalan"])), 2) if _sayi(_hucre(r, h["kalan"])) is not None else None,
        })

    krediler = [gruplar[a] for a in sira if gruplar[a]["taksitler"]]
    if not krediler:
        raise ValueError("Kredi ödeme planında geçerli taksit satırı bulunamadı.")
    return krediler
