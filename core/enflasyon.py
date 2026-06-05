# -*- coding: utf-8 -*-
"""
Enflasyon Duzeltmesi (VUK mukerrer 298) - kontrol & kaba tahmin motoru.

Mizandan beslenir. Kesin duzeltme KIYMET BAZINDA ve EDINIM TARIHINE gore yapilir;
mizan bunlari icermez. Bu modul:
  1) Parasal / parasal-olmayan ayrim   : Bilanco hesaplarini iki kovaya boler.
  2) Net parasal pozisyon kar/zarari   : Net parasal aktif -> satin alma gucu KAYBI,
                                         net parasal pasif  -> KAZANC (enflasyonda).
  3) Parasal-olmayan duzeltme tahmini  : Bakiye x (donem katsayisi - 1). Yil basindan
                                         tasindigi varsayimiyla KABA tahmin (YTD).
  4) 698 kontrolu                       : 698 Enflasyon Duzeltme Hesabi donem sonunda
                                         580/570'e devredilip kapanmali; acik kalmis mi.

Duzeltme katsayisi = donem sonu Yi-UFE / yil basi (onceki Aralik) Yi-UFE.

UYARI: Yi-UFE tablosu TUIK'ten TEYIT edilmelidir; 2025-2026 degerleri tahminidir.
Tablo bu dosyada (YI_UFE) guncellenebilir.

Isaret kurali: pozitif = borc bakiye, negatif = alacak bakiye (mizan_oku ile ayni).
"""
from core import ayarlar

TOLERANS = 1.0

# Yi-UFE (Yurt Ici Uretici Fiyat Endeksi, TUIK, 2003=100) - ay sonu degerleri.
# 2022-2024 gerceklesen (yaklasik); 2025-2026 TAHMINI -> teyit edilmeli.
YI_UFE = {
    "2022-12": 2021.2,
    "2023-01": 2105.2, "2023-02": 2147.0, "2023-03": 2181.0, "2023-04": 2244.9,
    "2023-05": 2247.2, "2023-06": 2319.4, "2023-07": 2434.0, "2023-08": 2629.0,
    "2023-09": 2749.0, "2023-10": 2803.0, "2023-11": 2882.0, "2023-12": 2915.3,
    "2024-01": 3017.2, "2024-02": 3076.6, "2024-03": 3195.9, "2024-04": 3299.0,
    "2024-05": 3372.0, "2024-06": 3429.0, "2024-07": 3486.0, "2024-08": 3537.0,
    "2024-09": 3593.0, "2024-10": 3661.0, "2024-11": 3713.0, "2024-12": 3742.0,
    "2025-01": 3823.0, "2025-02": 3897.0, "2025-03": 3968.0, "2025-04": 4040.0,
    "2025-05": 4109.0, "2025-06": 4170.0, "2025-07": 4230.0, "2025-08": 4290.0,
    "2025-09": 4350.0, "2025-10": 4405.0, "2025-11": 4458.0, "2025-12": 4510.0,
    "2026-01": 4560.0, "2026-02": 4610.0, "2026-03": 4660.0, "2026-04": 4708.0,
    "2026-05": 4755.0, "2026-06": 4800.0,
}

KAYNAK_NOTU = ("Yİ-ÜFE değerleri TÜİK kaynağından teyit edilmelidir; 2025-2026 satırları "
               "tahminîdir. Düzeltme katsayısı bu tabloya göre hesaplanır.")

# --- Parasal olmayan (duzeltmeye tabi) 3 haneli ana hesaplar ---
PARASAL_OLMAYAN = {
    # Menkul kiymet - hisse senedi
    "110", "118", "119",
    # Stoklar
    "150", "151", "152", "153", "157", "158", "159",
    # Gelecek aylara/yillara ait pesin odenen giderler
    "180", "181", "280", "281",
    # Mali duran varliklar (istirak/bagli ortaklik - hisse)
    "240", "242", "243", "244", "245", "247", "248", "249",
    # Maddi duran varliklar + amortisman + verilen avanslar
    "250", "251", "252", "253", "254", "255", "256", "257", "258", "259",
    # Maddi olmayan duran varliklar
    "260", "261", "262", "263", "264", "267", "268", "269",
    # Ozel tukenmeye tabi varliklar
    "271", "277", "278", "279",
    # Alinan siparis avanslari (parasal olmayan yukumluluk)
    "340", "349", "440", "449",
    # Ozkaynaklar (sermaye, yedekler, gecmis yil k/z)
    "500", "501", "502", "520", "521", "522", "523", "524", "525", "526", "527", "529",
    "540", "541", "542", "548", "549", "570", "580",
}

# --- Parasal (duzeltmeye tabi DEGIL) ---
PARASAL = {
    "100", "101", "102", "103", "104", "108",
    "111", "112",
    "120", "121", "122", "124", "126", "127", "128", "129",
    "130", "131", "132", "133", "135", "136", "137", "138",
    "190", "191", "192", "193", "195", "196",
    "300", "303", "304", "305", "306", "308", "309",
    "320", "321", "322", "326", "329",
    "330", "331", "335", "336", "337", "338", "339",
    "360", "361", "368", "369",
    "370", "371", "372", "373",
    "400", "405", "407", "408", "409",
    "420", "421", "426", "429",
    "430", "431", "432", "436", "437", "438", "439",
    "460", "472", "473", "474", "479", "480", "481", "492", "493", "499",
}


def _ayar():
    a = ayarlar.oku()
    return (bool(a.get("enflasyon_uygula", True)),
            float(a.get("enflasyon_onem_tutar", 1000.0)))


def _katsayi(guncel_ay):
    """Donem sonu Yi-UFE / yil basi (onceki yil Aralik) Yi-UFE. None ise yetersiz veri."""
    if not guncel_ay or guncel_ay not in YI_UFE:
        return None, None, None
    yil = int(guncel_ay[:4])
    onceki_aralik = f"{yil-1}-12"
    if onceki_aralik not in YI_UFE:
        return None, None, None
    son = YI_UFE[guncel_ay]
    bas = YI_UFE[onceki_aralik]
    if bas <= 0:
        return None, None, None
    return son / bas, son, bas


def analiz_et(mizan):
    uygula, onem = _ayar()
    h = mizan["hesaplar"]
    guncel = mizan.get("guncel_ay")
    katsayi, son_ufe, bas_ufe = _katsayi(guncel)

    parasal_aktif = parasal_pasif = 0.0
    pol_kalemler = []          # parasal olmayan kalemler (duzeltmeye tabi)
    pol_toplam = 0.0
    siniflanmamis = []         # bilanco hesabi ama listede yok -> dürüstlük icin ayri

    for ana, o in h.items():
        n = str(ana)[:3]
        b = o.get("toplam", 0.0) or 0.0
        if abs(b) <= TOLERANS:
            continue
        d = n[0] if n else ""
        if n in PARASAL:
            if b >= 0:
                parasal_aktif += b
            else:
                parasal_pasif += -b
        elif n in PARASAL_OLMAYAN:
            pol_toplam += b
            duzeltme = (b * (katsayi - 1)) if katsayi else None
            pol_kalemler.append({"ana": n, "ad": o.get("ad", ""), "bakiye": b,
                                 "duzeltme": (round(duzeltme, 2) if duzeltme is not None else None)})
        elif d in "12345":     # siniflanmamis bilanco hesabi (6/7 sonuc haric)
            siniflanmamis.append({"ana": n, "ad": o.get("ad", ""), "bakiye": b})

    # Net parasal pozisyon: + ise net parasal AKTIF (enflasyonda satin alma gucu KAYBI)
    net_parasal = parasal_aktif - parasal_pasif
    ppk = (net_parasal * (katsayi - 1)) if katsayi else None   # parasal pozisyon kayb(+)/kazanc(-)

    # Parasal olmayan net duzeltme (kaba tahmin)
    pol_duzeltme = (pol_toplam * (katsayi - 1)) if katsayi else None

    # 698 kontrolu
    b698 = (h.get("698", {}) or {}).get("toplam", 0.0) or 0.0
    uyarilar = []
    if uygula and katsayi and abs(pol_toplam) > onem and abs(b698) <= TOLERANS and not _enf_yapildi(h):
        uyarilar.append({"tip": "yapilmamis",
                         "ac": f"Parasal olmayan kıymetler {pol_toplam:,.2f} TL düzeyinde ancak 698 Enflasyon "
                               f"Düzeltme Hesabı'nda hareket yok — dönem enflasyon düzeltmesi yapılmamış olabilir."})
    if abs(b698) > TOLERANS:
        uyarilar.append({"tip": "acik_698",
                         "ac": f"698 Enflasyon Düzeltme Hesabı {b698:,.2f} TL bakiye veriyor — dönem sonunda "
                               f"580/570'e devredilip kapatılmalı."})
    if not katsayi:
        uyarilar.append({"tip": "veri",
                         "ac": f"{guncel or 'Dönem'} için Yİ-ÜFE katsayısı hesaplanamadı (tablo eksik) — "
                               f"core/enflasyon.py içindeki Yİ-ÜFE tablosunu güncelleyin."})
    if not uygula:
        uyarilar.append({"tip": "kapsam",
                         "ac": "Ayarlarda enflasyon düzeltmesi kapsam dışı işaretli — kontrol bilgi amaçlı sunulur."})

    pol_kalemler.sort(key=lambda x: -abs(x["bakiye"]))
    return {
        "uygula": uygula,
        "katsayi": (round(katsayi, 4) if katsayi else None),
        "son_ufe": son_ufe, "bas_ufe": bas_ufe, "guncel_ay": guncel,
        "parasal_aktif": round(parasal_aktif, 2),
        "parasal_pasif": round(parasal_pasif, 2),
        "net_parasal": round(net_parasal, 2),
        "parasal_poz_kar": (round(-ppk, 2) if ppk is not None else None),   # +kazanc / -kayip
        "pol_toplam": round(pol_toplam, 2),
        "pol_duzeltme": (round(pol_duzeltme, 2) if pol_duzeltme is not None else None),
        "pol_kalemler": pol_kalemler[:30],
        "pol_kalem_sayisi": len(pol_kalemler),
        "siniflanmamis": sorted(siniflanmamis, key=lambda x: -abs(x["bakiye"]))[:15],
        "b698": round(b698, 2),
        "uyarilar": uyarilar,
        "kaynak_notu": KAYNAK_NOTU,
        "var": bool(pol_kalemler),
    }


def _enf_yapildi(h):
    """698 gecmis hareketi ya da 580/570 enflasyon devri izine kaba bakis."""
    o = h.get("698")
    if o and o.get("aylik"):
        return any(abs(v or 0) > TOLERANS for v in o["aylik"].values())
    return False
