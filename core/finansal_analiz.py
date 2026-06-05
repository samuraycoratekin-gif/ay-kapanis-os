# -*- coding: utf-8 -*-
"""
Finansal Analiz motoru - Bilanco + Gelir Tablosu + Oran ve Risk analizi.

Mizandan (core.mizan_oku.oku ciktisi) calisir; EK DOSYA GEREKMEZ.
TDHP hesap sinifina gore gruplar, donem (acilis->guncel) ve aylik
trend karsilastirmalari uretir, finansal/operasyonel riskleri isaretler.

Isaret kurali (mizan): pozitif = BORC bakiye, negatif = ALACAK bakiye.
  - Varlik (1,2)         : borc bakiye  -> pozitif normal
  - Yabanci kaynak (3,4) : alacak bakiye -> negatif; buyukluk = -toplam
  - Ozkaynak (5)         : alacak bakiye -> negatif; buyukluk = -toplam
  - Gelir (60,64,67)     : alacak       -> negatif; buyukluk = -toplam
  - Gider/maliyet (61,62,63,65,66,68): borc -> pozitif
"""
from datetime import date, datetime


def _grup(hesaplar, *onekler, alan="toplam"):
    """Verilen kod oneklerine uyan hesaplarin 'alan' degerini toplar (ham, isaretli)."""
    t = 0.0
    for ana, o in hesaplar.items():
        if any(str(ana).startswith(p) for p in onekler):
            t += o.get(alan, 0) or 0
    return t


def _aylik_grup(hesaplar, ay, *onekler):
    t = 0.0
    for ana, o in hesaplar.items():
        if any(str(ana).startswith(p) for p in onekler):
            t += (o.get("aylik", {}).get(ay) or 0)
    return t


# --------------------------------------------------------------------------- #
# BILANCO
# --------------------------------------------------------------------------- #
def bilanco(mizan, alan="toplam"):
    """alan='toplam' -> guncel kumule bakiye; alan='acilis' -> donem basi."""
    h = mizan["hesaplar"]
    donen = _grup(h, "1", alan=alan)
    duran = _grup(h, "2", alan=alan)
    kv_yk = -_grup(h, "3", alan=alan)
    uv_yk = -_grup(h, "4", alan=alan)
    ozkaynak = -_grup(h, "5", alan=alan)
    aktif = donen + duran
    pasif = kv_yk + uv_yk + ozkaynak
    return {
        "donen": donen, "duran": duran, "aktif": aktif,
        "kv_yk": kv_yk, "uv_yk": uv_yk, "ozkaynak": ozkaynak, "pasif": pasif,
        # alt kalemler (buyukluk)
        "hazir_degerler": _grup(h, "10", alan=alan),
        "menkul": _grup(h, "11", alan=alan),
        "ticari_alacak": _grup(h, "12", alan=alan),
        "diger_alacak": _grup(h, "13", alan=alan),
        "stok": _grup(h, "15", alan=alan),
        "maddi_duran": _grup(h, "25", alan=alan),
        "ticari_borc": -_grup(h, "32", alan=alan),
        "mali_borc_kv": -_grup(h, "30", alan=alan),
        "mali_borc_uv": -_grup(h, "40", alan=alan),
        "odenecek_vergi": -_grup(h, "36", alan=alan),
        "sermaye": -_grup(h, "50", alan=alan),
        "denge_farki": aktif - pasif,
    }


# --------------------------------------------------------------------------- #
# GELIR TABLOSU
# --------------------------------------------------------------------------- #
def _gt_hesapla(brut, satis_ind, smm, faal_gid, diger_gel, diger_gid,
                finansman, olagandisi_gel, olagandisi_gid):
    net_satis = brut - satis_ind
    brut_kar = net_satis - smm
    faaliyet_kari = brut_kar - faal_gid
    olagan_kar = faaliyet_kari + diger_gel - diger_gid - finansman
    donem_kari = olagan_kar + olagandisi_gel - olagandisi_gid
    return {
        "brut_satis": brut, "satis_ind": satis_ind, "net_satis": net_satis,
        "smm": smm, "brut_kar": brut_kar, "faal_gid": faal_gid,
        "faaliyet_kari": faaliyet_kari, "diger_gel": diger_gel, "diger_gid": diger_gid,
        "finansman": finansman, "olagan_kar": olagan_kar,
        "olagandisi_gel": olagandisi_gel, "olagandisi_gid": olagandisi_gid,
        "donem_kari": donem_kari,
    }


def gelir_tablosu(mizan, alan="toplam"):
    """7/A maliyet hesaplari (7x) yansitilmamissa (62x/63x/66x bos kalmissa)
    maliyetler 7x'te durur; geliri tablosunu dogru kurmak icin 7x net bakiyeleri
    de gider olarak alinir. Tam yansitma yapildiysa 7x net ~0 olur, cift sayim olmaz.
    SMM=62+(70-74), Faaliyet gid=63+(75,76,77,79), Finansman=66+78."""
    h = mizan["hesaplar"]
    return _gt_hesapla(
        brut=-_grup(h, "60", alan=alan),
        satis_ind=_grup(h, "61", alan=alan),
        smm=_grup(h, "62", "70", "71", "72", "73", "74", alan=alan),
        faal_gid=_grup(h, "63", "75", "76", "77", "79", alan=alan),
        diger_gel=-_grup(h, "64", alan=alan),
        diger_gid=_grup(h, "65", alan=alan),
        finansman=_grup(h, "66", "78", alan=alan),
        olagandisi_gel=-_grup(h, "67", alan=alan),
        olagandisi_gid=_grup(h, "68", alan=alan),
    )


def gelir_tablosu_aylik(mizan, ay):
    h = mizan["hesaplar"]
    return _gt_hesapla(
        brut=-_aylik_grup(h, ay, "60"),
        satis_ind=_aylik_grup(h, ay, "61"),
        smm=_aylik_grup(h, ay, "62", "70", "71", "72", "73", "74"),
        faal_gid=_aylik_grup(h, ay, "63", "75", "76", "77", "79"),
        diger_gel=-_aylik_grup(h, ay, "64"),
        diger_gid=_aylik_grup(h, ay, "65"),
        finansman=_aylik_grup(h, ay, "66", "78"),
        olagandisi_gel=-_aylik_grup(h, ay, "67"),
        olagandisi_gid=_aylik_grup(h, ay, "68"),
    )


# --------------------------------------------------------------------------- #
# ORANLAR
# --------------------------------------------------------------------------- #
def _bol(a, b):
    return (a / b) if b else None


def oranlar(b, gt):
    yabanci = b["kv_yk"] + b["uv_yk"]
    return {
        "cari_oran": _bol(b["donen"], b["kv_yk"]),
        "asit_test": _bol(b["donen"] - b["stok"], b["kv_yk"]),
        "nakit_oran": _bol(b["hazir_degerler"], b["kv_yk"]),
        "net_isletme_sermayesi": b["donen"] - b["kv_yk"],
        "borc_ozkaynak": _bol(yabanci, b["ozkaynak"]),
        "ozkaynak_aktif": _bol(b["ozkaynak"], b["aktif"]),
        "kaldirac": _bol(yabanci, b["aktif"]),
        "brut_kar_marji": _bol(gt["brut_kar"], gt["net_satis"]),
        "faaliyet_kar_marji": _bol(gt["faaliyet_kari"], gt["net_satis"]),
        "net_kar_marji": _bol(gt["donem_kari"], gt["net_satis"]),
    }


# --------------------------------------------------------------------------- #
# ALTMAN Z'-SCORE (ozel sermayeli firma modeli)
# --------------------------------------------------------------------------- #
def altman_z(mizan, b, gt):
    """Altman Z'-Score (private firm): iflas/finansal saglik skoru.
    Z' = 0.717*T1 + 0.847*T2 + 3.107*T3 + 0.420*T4 + 0.998*T5
      T1 = Net Isletme Sermayesi / Toplam Aktif
      T2 = Dagitilmamis karlar (gecmis yil + donem) / Toplam Aktif
      T3 = EBIT (olagan kar + finansman) / Toplam Aktif
      T4 = Ozkaynak / Toplam Borc (defter degeri)
      T5 = Net Satislar / Toplam Aktif
    Bolge: Z'>2.9 guvenli, 1.23-2.9 gri, <1.23 riskli (sıkıntı).
    Aktif veya toplam borc <=0 ise hesaplanamaz (None)."""
    h = mizan["hesaplar"]
    aktif = b["aktif"]
    yabanci = b["kv_yk"] + b["uv_yk"]
    if aktif <= 0 or yabanci <= 0:
        return {"hesaplanabilir": False}
    gecmis_kar = -_grup(h, "57") - _grup(h, "58")          # 570 kâr (−), 580 zarar (+)
    dagitilmamis = gecmis_kar + b.get("donem_kari", 0)
    ebit = gt["olagan_kar"] + gt["finansman"]              # faiz öncesi (vergi ayrı değil)
    T1 = (b["donen"] - b["kv_yk"]) / aktif
    T2 = dagitilmamis / aktif
    T3 = ebit / aktif
    T4 = b["ozkaynak"] / yabanci
    T5 = gt["net_satis"] / aktif
    z = round(0.717 * T1 + 0.847 * T2 + 3.107 * T3 + 0.420 * T4 + 0.998 * T5, 2)
    if z > 2.9:
        zon, etiket = "guvenli", "Güvenli Bölge"
    elif z >= 1.23:
        zon, etiket = "gri", "Gri Bölge (izlenmeli)"
    else:
        zon, etiket = "riskli", "Sıkıntı Bölgesi (yüksek risk)"
    return {
        "hesaplanabilir": True, "z": z, "zon": zon, "etiket": etiket,
        "bilesenler": {"T1": round(T1, 3), "T2": round(T2, 3), "T3": round(T3, 3),
                       "T4": round(T4, 3), "T5": round(T5, 3)},
    }


# --------------------------------------------------------------------------- #
# RISKLER
# --------------------------------------------------------------------------- #
def riskler(b, gt, o):
    r = []

    def ekle(seviye, baslik, mesaj):
        r.append({"seviye": seviye, "baslik": baslik, "mesaj": mesaj})

    # Ozkaynak / TTK 376
    if b["ozkaynak"] < 0:
        ekle("kritik", "Teknik İflas (TTK 376)",
             "Özkaynaklar NEGATİF. Şirket teknik iflas durumunda — yönetim kurulu "
             "derhal genel kurulu toplamak ve tedbir almakla yükümlü.")
    elif b["sermaye"] > 0 and b["ozkaynak"] < b["sermaye"] / 2:
        ekle("kritik", "Sermaye Erimesi (TTK 376)",
             "Özkaynaklar, ödenmiş sermayenin yarısının ALTINDA. TTK 376 kapsamında "
             "sermaye kaybı bildirimi ve iyileştirme planı gerekir.")
    elif b["sermaye"] > 0 and b["ozkaynak"] < b["sermaye"] * 2 / 3:
        ekle("uyari", "Sermaye Aşınması",
             "Özkaynaklar sermayenin 2/3'ünün altına indi — yakından izlenmeli.")

    # Likidite
    if o["cari_oran"] is not None:
        if o["cari_oran"] < 1:
            ekle("kritik", "Likidite Yetersiz (Cari Oran < 1)",
                 f"Cari oran {o['cari_oran']:.2f}. Kısa vadeli borçlar dönen varlıkları "
                 "aşıyor; ödeme güçlüğü riski.")
        elif o["cari_oran"] < 1.5:
            ekle("uyari", "Likidite Sınırda",
                 f"Cari oran {o['cari_oran']:.2f} (ideal ≥1,5). Nakit yönetimi izlenmeli.")
    if o["asit_test"] is not None and o["asit_test"] < 0.8:
        ekle("uyari", "Asit-Test Düşük",
             f"Asit-test oranı {o['asit_test']:.2f} (<0,80). Stok hariç likidite zayıf.")
    if o["net_isletme_sermayesi"] < 0:
        ekle("kritik", "Negatif İşletme Sermayesi",
             "Net işletme sermayesi negatif — kısa vadeli yükümlülükler dönen varlıkların "
             "üzerinde; rotatif finansman bağımlılığı.")

    # Kaldirac
    if o["borc_ozkaynak"] is not None and b["ozkaynak"] > 0:
        if o["borc_ozkaynak"] > 3:
            ekle("kritik", "Aşırı Borçluluk",
                 f"Borç/Özkaynak {o['borc_ozkaynak']:.2f} (>3). Çok yüksek finansal kaldıraç.")
        elif o["borc_ozkaynak"] > 2:
            ekle("uyari", "Yüksek Kaldıraç",
                 f"Borç/Özkaynak {o['borc_ozkaynak']:.2f} (>2). Borç yükü yüksek.")

    # Karlilik
    if gt["net_satis"] > 0:
        if gt["donem_kari"] < 0:
            ekle("kritik", "Dönem Zararı",
                 "Şirket dönem zararında — kârlılık ve gider yapısı acilen gözden geçirilmeli.")
        elif o["faaliyet_kar_marji"] is not None and o["faaliyet_kar_marji"] < 0:
            ekle("uyari", "Faaliyet Zararı",
                 "Esas faaliyet zarar üretiyor; kâr sadece faaliyet dışı kalemlerden geliyor.")
        if (gt["net_satis"] and gt["finansman"] / gt["net_satis"] > 0.1):
            ekle("uyari", "Yüksek Finansman Gideri",
                 f"Finansman gideri net satışın %{gt['finansman']/gt['net_satis']*100:.0f}'ı — "
                 "faiz yükü kârlılığı baskılıyor.")

    # Gelir tablosu donem kari, bilanco donem sonucuyla uyumlu mu?
    sapma = b.get("gt_sapma", 0)
    taban = abs(b.get("donem_kari", 0)) or abs(gt["net_satis"]) or 1
    if abs(sapma) > max(1.0, taban * 0.01):
        ekle("uyari", "Gelir Tablosu — Bilanço Sapması",
             f"Bilançodan çıkan dönem sonucu ile gelir tablosu kârı arasında "
             f"{sapma:,.0f} TL fark var. Sınıflanmamış hesap (ör. 7/A maliyet 7xx veya "
             "69x dönem kârı hesabı) ya da yansıtma eksikliği olabilir; gelir tablosu "
             "kalemleri kontrol edilmeli.")

    if not r:
        ekle("iyi", "Belirgin Risk Yok",
             "Temel finansal göstergeler sağlıklı aralıkta görünüyor.")
    return r


def _yuzde_degisim(yeni, eski):
    if not eski:
        return None
    return (yeni - eski) / abs(eski) * 100


# --------------------------------------------------------------------------- #
# TUM ANALIZ
# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# NAKIT AKIS ONGORUSU (ileriye donuk likidite projeksiyonu)
# Kaynak: senet/cek vadeleri (gercek vade tarihleri) + baslangic nakit (mizan 10).
# Cari yaslandirma EK BAGLAM olarak gosterilir (kesin vade yok, projeksiyona
# katilmaz). Senet alacak = nakit girisi, borc = nakit cikisi.
# --------------------------------------------------------------------------- #
NAKIT_KOVA = [("gecikmis", "Vadesi geçmiş"), ("0-7", "Bu hafta (0-7 gün)"),
              ("8-30", "8-30 gün"), ("31-60", "31-60 gün"),
              ("61-90", "61-90 gün"), ("90+", "90+ gün")]


def _tarihe(v):
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v or "").strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y.%m.%d"):
        try:
            return datetime.strptime(s[:10], fmt).date()
        except ValueError:
            continue
    return None


def _nakit_kova(gun):
    if gun < 0:
        return "gecikmis"
    if gun <= 7:
        return "0-7"
    if gun <= 30:
        return "8-30"
    if gun <= 60:
        return "31-60"
    if gun <= 90:
        return "61-90"
    return "90+"


def nakit_akis_ongoru(baslangic_nakit, senetler, cari_yas=None, bugun=None):
    """Senet/cek vadelerinden ileriye donuk nakit projeksiyonu uretir.
    Her vade kovasinda giris (alacak) - cikis (borc) = net; baslangic nakitten
    baslayarak kumulatif bakiye yurutulur. Bakiye herhangi bir kovada negatife
    duserse likidite acigi uyarisi verir."""
    if bugun is None:
        bugun = date.today()
    elif not isinstance(bugun, date):
        bugun = _tarihe(bugun) or date.today()

    from core import takvim
    kovalar = {k: {"giris": 0.0, "cikis": 0.0} for k, _ in NAKIT_KOVA}
    tatil_kaymasi = 0          # vadesi hafta sonu/tatile denk gelip kayan senet
    tatil_yaklasik = False     # vade yili dini-bayram listesinde yoksa True
    for s in (senetler or []):
        vade = _tarihe(s.get("vade"))
        if vade is None:
            continue
        # Vade tatile/hafta sonuna denk gelirse tahsilat/odeme sonraki is gununde:
        efektif, kaydi = takvim.kaydir(vade)
        if kaydi:
            tatil_kaymasi += 1
        if not takvim.dini_kapsam_var(vade):
            tatil_yaklasik = True
        kv = _nakit_kova((efektif - bugun).days)
        tutar = abs(s.get("tutar", 0) or 0)
        if s.get("tip") == "borc":
            kovalar[kv]["cikis"] = round(kovalar[kv]["cikis"] + tutar, 2)
        else:
            kovalar[kv]["giris"] = round(kovalar[kv]["giris"] + tutar, 2)

    bakiye = round(baslangic_nakit or 0, 2)
    satirlar, en_dusuk, en_dusuk_kova = [], bakiye, None
    for k, et in NAKIT_KOVA:
        g, c = kovalar[k]["giris"], kovalar[k]["cikis"]
        net = round(g - c, 2)
        bakiye = round(bakiye + net, 2)
        if bakiye < en_dusuk:
            en_dusuk, en_dusuk_kova = bakiye, et
        satirlar.append({"kova": k, "etiket": et, "giris": g, "cikis": c,
                         "net": net, "bakiye": bakiye})

    toplam_giris = round(sum(s["giris"] for s in satirlar), 2)
    toplam_cikis = round(sum(s["cikis"] for s in satirlar), 2)

    cari_ozet = None
    if cari_yas:
        cari_ozet = {"acik_alacak": round(cari_yas.get("toplam", 0) or 0, 2),
                     "vadesi_gecen": round(cari_yas.get("vadesi_gecen", 0) or 0, 2)}

    uyarilar = []
    if (en_dusuk or 0) < 0:
        uyarilar.append(f"Projeksiyonda nakit bakiye {en_dusuk_kova or 'bir dönem'} "
                        f"sonunda {en_dusuk:,.2f} TL'ye kadar düşüyor — likidite açığı riski. "
                        f"Tahsilatı öne çekin veya ödemeleri yeniden planlayın.")

    return {
        "hesaplanabilir": bool(senetler) or bool(cari_yas),
        "senet_var": bool(senetler),
        "bugun": bugun.isoformat(),
        "baslangic": round(baslangic_nakit or 0, 2),
        "satirlar": satirlar,
        "toplam_giris": toplam_giris, "toplam_cikis": toplam_cikis,
        "net": round(toplam_giris - toplam_cikis, 2),
        "bitis": bakiye, "en_dusuk": en_dusuk,
        "cari": cari_ozet, "uyarilar": uyarilar,
        "tatil_kaymasi": tatil_kaymasi, "tatil_yaklasik": tatil_yaklasik,
    }


def analiz(mizan):
    b_guncel = bilanco(mizan, "toplam")
    b_acilis = bilanco(mizan, "acilis")
    gt_donem = gelir_tablosu(mizan, "toplam")

    # Kapanis-oncesi mizanda donem sonucu hala 6/7 hesaplarinda durur, ozkaynaga
    # aktarilmamistir. Mizanin borc=alacak ozdesligi geregi donem net sonucu tam
    # olarak (Aktif - kapanis-oncesi Pasif) kadardir; bunu ozkaynaga ekleyince
    # bilanco daima denklesir.
    pasif_oncesi = b_guncel["pasif"]
    donem_sonucu = b_guncel["aktif"] - pasif_oncesi
    b_guncel["donem_kari"] = donem_sonucu
    b_guncel["ozkaynak"] += donem_sonucu
    b_guncel["pasif"] += donem_sonucu
    b_guncel["denge_farki"] = b_guncel["aktif"] - b_guncel["pasif"]
    # Bilanco donem sonucu ile gelir tablosu donem kari arasindaki sapma:
    # buyukse 7/A maliyet (7x) veya 69x gibi siniflanmamis hesap var demektir.
    b_guncel["gt_sapma"] = donem_sonucu - gt_donem["donem_kari"]

    o = oranlar(b_guncel, gt_donem)
    rsk = riskler(b_guncel, gt_donem, o)
    altman = altman_z(mizan, b_guncel, gt_donem)

    # bilanco donem karsilastirmasi (acilis -> guncel)
    bil_karsilastir = {}
    for k in ("donen", "duran", "aktif", "kv_yk", "uv_yk", "ozkaynak"):
        bil_karsilastir[k] = {
            "guncel": b_guncel[k], "acilis": b_acilis[k],
            "degisim": b_guncel[k] - b_acilis[k],
            "yuzde": _yuzde_degisim(b_guncel[k], b_acilis[k]),
        }

    # aylik gelir tablosu trendi
    aylar = mizan.get("aylar", [])
    aylik_trend = []
    for ay in aylar:
        g = gelir_tablosu_aylik(mizan, ay)
        aylik_trend.append({"ay": ay, "net_satis": g["net_satis"],
                            "brut_kar": g["brut_kar"], "donem_kari": g["donem_kari"]})

    # son ay vs onceki aylar ortalamasi
    ay_kiyas = None
    dolu = [a for a in aylik_trend if abs(a["net_satis"]) > 0.5]
    if len(dolu) >= 2:
        son = dolu[-1]
        onceki = dolu[:-1]
        ort_satis = sum(a["net_satis"] for a in onceki) / len(onceki)
        ort_kar = sum(a["donem_kari"] for a in onceki) / len(onceki)
        ay_kiyas = {
            "son_ay": son["ay"],
            "son_satis": son["net_satis"], "ort_satis": ort_satis,
            "satis_yuzde": _yuzde_degisim(son["net_satis"], ort_satis),
            "son_kar": son["donem_kari"], "ort_kar": ort_kar,
            "kar_yuzde": _yuzde_degisim(son["donem_kari"], ort_kar),
        }

    kritik = sum(1 for x in rsk if x["seviye"] == "kritik")
    uyari = sum(1 for x in rsk if x["seviye"] == "uyari")

    return {
        "bilanco": b_guncel, "bilanco_acilis": b_acilis,
        "gelir_tablosu": gt_donem, "oranlar": o, "riskler": rsk,
        "altman": altman,
        "bilanco_karsilastir": bil_karsilastir,
        "aylik_trend": aylik_trend, "ay_kiyas": ay_kiyas,
        "guncel_ay": mizan.get("guncel_ay"), "aylar": aylar,
        "kritik_sayisi": kritik, "uyari_sayisi": uyari,
    }
