# -*- coding: utf-8 -*-
"""
Stok & Maliyet kontrolu - analiz motoru (mizandan beslenir, ek yukleme YOK).

17 yil AP muhasebe deneyimiyle onaylanan, sadece mizandan turetilebilen kontroller:

  1) Negatif stok bakiyesi : 150-157 stok hesaplari ALACAK bakiye veriyorsa fiziksel
                             olarak imkansiz -> maliyet/sayim/giris-cikis hatasi.
  2) Maliyet-satis uyumu   : Brut kar marji = (net satis - SMM) / net satis.
                             Marj < alt esik (zararina satis) ya da > ust esik
                             (SMM eksik kaydi) -> uyari. Satis var-maliyet yok / tersi
                             durumlari da yakalanir (SMM fisi kesilmemis).
  3) Atil / yavas stok     : Donem sonu ticari stok / aylik ort. SMM = kac aylik stok.
                             Esigi asarsa olu/atil stok suphesi (deger dususu karsiligi?).
  4) Kontra 158 kontrolu   : 158 Stok Deger Dususu Karsiligi (-) borc bakiye veriyorsa ters.
  5) Acik siparis avansi   : 159 Verilen Siparis Avanslari bakiyesi -> mal girisi/mahsup
                             bekleyen avans (izlenecek; tek basina hata degil).

Isaret kurali: pozitif = borc bakiye, negatif = alacak bakiye (mizan_oku ile ayni).
"""
from core import ayarlar

TOLERANS = 1.0

STOK_HESAPLAR = ["150", "151", "152", "153", "157"]   # borc bakiye beklenir
TICARI_STOK = ["150", "151", "152", "153"]            # devir hesabina giren stok
SMM_HESAPLAR = ["620", "621", "622"]                  # borc (gider)
SATIS_HESAPLAR = ["600", "601", "602"]                # alacak (gelir)
SATIS_INDIRIM = ["610", "611", "612"]                 # borc (satistan dusulur)

AD_TABLO = {
    "150": "İlk Madde ve Malzeme", "151": "Yarı Mamuller", "152": "Mamuller",
    "153": "Ticari Mallar", "157": "Diğer Stoklar",
    "158": "Stok Değer Düşüklüğü Karşılığı (-)", "159": "Verilen Sipariş Avansları",
    "620": "Satılan Mamul Maliyeti", "621": "Satılan Ticari Mallar Maliyeti",
    "622": "Satılan Hizmet Maliyeti",
}


def _esikler():
    a = ayarlar.oku()
    return (float(a.get("stok_brut_kar_alt_yuzde", 0.0)),
            float(a.get("stok_brut_kar_ust_yuzde", 85.0)),
            float(a.get("stok_devir_ay_esik", 12.0)),
            float(a.get("stok_min_tutar", 1000.0)))


def _bakiye(hesaplar, ana):
    o = hesaplar.get(ana)
    return (o.get("toplam", 0.0) or 0.0) if o else 0.0


def _ad(hesaplar, ana):
    o = hesaplar.get(ana)
    return (o.get("ad") if o and o.get("ad") else AD_TABLO.get(ana, ana))


def analiz_et(mizan):
    alt_y, ust_y, devir_esik, min_tutar = _esikler()
    h = mizan["hesaplar"]
    aylar = mizan.get("aylar") or []
    ay_sayisi = max(1, len(aylar))

    negatif, satis_uyari, atil, kontra, avans = [], [], [], [], []

    # 1) Negatif stok
    for ana in STOK_HESAPLAR:
        b = _bakiye(h, ana)
        if b < -TOLERANS:
            negatif.append({"ana": ana, "ad": _ad(h, ana), "bakiye": b,
                            "ac": f"{ana} {_ad(h, ana)}: {abs(b):,.2f} TL ALACAK (negatif) bakiye — "
                                  f"fiziksel olarak imkânsız; maliyet/giriş-çıkış veya sayım hatası."})

    # 2) Maliyet-satis uyumu (brut kar marji)
    brut_satis = -sum(_bakiye(h, a) for a in SATIS_HESAPLAR)       # alacak -> pozitif gelir
    indirim = sum(_bakiye(h, a) for a in SATIS_INDIRIM)           # borc -> dusulur
    net_satis = brut_satis - indirim
    smm = sum(_bakiye(h, a) for a in SMM_HESAPLAR)                # borc -> pozitif maliyet
    marj = None
    if net_satis > min_tutar and smm > min_tutar:
        marj = (net_satis - smm) / net_satis * 100.0
        if marj < alt_y:
            satis_uyari.append({"tip": "zarar", "marj": marj,
                                "ac": f"Brüt kâr marjı %{marj:.1f} — zararına satış görünümü "
                                      f"(net satış {net_satis:,.2f} TL < SMM {smm:,.2f} TL). "
                                      f"Maliyet fazla mı kaydedilmiş, fiyatlama mı hatalı?"})
        elif marj > ust_y:
            satis_uyari.append({"tip": "maliyet_eksik", "marj": marj,
                                "ac": f"Brüt kâr marjı %{marj:.1f} (eşik %{ust_y:.0f}) — olağandışı yüksek; "
                                      f"satılan malın maliyeti (SMM) eksik kaydedilmiş olabilir."})
    elif net_satis > min_tutar and smm <= min_tutar:
        satis_uyari.append({"tip": "maliyet_yok", "marj": None,
                            "ac": f"Net satış {net_satis:,.2f} TL var ancak satılan mal maliyeti (620/621/622) "
                                  f"işlenmemiş — SMM/maliyet fişi kesilmemiş olabilir."})
    elif smm > min_tutar and net_satis <= min_tutar:
        satis_uyari.append({"tip": "satis_yok", "marj": None,
                            "ac": f"Satılan mal maliyeti {smm:,.2f} TL var ancak satış geliri (600/601/602) "
                                  f"görünmüyor — satış kaydı eksik olabilir."})

    # 3) Atil / yavas stok (kac aylik stok)
    donem_stok = sum(max(_bakiye(h, a), 0.0) for a in TICARI_STOK)
    aylik_smm = smm / ay_sayisi if smm > 0 else 0.0
    ay_stok = None
    if donem_stok > min_tutar:
        if aylik_smm > TOLERANS:
            ay_stok = donem_stok / aylik_smm
            if ay_stok > devir_esik:
                atil.append({"ay": ay_stok, "stok": donem_stok,
                             "ac": f"Dönem sonu ticari stok {donem_stok:,.2f} TL ≈ {ay_stok:.1f} aylık satış "
                                   f"(eşik {devir_esik:.0f} ay) — yavaş devreden/atıl stok; "
                                   f"değer düşüklüğü karşılığı (158) gerekebilir."})
        else:
            atil.append({"ay": None, "stok": donem_stok,
                         "ac": f"Dönem sonu ticari stok {donem_stok:,.2f} TL var ancak dönem içi satış "
                               f"maliyeti (SMM) yok — stok hiç dönmüyor; durağan/ölü stok şüphesi."})

    # 4) Kontra 158
    b158 = _bakiye(h, "158")
    if b158 > TOLERANS:
        kontra.append({"ana": "158", "ad": _ad(h, "158"), "bakiye": b158,
                       "ac": f"158 {_ad(h, '158')}: kontra hesap, alacak bakiye beklenir; "
                             f"{b158:,.2f} TL BORÇ bakiye veriyor — ters kayıt."})

    # 5) Acik siparis avansi (159) - izlenecek
    b159 = _bakiye(h, "159")
    if b159 > min_tutar:
        avans.append({"ana": "159", "ad": _ad(h, "159"), "bakiye": b159,
                      "ac": f"159 {_ad(h, '159')}: {b159:,.2f} TL açık avans — mal girişi/mahsup "
                            f"bekleyen sipariş avansı; dönem sonunda kapanması beklenir."})

    bulgular = {"negatif": negatif, "satis": satis_uyari, "atil": atil,
                "kontra": kontra, "avans": avans}
    toplam = sum(len(v) for v in bulgular.values())
    return {
        "bulgular": bulgular, "toplam_bulgu": toplam,
        "ozet": {
            "net_satis": round(net_satis, 2), "smm": round(smm, 2),
            "brut_kar": round(net_satis - smm, 2),
            "marj": (round(marj, 1) if marj is not None else None),
            "donem_stok": round(donem_stok, 2),
            "ay_stok": (round(ay_stok, 1) if ay_stok is not None else None),
        },
        "stok_var": any(h.get(a) for a in STOK_HESAPLAR),
    }
