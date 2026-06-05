# -*- coding: utf-8 -*-
"""
Mizan saglik taramasi - analiz motoru.

Kullanici (17 yil AP muhasebe) tarafindan onaylanan 4 kural:
  1) Ters bakiye      : aktif hesap alacak, pasif/gelir hesap borc bakiye veriyorsa.
                        Cift yonlu/kontra hesaplar (131/331, amortisman vb.) haric.
  2) Anormal sapma    : guncel ay net hareketi onceki aylara gore esik (varsayilan %100)
                        ustu sapiyorsa VE tutar alt limit (varsayilan 100.000 TL) ustuyse.
  3) Kapanmamis gecici : 191/391/196 ve 7xx yansitma hesaplari ay sonunda bakiye veriyorsa.
  4) Bos zorunlu hesap : donem sonunda mutlaka hareket/bakiye beklenen kontrol
                        hesaplari (ayarlar.zorunlu_hesaplar) mizanda yoksa veya
                        hem bakiye hem bu ayki hareket ~0 ise SOFT uyari uretir.

Isaret: pozitif=borc, negatif=alacak.
"""
from core import ayarlar

TOLERANS = 1.0          # TL; bu altindaki bakiye "sifir" sayilir
SAPMA_ESIGI = 1.0       # %100 (cur > 2x onceki ortalama)
SAPMA_MIN_TUTAR = 100_000.0

# --- Ters bakiye icin beklenen yon ('+'=borc, '-'=alacak, None=kontrol etme) ---
ESNEK = {"131", "331", "193", "393", "136", "336", "690", "691", "692"}  # cift yonlu / sonuc
KONTRA_ALACAK = {"119", "122", "129", "137", "138", "158", "199",
                 "222", "232", "239", "247", "257", "268", "277", "278", "298"}  # kontra-aktif
KONTRA_BORC = {"501", "580", "591"}                                              # kontra-pasif/ozkaynak
GELIR6 = {"600", "601", "602", "640", "641", "642", "643", "644", "645",
          "646", "647", "648", "649", "671", "679"}
GIDER6 = {"610", "611", "612", "620", "621", "630", "631", "632", "653",
          "654", "655", "656", "657", "658", "659", "660", "661", "680", "681", "689"}
YANSITMA7 = {"711", "721", "731", "741", "751", "761", "771", "781", "791", "798"}
# Ay sonunda bakiye vermemesi gereken gecici hesaplar
KAPANMALI = {"191", "391", "196"} | YANSITMA7


def beklenen_yon(ana, ad=""):
    n = str(ana)[:3]
    if n in ESNEK:
        return None
    if n in KONTRA_ALACAK:
        return "-"
    if n in KONTRA_BORC:
        return "+"
    d = n[0] if n else ""
    # Hesap adinda "(-)" varsa kontra hesaptir: aktif grupta (1xx/2xx) alacak normaldir.
    if "(-)" in str(ad).replace(" ", "") and d in "12":
        return "-"
    if d in "12":
        return "+"
    if d in "345":
        return "-"
    if d == "7":
        return "-" if n in YANSITMA7 else "+"
    if d == "6":
        if n in GELIR6:
            return "-"
        if n in GIDER6:
            return "+"
    return None


def _yon_ad(yon):
    return "borç" if yon == "+" else "alacak"


def _karsi_bacak_ipucu(ana, cur):
    """Anormal hareketin muhtemel KARSI BACAGI (cift taraf kaydinda nereyi
    aramali). cur>0 = borc hareketi, cur<0 = alacak hareketi. Sadece ipucudur."""
    n = str(ana)[:3]
    d = n[:1]
    borc = cur > 0
    if d == "6":
        if n in GELIR6:
            return "satış karşılığı 120 Alıcılar / 102 Banka ve 391 Hesaplanan KDV"
        if n in GIDER6:
            return "gider karşılığı 320 Satıcılar / 102 Banka / 381 Gider Tahakkuku ve 191 İndirilecek KDV"
        return "ilgili gelir/gider karşı hesabı"
    if d == "7":
        return "gider tahakkuku 320 Satıcılar / 102 Banka / 360-361-381; ay sonu 7xx yansıtma (711/721…)"
    if d == "1":
        return ("tahsilat karşılığı 600 Satışlar / 120 Alıcılar / ilgili gelir" if not borc
                else "ödeme/çıkış karşılığı 102 Banka / 320 Satıcılar / 153 Stok")
    if d == "2":
        return "yatırım finansmanı 320 Satıcılar / 102 Banka / 300-400 Krediler (+191 İndirilecek KDV)"
    if d in "34":
        return ("yükümlülük ödemesi 102 Banka / 100 Kasa" if borc
                else "yükümlülük tahakkuku ilgili 6xx-7xx gider / 153 Stok / 320 Satıcılar")
    if d == "5":
        return "özkaynak hareketi 102 Banka / 331 Ortaklara Borçlar / 590-690 dönem sonucu"
    return "çift taraflı kayıt gereği ilgili karşı hesap"


def zorunlu_hesap_kontrol(mizan, zorunlu=None, tolerans=None):
    """Donem sonunda hareket/bakiye beklenen kontrol hesaplarini denetler.
    Hesap mizanda hic yoksa -> 'yok'; var ama hem bakiye hem bu ayki hareket
    tolerans altindaysa -> 'hareketsiz'. Ikisi de SOFT uyaridir (firmaya gore
    mesru olabilir; ayarlar.zorunlu_hesaplar ile listelenir)."""
    ayar = ayarlar.oku()
    if zorunlu is None:
        zorunlu = ayar.get("zorunlu_hesaplar", {})
    if tolerans is None:
        tolerans = ayar.get("zorunlu_hesap_tolerans", TOLERANS)
    guncel = mizan.get("guncel_ay")
    hesaplar = mizan["hesaplar"]
    bulgular = []
    for kod, etiket in zorunlu.items():
        o = hesaplar.get(str(kod)[:3])
        if o is None:
            bulgular.append({"ana": kod, "ad": etiket, "durum": "yok", "bakiye": 0.0,
                             "ac": f"{kod} {etiket}: mizanda HİÇ YOK — dönem sonunda bu hesabın "
                                   f"bulunması beklenir, kontrol edin."})
            continue
        bakiye = o.get("toplam", 0) or 0
        hareket = (o.get("aylik", {}).get(guncel, 0) or 0) if guncel else 0
        if abs(bakiye) <= tolerans and abs(hareket) <= tolerans:
            bulgular.append({"ana": kod, "ad": o.get("ad", "") or etiket, "durum": "hareketsiz",
                             "bakiye": bakiye,
                             "ac": f"{kod} {etiket}: dönem sonu bakiyesi ve {guncel or 'bu ay'} "
                                   f"hareketi yok — beklenmedik, kontrol edin."})
    return bulgular


def analiz_et(mizan, sapma_esigi=None, min_tutar=None):
    if sapma_esigi is None or min_tutar is None:
        ayar = ayarlar.oku()
        if sapma_esigi is None:
            sapma_esigi = (ayar.get("mizan_sapma_yuzde", 100) or 100) / 100.0
        if min_tutar is None:
            min_tutar = ayar.get("mizan_sapma_min_tutar", SAPMA_MIN_TUTAR)
    aylar = mizan["aylar"]
    guncel = mizan["guncel_ay"]
    hesaplar = mizan["hesaplar"]

    ters, sapma, gecici = [], [], []

    for ana, o in sorted(hesaplar.items()):
        toplam = o["toplam"]
        ad = o.get("ad", "")

        # 1) Ters bakiye
        yon = beklenen_yon(ana, ad)
        if yon == "+" and toplam < -TOLERANS:
            ters.append({"ana": ana, "ad": ad, "bakiye": toplam,
                         "beklenen": "borç", "gercek": "alacak",
                         "ac": f"{ana} {ad}: borç bakiye beklenir, {abs(toplam):,.2f} TL ALACAK bakiye veriyor."})
        elif yon == "-" and toplam > TOLERANS:
            ters.append({"ana": ana, "ad": ad, "bakiye": toplam,
                         "beklenen": "alacak", "gercek": "borç",
                         "ac": f"{ana} {ad}: alacak bakiye beklenir, {toplam:,.2f} TL BORÇ bakiye veriyor."})

        # 2) Anormal aylik sapma (en az 2 ay hareket varsa)
        if guncel and len(aylar) >= 2:
            cur = o["aylik"].get(guncel, 0) or 0
            onceki = [o["aylik"].get(a, 0) or 0 for a in aylar[:-1]]
            ort = sum(abs(v) for v in onceki) / len(onceki) if onceki else 0
            if abs(cur) >= min_tutar:
                ipucu = _karsi_bacak_ipucu(ana, cur)
                seri = [o["aylik"].get(a, 0) or 0 for a in aylar]
                if ort > TOLERANS:
                    katsayi = abs(cur) / ort
                    if katsayi - 1 >= sapma_esigi:
                        sapma.append({"ana": ana, "ad": ad, "guncel": cur, "ort_onceki": ort,
                                      "kat": katsayi, "karsi": ipucu, "seri": seri,
                                      "ac": f"{ana} {ad}: {guncel} hareketi {cur:,.2f} TL — "
                                            f"önceki ay ort. {ort:,.2f} TL'nin {katsayi:.1f} katı. "
                                            f"Karşı bacak: {ipucu}."})
                elif ort <= TOLERANS:
                    sapma.append({"ana": ana, "ad": ad, "guncel": cur, "ort_onceki": 0,
                                  "kat": None, "karsi": ipucu, "seri": seri,
                                  "ac": f"{ana} {ad}: önceki aylarda hareket yokken {guncel} ayında "
                                        f"{cur:,.2f} TL hareket — ani giriş. Karşı bacak: {ipucu}."})

        # 3) Kapanmamis gecici hesap
        if str(ana)[:3] in KAPANMALI and abs(toplam) > TOLERANS:
            gecici.append({"ana": ana, "ad": ad, "bakiye": toplam,
                           "ac": f"{ana} {ad}: dönem sonunda kapanmalı, {toplam:,.2f} TL bakiye veriyor "
                                 f"(mahsup/yansıtma yapılmamış olabilir)."})

    bulgular = {
        "ters": sorted(ters, key=lambda x: -abs(x["bakiye"])),
        "sapma": sorted(sapma, key=lambda x: -abs(x["guncel"])),
        "gecici": sorted(gecici, key=lambda x: -abs(x["bakiye"])),
        "bos_hesap": zorunlu_hesap_kontrol(mizan),
    }
    toplam_bulgu = sum(len(v) for v in bulgular.values())
    # Aylik hareket yogunlugu (goreli): her ay icin |net hareket| toplami.
    aylik_hareket = [round(sum(abs(o["aylik"].get(a, 0) or 0) for o in hesaplar.values()), 2)
                     for a in aylar]
    return {
        "kaynak": mizan["kaynak"], "format": mizan["format"],
        "aylar": aylar, "guncel_ay": guncel,
        "aylik_hareket": aylik_hareket,
        "hesap_sayisi": mizan["hesap_sayisi"], "satir_sayisi": mizan["satir_sayisi"],
        "bulgular": bulgular, "toplam_bulgu": toplam_bulgu,
        "esik": {"sapma_yuzde": int(sapma_esigi * 100), "min_tutar": min_tutar},
    }
