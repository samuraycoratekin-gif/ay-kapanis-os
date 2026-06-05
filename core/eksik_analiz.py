# -*- coding: utf-8 -*-
"""
Eksik Belge Avcisi motoru.

Mizandaki AYLIK hareket sutunlarini kullanarak "duzenli gelen ama bu donem
gelmemis" kalemleri yakalar: bir hesap onceki aylarda duzenli hareket etmis
ama kapanis ayinda durmussa, o belge bu ay eksik olabilir (kira/elektrik/
telefon/danismanlik gibi). EK DOSYA GEREKMEZ; M2 mizanindan beslenir.

Isaret kurali (mizan): pozitif = BORC, negatif = ALACAK.
"""

TOL = 100.0  # TL altindaki hareketler "yok" sayilir


SINIF_AD = {
    "6": "Gelir/Gider", "7": "Maliyet/Gider", "1": "Dönen Varlık",
    "2": "Duran Varlık", "3": "KV Yabancı Kaynak", "4": "UV Yabancı Kaynak",
    "5": "Özkaynak",
}

# Duzenli gider/maliyet hesap onekleri (borc bakiyeli)
GIDER_ONEK = ("62", "63", "65", "66", "68",
              "70", "71", "72", "73", "74", "75", "76", "77", "78", "79")
# Tahakkuk yukumlulukleri (her ay tekrarlayan): odenecek vergi/fon + SGK
YUKUMLULUK_AD = {
    "361": "Ödenecek Sosyal Güvenlik Kesintileri (SGK işçi+işveren)",
    "360": "Ödenecek Vergi ve Fonlar (gelir stopajı / damga)",
    "368": "Vadesi Geçmiş / Ertelenmiş Vergi ve Fonlar",
}
YUKUMLULUK_ONEK = tuple(YUKUMLULUK_AD)  # ("361", "360", "368")


def _kapanis_ayi(mizan):
    """Genel hareketi olan EN SON ayi (kapanis ayi) bulur."""
    aylar = mizan.get("aylar", [])
    h = mizan["hesaplar"]
    son = None
    for ay in aylar:
        toplam = sum(abs(o.get("aylik", {}).get(ay) or 0) for o in h.values())
        if toplam > TOL:
            son = ay
    return son


def duzenli_gider(mizan):
    aylar = mizan.get("aylar", [])
    h = mizan["hesaplar"]
    if len(aylar) < 3:
        return {"yeterli_veri": False, "aylar": len(aylar)}

    kapanis = _kapanis_ayi(mizan)
    if not kapanis:
        return {"yeterli_veri": False, "aylar": len(aylar)}
    onceki = aylar[:aylar.index(kapanis)]
    if len(onceki) < 2:
        return {"yeterli_veri": False, "aylar": len(aylar), "kapanis": kapanis}

    eksikler = []
    for ana, o in h.items():
        kod = str(ana)
        if not kod.startswith(GIDER_ONEK):
            continue
        vals = [o.get("aylik", {}).get(m) or 0 for m in onceki]
        nonzero = [v for v in vals if abs(v) > TOL]
        if len(nonzero) < max(2, round(len(onceki) * 0.5)):
            continue  # duzenli degil
        avg = sum(nonzero) / len(nonzero)
        cur = o.get("aylik", {}).get(kapanis) or 0
        if abs(cur) < max(TOL, abs(avg) * 0.15):
            eksikler.append({
                "ana": kod, "ad": o.get("ad", ""),
                "sinif": SINIF_AD.get(kod[:1], ""),
                "gecmis_ay": len(nonzero), "toplam_ay": len(onceki),
                "beklenen": abs(avg), "bu_ay": abs(cur),
            })

    eksikler.sort(key=lambda x: -x["beklenen"])
    toplam = sum(x["beklenen"] for x in eksikler)
    return {
        "yeterli_veri": True, "kapanis": kapanis, "gecmis_ay": len(onceki),
        "eksikler": eksikler, "toplam_beklenen": toplam,
    }


def _operasyon_aktif(h, ay):
    """Kapanis ayinda gider/maliyet hesaplarinda anlamli hareket var mi?
    (Isletme faal -> personel/SGK/stopaj tahakkuku da beklenir.)"""
    return sum(abs(o.get("aylik", {}).get(ay) or 0)
               for ana, o in h.items() if str(ana).startswith(GIDER_ONEK)) > TOL * 5


def tahakkuk_eksigi(mizan):
    """SGK/vergi tahakkuk kontrolu: 361/360/368 onceki aylarda duzenli tahakkuk
    etmis ama kapanis ayinda durmussa -> tahakkuk fisi unutulmus olabilir.
    Operasyon (gider hareketi) devam ediyorsa sinyal guclenir.
    Mizan disinda veri GEREKMEZ; ic tutarlilik kontroludur (kayit ONERILMEZ,
    yalnizca uyari) - son onay her zaman kullanicida."""
    aylar = mizan.get("aylar", [])
    h = mizan["hesaplar"]
    if len(aylar) < 3:
        return {"yeterli_veri": False, "aylar": len(aylar)}
    kapanis = _kapanis_ayi(mizan)
    if not kapanis:
        return {"yeterli_veri": False, "aylar": len(aylar)}
    onceki = aylar[:aylar.index(kapanis)]
    if len(onceki) < 2:
        return {"yeterli_veri": False, "aylar": len(aylar), "kapanis": kapanis}

    op_aktif = _operasyon_aktif(h, kapanis)
    eksikler = []
    for kod in YUKUMLULUK_ONEK:
        o = h.get(kod)
        if not o:
            continue
        vals = [o.get("aylik", {}).get(m) or 0 for m in onceki]
        nonzero = [v for v in vals if abs(v) > TOL]
        if len(nonzero) < max(2, round(len(onceki) * 0.5)):
            continue  # bu yukumluluk zaten duzenli degil -> tahakkuk beklenmez
        avg = sum(nonzero) / len(nonzero)
        cur = o.get("aylik", {}).get(kapanis) or 0
        if abs(cur) < max(TOL, abs(avg) * 0.15):
            eksikler.append({
                "ana": kod, "ad": o.get("ad", "") or YUKUMLULUK_AD.get(kod, ""),
                "tur": YUKUMLULUK_AD.get(kod, ""),
                "gecmis_ay": len(nonzero), "toplam_ay": len(onceki),
                "beklenen": abs(avg), "bu_ay": abs(cur), "op_aktif": op_aktif,
            })
    eksikler.sort(key=lambda x: -x["beklenen"])
    return {
        "yeterli_veri": True, "kapanis": kapanis, "gecmis_ay": len(onceki),
        "op_aktif": op_aktif, "eksikler": eksikler,
        "toplam_beklenen": sum(x["beklenen"] for x in eksikler),
    }
