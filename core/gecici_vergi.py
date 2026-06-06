# -*- coding: utf-8 -*-
"""
Gecici Vergi (Kurum) hazirlik & matrah motoru.

Ceyrek kapanis mizanindan (kumulatif) ticari kar/zarari alir; musavirin
girdigi/onayladigi KKEG + indirim kalemleriyle matrahi ve odenecek gecici
vergiyi uretir. Enflasyon modulunun sira=8 slotunu devralir.

ILK SURUM KAPSAMI: yalnizca KURUMLAR gecici vergisi (sabit %25 oran).
Gelir vergisi gecici (dilimli %15...) sonraki surume birakildi.

Dogrulama (AGB Kutu Imalat Ltd, ornek beyannameler):
  Kurumlar 2025 yillik:
    ticari = -343.064,34 ; KKEG = 573.303,06
    matrah = 230.238,72 ; x%25 = 57.559,68 ; asgari x%10 = 23.023,87
    nihai = MAX(57.559,68 ; 23.023,87) = 57.559,68
  Gecici 2026/1:
    ticari = -181.481,71 ; KKEG = 163.663,81
    matrah_ham = -17.817,90 -> negatif -> matrah 0 -> vergi 0

ANA ILKE: motor fis ATMAZ; tahakkuk fisi 691/370 yalnizca ONERIDIR,
onay/kayit musavirde. KKEG tam-otomatik degil: motor aday isaretler,
tutari musavir girer/onaylar.
"""

# Kurumlar gecici vergi oranlari (2025+). Mevzuat degisirse guncellenir;
# parametrik tutuldu (ayarlar.py'den override edilebilir hale getirilebilir).
ORAN_KURUMLAR = 0.25
ORAN_ASGARI = 0.10          # Yurt Ici Asgari Kurumlar/Gecici Vergi (2025+)
# Damga vergisi beyanname basina sabit tutar (GIB yillik belirler -> parametrik).
DAMGA_GECICI = 1085.20
DAMGA_KURUMLAR = 2516.30

# Ceyrek -> kumulatif kapsanan ay sayisi (matrah kumulatif uretildigi icin bilgi amacli).
CEYREK_AY = {1: 3, 2: 6, 3: 9}


def _r(v):
    return round(float(v or 0), 2)


# --------------------------------------------------------------------------- #
# KKEG aday avcisi (mizandan) -- yari otomatik: motor isaretler, musavir onaylar
# --------------------------------------------------------------------------- #
# GIB beyanname bucket yapisina gore aday gruplari. Anahtar kelimeler hesap
# ADINDA aranir (mizan_oku her hesap icin "ad" tasir). Tutar = hesap bakiyesi
# (borc bakiye pozitif). Bunlar ADAYDIR; nihai KKEG'i musavir onaylar.
_KKEG_DESEN = [
    ("gvk40_binek", "GVK 40 Binek Otomobil Gider/Amortisman/Kira Kisitlamasi",
     ("binek", "otomobil", "tasit gider", "arac kira", "arac kira")),
    ("kvk11_genel", "KVK m.11 Genel KKEG",
     ("kkeg", "kanunen kabul", "mtv", "motorlu tasit", "ozel iletisim",
      "ceza", "gecikme zamm", "gecikme faiz", "bagis", "bağış", "trafik")),
    ("fgk", "Finansman Gider Kisitlamasi (KVK 11/1-i)",
     ("finansman gider kisit", "fgk")),
]


def kkeg_adaylari(mizan):
    """Mizandaki hesaplari tarayip KKEG bucket adaylarini cikarir.
    Donus: bucket koduna gore aday hesap listesi + bucket toplami.
    NOT: bu yalnizca ONERIDIR; tutarlari musavir girer/onaylar."""
    h = mizan.get("hesaplar", {})
    sonuc = {kod: {"ad": ad, "kalemler": [], "toplam": 0.0}
             for kod, ad, _ in _KKEG_DESEN}
    for ana, o in h.items():
        adi = (o.get("ad") or "").lower()
        if not adi:
            continue
        bakiye = _r(o.get("toplam"))
        if abs(bakiye) < 1.0:
            continue
        for kod, _ad, kelimeler in _KKEG_DESEN:
            if any(k in adi for k in kelimeler):
                sonuc[kod]["kalemler"].append(
                    {"hesap": str(ana), "ad": o.get("ad", ""), "bakiye": bakiye})
                sonuc[kod]["toplam"] = _r(sonuc[kod]["toplam"] + bakiye)
                break
    return sonuc


# --------------------------------------------------------------------------- #
# Matrah & vergi motoru (pure)
# --------------------------------------------------------------------------- #
def hesapla(ticari_kar, kkeg=0.0, istisna=0.0, gecmis_zarar=0.0,
            onceki_hesaplanan=0.0, pesin_odenen=0.0,
            oran=ORAN_KURUMLAR, asgari_oran=ORAN_ASGARI,
            asgari_matrah=None, damga=DAMGA_GECICI):
    """Kurumlar gecici vergi matrahi ve odenecek vergiyi hesaplar.

    matrah = max(0, ticari_kar + kkeg - istisna - gecmis_zarar)
    normal_vergi = matrah * oran
    asgari_vergi = (asgari_matrah or matrah) * asgari_oran     (2025+ zorunlu)
    hesaplanan   = MAX(normal_vergi, asgari_vergi)
    odenecek     = max(0, hesaplanan - onceki_hesaplanan - pesin_odenen) + damga

    onceki_hesaplanan: ayni yil onceki gecici donem(ler)de hesaplanan vergi
                       (kumulatif matrah mantigi -> mahsup).
    pesin_odenen     : donem ici kesilen stopaj/tevkifat (193 vb.).
    """
    ticari_kar = _r(ticari_kar)
    kkeg = _r(kkeg)
    istisna = _r(istisna)
    gecmis_zarar = _r(gecmis_zarar)
    onceki_hesaplanan = _r(onceki_hesaplanan)
    pesin_odenen = _r(pesin_odenen)

    matrah_ham = _r(ticari_kar + kkeg - istisna - gecmis_zarar)
    matrah = _r(max(0.0, matrah_ham))

    # Asgari matrah verilmezse matrah baz alinir (AGB ornegi ile dogrulandi).
    # Gercek asgari matrahta bazi indirim/istisnalar dislanir -> gercek mizanla
    # kalibre edilecek; simdilik parametre + varsayilan=matrah.
    a_matrah = _r(asgari_matrah) if asgari_matrah is not None else matrah

    normal_vergi = _r(matrah * oran)
    asgari_vergi = _r(a_matrah * asgari_oran)
    hesaplanan = _r(max(normal_vergi, asgari_vergi))
    asgari_baglayici = asgari_vergi > normal_vergi and matrah > 0

    mahsup_sonrasi = _r(max(0.0, hesaplanan - onceki_hesaplanan - pesin_odenen))
    damga = _r(damga)
    odenecek = _r(mahsup_sonrasi + damga)

    return {
        "ticari_kar": ticari_kar,
        "kkeg": kkeg, "istisna": istisna, "gecmis_zarar": gecmis_zarar,
        "matrah_ham": matrah_ham, "matrah": matrah,
        "matrah_negatif": matrah_ham < 0,
        "oran": oran, "asgari_oran": asgari_oran,
        "asgari_matrah": a_matrah,
        "normal_vergi": normal_vergi, "asgari_vergi": asgari_vergi,
        "hesaplanan": hesaplanan, "asgari_baglayici": asgari_baglayici,
        "onceki_hesaplanan": onceki_hesaplanan, "pesin_odenen": pesin_odenen,
        "mahsup_sonrasi": mahsup_sonrasi,
        "damga": damga, "odenecek": odenecek,
    }


# --------------------------------------------------------------------------- #
# Ters-mutabakat: musavirin beyan ettigi matrah ile motorun urettigi matrah
# --------------------------------------------------------------------------- #
def ters_mutabakat(motor_matrah, beyan_matrah, tol=1.0):
    """Beyan edilecek matrah ile mizandan uretilen matrahi karsilastirir.
    Yanlis beyani GONDERMEDEN once yakalamak icin (Mutabakat urunu DNA'si)."""
    if beyan_matrah is None:
        return {"karsilastirildi": False}
    fark = _r(motor_matrah - _r(beyan_matrah))
    return {
        "karsilastirildi": True,
        "motor_matrah": _r(motor_matrah),
        "beyan_matrah": _r(beyan_matrah),
        "fark": fark,
        "uyumlu": abs(fark) <= tol,
    }


# --------------------------------------------------------------------------- #
# Ceyrek bilgisi (donem ayindan)
# --------------------------------------------------------------------------- #
def ceyrek_bilgi(donem):
    """donem 'YYYY-MM' -> ait oldugu gecici vergi ceyregi bilgisi."""
    ay = int(donem[5:7])
    if 1 <= ay <= 3:
        c, ad, kapanis = 1, "1. Dönem (Oca-Mar)", (ay == 3)
    elif 4 <= ay <= 6:
        c, ad, kapanis = 2, "2. Dönem (Nis-Haz)", (ay == 6)
    elif 7 <= ay <= 9:
        c, ad, kapanis = 3, "3. Dönem (Tem-Eyl)", (ay == 9)
    else:
        c, ad, kapanis = None, "4. çeyrek (geçici dönem kaldırıldı → yıllık)", False
    return {"ceyrek": c, "ad": ad, "kapanis_ayi": kapanis,
            "kapsanan_ay": CEYREK_AY.get(c)}


# --------------------------------------------------------------------------- #
# Tahakkuk fisi ONERISI (691/370) -- motor atmaz, M6'ya akar, onay musavirde
# --------------------------------------------------------------------------- #
def fis_onerisi(odenecek_kurumlar_vergisi):
    """Donem gecici vergi tahakkuk fisi onerisi: 691 (borc) / 370 (alacak).
    Damga haric, kurumlar gecici vergi tahakkuku."""
    v = _r(odenecek_kurumlar_vergisi)
    if v <= 0:
        return None
    return {
        "aciklama": "Dönem kârı vergi karşılığı (geçici vergi tahakkuku)",
        "satirlar": [
            {"hesap": "691", "ad": "Dönem Kârı Vergi ve Diğer Yasal Yük. Karşılığı",
             "borc": v, "alacak": 0.0},
            {"hesap": "370", "ad": "Dönem Kârı Vergi ve Diğer Yasal Yük. Karşılığı",
             "borc": 0.0, "alacak": v},
        ],
        "toplam": v,
    }
