# -*- coding: utf-8 -*-
"""
KDV & e-Fatura analizi.

1) mizandan_kdv(mizan): Yuklenen mizandan (M2 ile ayni dosya) KDV pozisyonunu
   ve beyanname taslagini cikarir. Ek yukleme gerekmez.
     191 Indirilecek KDV  (donem hareketi)
     391 Hesaplanan KDV   (donem hareketi)
     190 Devreden KDV     (onceki donemden, acilis bakiyesi)
     360 Odenecek Vergi/Fonlar (kumule bakiye)
   Hesap: Hesaplanan - (Indirilecek + Onceki Devreden)
          > 0  -> Odenecek KDV
          <= 0 -> Sonraki doneme devreden KDV
   Kontroller: 191/391 ay sonunda kapanmamissa (mahsup fisi kesilmemis) uyarir.

2) gib_karsilastir(gib_kayit, defter_kayit): GIB e-Fatura listesi ile defter alis
   faturalarini belge no + tutar bazinda karsilastirir (kendi kendine yeter; Akilli
   Mutabakat'a baglilik YOK).
     - GIB'de var, defterde yok -> islenmemis alis -> kaybolan indirilecek KDV
     - Tutar farki              -> kayit hatasi
     - Defterde var, GIB'de yok -> iptal/hayali fatura olabilir

Isaret: pozitif = borc bakiye, negatif = alacak bakiye (mizan_oku kuralı).
"""
import re
from core.metin import nrm as _norm

TOLERANS = 1.0
KDV_ORAN = 0.20   # bilgi amacli; tek oran varsayimi


def _tl(v):
    return f"{v:,.2f} TL".replace(",", "X").replace(".", ",").replace("X", ".")


# --------------------------------------------------------------------------- #
# 1) Mizandan KDV pozisyonu
# --------------------------------------------------------------------------- #
def devreden_onceki_190(mizan):
    """Bu ayin mahsubu ONCESI 190 Devreden KDV bakiyesi.

    Yil icinde devir olusan firmada 'onceki donemden devreden' = yilbasi ACILISI
    degil, gecen ay sonu bakiyesidir. Kumule formatta bu, acilis + guncel ay
    HARIC tum aylarin net hareketidir (guncel ayin mahsup fisi atilmis olsa
    bile o hareket dislanir). Standart (tek bakiye kolonlu) mizanda ay kirilimi
    olmadigindan mevcut 190 bakiyesi en iyi yaklasimdir."""
    o = mizan.get("hesaplar", {}).get("190")
    if not o:
        return 0.0
    ay = mizan.get("guncel_ay")
    aylik = o.get("aylik") or {}
    if ay and aylik:
        onceki = sum((v or 0) for a, v in aylik.items() if a != ay)
        return abs(round((o.get("acilis") or 0) + onceki, 2))
    return abs(round(o.get("toplam", 0.0) or 0.0, 2))


def mizandan_kdv(mizan):
    h = mizan["hesaplar"]
    ay = mizan.get("guncel_ay")

    def hesap(ana):
        return h.get(ana)

    def hareket(ana):
        o = hesap(ana)
        if not o:
            return 0.0
        if ay and o.get("aylik"):
            return o["aylik"].get(ay, 0) or 0.0
        return o.get("toplam", 0.0)

    def bakiye(ana):
        o = hesap(ana)
        return o.get("toplam", 0.0) if o else 0.0

    def acilis(ana):
        o = hesap(ana)
        return o.get("acilis", 0.0) if o else 0.0

    indirilecek = abs(hareket("191"))
    hesaplanan = abs(hareket("391"))
    devreden_onceki = devreden_onceki_190(mizan)   # gecen ay sonu devri (acilis degil)
    devreden_son = abs(bakiye("190"))         # mizandaki guncel 190 bakiyesi
    odenecek_hesap = bakiye("360")            # 360 Odenecek Vergi/Fonlar (KDV disi de icerebilir)

    ham = hesaplanan - indirilecek - devreden_onceki
    if ham > TOLERANS:
        sonuc_tip, sonuc_tutar = "ODENECEK", round(ham, 2)
    else:
        sonuc_tip, sonuc_tutar = "DEVREDEN", round(-ham, 2)

    # Kontroller
    uyarilar = []
    b191 = bakiye("191")
    b391 = bakiye("391")
    if abs(b191) > TOLERANS:
        uyarilar.append({"tip": "mahsup", "hesap": "191",
                         "ac": f"191 İndirilecek KDV ay sonunda {_tl(abs(b191))} bakiye veriyor "
                               f"— KDV mahsup fişi kesilmemiş olabilir."})
    if abs(b391) > TOLERANS:
        uyarilar.append({"tip": "mahsup", "hesap": "391",
                         "ac": f"391 Hesaplanan KDV ay sonunda {_tl(abs(b391))} bakiye veriyor "
                               f"— KDV mahsup fişi kesilmemiş olabilir."})
    if hesap("191") is None and hesap("391") is None:
        uyarilar.append({"tip": "yok", "hesap": "—",
                         "ac": "Mizanda 191/391 KDV hesapları bulunamadı — bu firma KDV mükellefi olmayabilir "
                               "veya hesap planı farklı kodlanmış."})
    if sonuc_tip == "ODENECEK" and abs(odenecek_hesap) <= TOLERANS and abs(b391) <= TOLERANS:
        uyarilar.append({"tip": "tahakkuk", "hesap": "360",
                         "ac": f"Hesaplanan ödenecek KDV {_tl(sonuc_tutar)} ancak 360 Ödenecek Vergi/Fonlar "
                               f"bakiyesi görünmüyor — tahakkuk fişi kontrol edilmeli."})

    # --- 190 Devreden KDV takibi & teyit (190/191/391 zinciri) ---
    # Ay sonu KDV mahsup fisi kesildikten sonra olmasi gereken 190 bakiyesi:
    #   DEVREDEN sonuc -> 190 son = sonuc_tutar ; ODENECEK sonuc -> 190 son = 0.
    # Mahsup fisi kesilmemisse (191/391 hala bakiye veriyor) 190 hala acilis
    # devrini tasir; bu durumda "fis kesilince ne olmali" rehberligi verilir.
    kdv_hesap_var = hesap("191") is not None or hesap("391") is not None
    var_190 = hesap("190") is not None
    mahsup_yapildi = kdv_hesap_var and abs(b191) <= TOLERANS and abs(b391) <= TOLERANS
    beklenen_devreden = sonuc_tutar if sonuc_tip == "DEVREDEN" else 0.0

    if (beklenen_devreden <= TOLERANS and devreden_son <= TOLERANS
            and devreden_onceki <= TOLERANS):
        devir_durum = "yok"
        devir_ac = "Bu dönem devreden KDV oluşmuyor; önceki/sonraki dönem 190 hareketi yok."
    elif not var_190 and beklenen_devreden > TOLERANS:
        devir_durum = "ac"
        devir_ac = (f"Mizanda 190 Devreden KDV hesabı yok ama bu dönem {_tl(beklenen_devreden)} devir oluşuyor "
                    f"— KDV mahsup fişiyle 190 hesabının açılması gerekir.")
        uyarilar.append({"tip": "devir", "hesap": "190", "ac": devir_ac})
    elif not mahsup_yapildi:
        devir_durum = "bekliyor"
        devir_ac = (f"KDV mahsup fişi henüz kesilmemiş (191/391 hâlâ açık). Fiş kesildiğinde 190 Devreden KDV "
                    f"bakiyesi {_tl(beklenen_devreden)} olmalı (mizandaki güncel 190: {_tl(devreden_son)}).")
    else:
        fark = abs(devreden_son - beklenen_devreden)
        if fark <= TOLERANS:
            devir_durum = "uygun"
            devir_ac = (f"190 Devreden KDV doğru: {_tl(devreden_son)} — "
                        + ("sonraki döneme devrediyor." if beklenen_devreden > TOLERANS
                           else "devir yok, ödenecek KDV çıktı ve 190 sıfırlanmış."))
        else:
            devir_durum = "uyumsuz"
            devir_ac = (f"190 Devreden KDV beklenen {_tl(beklenen_devreden)} iken mizanda {_tl(devreden_son)} "
                        f"görünüyor (fark {_tl(fark)}) — mahsup fişi 190'ı hatalı güncellemiş olabilir, kontrol edin.")
            uyarilar.append({"tip": "devir", "hesap": "190", "ac": devir_ac})

    return {
        "ay": ay,
        "hesaplanan": round(hesaplanan, 2),
        "indirilecek": round(indirilecek, 2),
        "devreden_onceki": round(devreden_onceki, 2),
        "devreden_son": round(devreden_son, 2),
        "odenecek_hesap": round(odenecek_hesap, 2),
        "sonuc_tip": sonuc_tip,
        "sonuc_tutar": sonuc_tutar,
        "uyarilar": uyarilar,
        "var": hesap("191") is not None or hesap("391") is not None,
        "var_190": var_190,
        "mahsup_yapildi": mahsup_yapildi,
        "beklenen_devreden": round(beklenen_devreden, 2),
        "devir_durum": devir_durum,
        "devir_ac": devir_ac,
    }


# --------------------------------------------------------------------------- #
# 2) GIB e-Fatura karsilastirmasi (kendi kendine yeter)
# --------------------------------------------------------------------------- #
def _cekirdek(s):
    r = re.findall(r"\d+", str(s))
    return int(r[-1]) if r else None


def _yakin(a, b):
    return abs(float(a) - float(b)) <= TOLERANS


def _earsiv_mi(d):
    """Belge tipi/senaryosu e-Arsiv ya da kagit/matbu fatura mi? Bunlar GIB
    e-Fatura (gelen) listesinde GORUNMEZ; defterde fazla cikmalari normaldir,
    'iptal/hayali' anomalisi sayilmamalidir. (tip, etiket) doner; degilse None."""
    from core.mizan_oku import _nrm   # Turkce-duyarli (ş->S, İ->I)
    bt = _nrm(d.get("belge_tipi", ""))
    if not bt:
        return None
    if "ARSIV" in bt:                       # E-ARSIV / EARSIV / EARSIVFATURA
        return ("earsiv", "e-Arşiv")
    if "KAGIT" in bt or "MATBU" in bt or "MANUEL" in bt:
        return ("kagit", "Kağıt/matbu fatura")
    return None


def gib_karsilastir(gib_kayit, defter_kayit):
    defter = [dict(d, _eslesti=False) for d in defter_kayit]

    def bul(g):
        gno, gc = _norm(g["belge_no"]), _cekirdek(g["belge_no"])
        for d in defter:
            if not d["_eslesti"] and _norm(d["belge_no"]) == gno:
                return d
        for d in defter:
            if not d["_eslesti"] and gc is not None and _cekirdek(d["belge_no"]) == gc:
                return d
        return None

    eksik_defter, tutar_farki, eslesen = [], [], 0
    for g in gib_kayit:
        d = bul(g)
        if d is None:
            eksik_defter.append({"belge_no": g["belge_no"], "tutar": float(g["tutar"]),
                                 "cari": g.get("cari_adi", ""),
                                 "ac": f"GİB'de var, defterde yok: {g['belge_no']} = {_tl(float(g['tutar']))} "
                                       f"→ işlenmemiş alış, indirilecek KDV kayboluyor."})
        elif not _yakin(d["tutar"], g["tutar"]):
            d["_eslesti"] = True
            tutar_farki.append({"belge_no": g["belge_no"], "gib": float(g["tutar"]),
                                "defter": float(d["tutar"]),
                                "fark": round(float(d["tutar"]) - float(g["tutar"]), 2),
                                "ac": f"{g['belge_no']}: defterde {_tl(float(d['tutar']))} / GİB {_tl(float(g['tutar']))} "
                                      f"→ kayıt hatası."})
        else:
            d["_eslesti"] = True
            eslesen += 1

    # Defterde olup GIB'de olmayanlar: e-Arsiv/kagit ise BEKLENEN (anomali degil),
    # geri kalan iptal/hayali fatura supheli -> ayri listelenir.
    fazla_defter, earsiv_defter = [], []
    for d in defter:
        if d["_eslesti"]:
            continue
        ea = _earsiv_mi(d)
        if ea:
            earsiv_defter.append({"belge_no": d["belge_no"], "tutar": float(d["tutar"]),
                                  "tip": ea[0],
                                  "ac": f"{d['belge_no']} = {_tl(float(d['tutar']))} → {ea[1]}; "
                                        f"GİB e-Fatura listesinde görünmez (beklenen)."})
        else:
            fazla_defter.append({"belge_no": d["belge_no"], "tutar": float(d["tutar"]),
                                 "ac": f"Defterde var, GİB'de yok: {d['belge_no']} = {_tl(float(d['tutar']))} "
                                       f"→ iptal/hayali fatura olabilir (belge tipi e-Arşiv/kağıt değil)."})

    sorunlu = len(eksik_defter) + len(tutar_farki) + len(fazla_defter)
    kayip_kdv = round(sum(x["tutar"] for x in eksik_defter) * KDV_ORAN / (1 + KDV_ORAN), 2)
    return {
        "gib_sayisi": len(gib_kayit), "defter_sayisi": len(defter_kayit),
        "eslesen": eslesen, "eksik_defter": eksik_defter,
        "tutar_farki": tutar_farki, "fazla_defter": fazla_defter,
        "earsiv_defter": earsiv_defter,
        "sorunlu": sorunlu, "tahmini_kayip_kdv": kayip_kdv,
    }


# --------------------------------------------------------------------------- #
# 3) KDV Tevkifati (kismi tevkifat — alici sorumlu sifatiyla)
#    Hesaplanan KDV'nin tevkifat oranina denk gelen kismi 360'a (2 No.lu KDV
#    beyannamesi), kalan kisim saticiya odenir ve 191 indirilecek KDV'dir.
# --------------------------------------------------------------------------- #
# Standart GIB tevkifat oran tablosu (pay/10) — oran bos birakilan kalemlerde
# islem turune gore varsayilan uygulanir. Kullanici listede oran verirse o gecerli.
TEVKIFAT_TABLO = [
    (("ISGUCU", "PERSONEL", "ELEMAN"), (9, 10), "İşgücü temin hizmeti"),
    (("OZELGUVENLIK", "GUVENLIK"), (9, 10), "Özel güvenlik hizmeti"),
    (("TEMIZLIK", "CEVRE", "BAHCE"), (9, 10), "Temizlik / çevre / bahçe bakım"),
    (("DANISMAN", "MUSAVIR", "DENETIM", "ETUT", "PROJE", "MUHENDISLIK", "MIMARLIK"), (9, 10), "Danışmanlık / denetim / etüt-proje"),
    (("YAPIDENETIM",), (9, 10), "Yapı denetim hizmeti"),
    (("FASON", "TEKSTIL", "KONFEKSIYON"), (7, 10), "Fason tekstil / konfeksiyon"),
    (("TAMIR", "BAKIM", "ONARIM", "MAKINE", "TECHIZAT"), (7, 10), "Makine-teçhizat tamir bakım"),
    (("BASKI", "BASIM", "MATBAA"), (7, 10), "Baskı / basım hizmeti"),
    (("HURDA", "ATIK", "METAL", "PLASTIK", "KAGIT", "KAUCUK"), (7, 10), "Hurda / atık teslimi"),
    (("SERVIS", "TASIMA", "TASIMACILIK", "NAKLIYE"), (5, 10), "Servis taşımacılığı"),
    (("YEMEK", "ORGANIZASYON", "CATERING"), (5, 10), "Yemek servisi / organizasyon"),
    (("KULCE", "BAKIR", "CINKO", "ALUMINYUM", "KURSUN", "DEMIRCELIK", "AGAC", "ORMAN"), (5, 10), "Metal/ağaç ürünleri teslimi"),
    (("REKLAM", "ILAN"), (2, 10), "Ticari reklam hizmeti"),
]
TEVKIFAT_VARSAYILAN = (5, 10)   # eslesme yoksa


def _oran_coz(ham):
    """'2/10', '9/10', '%90', '0.9', '90' -> (pay, payda); cozulemezse None."""
    s = str(ham or "").strip()
    if not s:
        return None
    s = s.replace(",", ".")
    if "/" in s:
        a, _, b = s.partition("/")
        try:
            return (float(a), float(b))
        except ValueError:
            return None
    s2 = s.replace("%", "").strip()
    try:
        v = float(s2)
    except ValueError:
        return None
    if v <= 0:
        return None
    if v <= 1:          # 0.9 -> 9/10
        return (v, 1.0)
    return (v, 100.0)   # 90 -> 90/100


def _varsayilan_oran():
    try:
        from core import ayarlar
        a = ayarlar.oku()
        pay = a.get("tevkifat_varsayilan_pay")
        payda = a.get("tevkifat_varsayilan_payda")
        if pay and payda:
            return (pay, payda)
    except Exception:
        pass
    return TEVKIFAT_VARSAYILAN


def _tablo_oran(islem):
    from core.mizan_oku import _nrm
    n = _nrm(islem)   # Turkce-duyarli normalizasyon (İşgücü -> ISGUCU)
    for anahtarlar, oran, etiket in TEVKIFAT_TABLO:
        if any(a in n for a in anahtarlar):
            return oran, etiket
    return _varsayilan_oran(), None


def tevkifat(kalemler):
    """kalemler: [{islem, matrah, kdv_orani(None=0.20), oran_ham}]"""
    satirlar = []
    uyarilar = []
    varsayilan_say = 0
    t_matrah = t_kdv = t_tevkif = t_indir = 0.0
    for k in kalemler:
        matrah = float(k["matrah"])
        orani = k.get("kdv_orani")
        orani = KDV_ORAN if orani is None else float(orani)   # 0 gecerli orandir
        kdv = round(matrah * orani, 2)
        coz = _oran_coz(k.get("oran_ham"))
        if coz:
            pay, payda = coz
            kaynak = "liste"
        else:
            (pay, payda), etiket = _tablo_oran(k["islem"])
            kaynak = "varsayilan"
            varsayilan_say += 1
        oran_oran = pay / payda if payda else 0.0
        tevkif = round(kdv * oran_oran, 2)
        indir = round(kdv - tevkif, 2)
        t_matrah += matrah; t_kdv += kdv; t_tevkif += tevkif; t_indir += indir
        satirlar.append({
            "islem": k["islem"], "matrah": round(matrah, 2),
            "kdv_orani": round(orani * 100, 0), "kdv": kdv,
            "oran_metin": (f"{int(pay)}/{int(payda)}" if payda in (10.0, 100.0) and pay == int(pay)
                           else f"%{round(oran_oran*100, 0):g}"),
            "tevkif": tevkif, "indirilecek": indir, "kaynak": kaynak,
        })
    if varsayilan_say:
        uyarilar.append({
            "tip": "varsayilan",
            "ac": f"{varsayilan_say} kalemde tevkifat oranı listede yoktu; standart GİB oran "
                  f"tablosundan varsayılan uygulandı — beyan öncesi oranları doğrulayın."})
    return {
        "kalem_sayisi": len(satirlar),
        "satirlar": satirlar,
        "toplam_matrah": round(t_matrah, 2),
        "toplam_kdv": round(t_kdv, 2),
        "toplam_tevkif": round(t_tevkif, 2),      # 360'a — 2 No.lu KDV beyannamesi
        "toplam_indirilecek": round(t_indir, 2),  # 191'e — saticiya odenen
        "uyarilar": uyarilar,
    }


# --------------------------------------------------------------------------- #
# 4) KDV matrah/oran tutarlilik denetimi
#    A) Satis matrah x oran  -> beklenen Hesaplanan KDV  vs  mizan 391 hareketi
#    B) Alis  matrah x oran  -> beklenen Indirilecek KDV vs  mizan 191 hareketi
#    C) Oran disi / anormal oran (gecerli liste disi) ve bos oran kalemleri
#    D) Beyan dokumu toplami ile mizan ortusmesi (A+B ozet karari)
#    Tolerans: |fark| HEM yuzde band HEM min TL'yi asarsa uyari (az yanlis-pozitif).
# --------------------------------------------------------------------------- #
def _kdv_tolerans():
    try:
        from core import ayarlar
        a = ayarlar.oku()
        return (float(a.get("kdv_oran_tolerans_yuzde", 2.0)),
                float(a.get("kdv_tutar_tolerans", 1000.0)),
                [int(round(float(x))) for x in a.get("kdv_gecerli_oranlar", [0, 1, 10, 20])],
                [int(round(float(x))) for x in a.get("kdv_eski_oranlar", [8, 18])])
    except Exception:
        return (2.0, 1000.0, [0, 1, 10, 20], [8, 18])


def matrah_oran_denetim(kalemler, kdv_pozisyon=None, tol_yuzde=None, tol_tutar=None):
    g_yuzde, g_tutar, gecerli, eski = _kdv_tolerans()
    tol_yuzde = g_yuzde if tol_yuzde is None else tol_yuzde
    tol_tutar = g_tutar if tol_tutar is None else tol_tutar

    satirlar, oran_uyari, satir_uyari = [], [], []
    s_matrah = s_kdv = a_matrah = a_kdv = 0.0
    for i, k in enumerate(kalemler, 1):
        matrah = float(k["matrah"])
        oran = k.get("oran")
        beklenen = round(matrah * (oran / 100.0), 2) if oran is not None else None
        verilen = k.get("kdv")
        etiket = k.get("aciklama") or k.get("belge") or f"{i}. kalem"
        tur_et = "Alış" if k["tur"] == "alis" else "Satış"

        # C) oran kontrolu
        if oran is None:
            oran_uyari.append({"seviye": "oran_disi", "tur": k["tur"],
                               "ac": f"{tur_et} — {etiket}: KDV oranı boş; matrah×oran kontrolü yapılamadı."})
        else:
            o_int = int(round(oran))
            if o_int not in gecerli:
                if o_int in eski:
                    oran_uyari.append({"seviye": "dogrula", "tur": k["tur"],
                                       "ac": f"{tur_et} — {etiket}: %{o_int} eski/geçiş dönemi oranı — "
                                             f"cari dönem için doğrulayın."})
                else:
                    oran_uyari.append({"seviye": "oran_disi", "tur": k["tur"],
                                       "ac": f"{tur_et} — {etiket}: %{o_int} standart KDV oranı değil "
                                             f"(geçerli: {', '.join('%'+str(x) for x in gecerli)}) — kayıt hatası olabilir."})

        # satir-ici KDV vs matrah×oran
        if verilen is not None and beklenen is not None:
            fark = abs(float(verilen) - beklenen)
            band = max(beklenen, 1.0) * tol_yuzde / 100.0
            if fark > tol_tutar and fark > band:
                satir_uyari.append({"tur": k["tur"],
                                    "ac": f"{tur_et} — {etiket}: yazılan KDV {_tl(float(verilen))}, "
                                          f"matrah×%{int(round(oran))} = {_tl(beklenen)} olmalı "
                                          f"(fark {_tl(fark)})."})

        kdv_deger = beklenen if beklenen is not None else (float(verilen) if verilen is not None else 0.0)
        if k["tur"] == "alis":
            a_matrah += matrah; a_kdv += kdv_deger
        else:
            s_matrah += matrah; s_kdv += kdv_deger
        satirlar.append({"tur": k["tur"], "etiket": etiket, "matrah": round(matrah, 2),
                         "oran": (int(round(oran)) if oran is not None else None),
                         "beklenen_kdv": beklenen, "verilen_kdv": verilen})

    # A) ve B) mizan ile karsilastirma
    def kiyas(etiket, hesap, beyan_kdv, beyan_matrah, mizan_kdv):
        fark = round(beyan_kdv - mizan_kdv, 2)
        band = max(abs(beyan_kdv), abs(mizan_kdv), 1.0) * tol_yuzde / 100.0
        uyumlu = not (abs(fark) > tol_tutar and abs(fark) > band)
        return {"etiket": etiket, "hesap": hesap, "beyan_matrah": round(beyan_matrah, 2),
                "beyan_kdv": round(beyan_kdv, 2), "mizan_kdv": round(mizan_kdv, 2),
                "fark": fark, "uyumlu": uyumlu}

    karsilastirma = []
    mizan_var = bool(kdv_pozisyon and kdv_pozisyon.get("var"))
    if mizan_var:
        if s_matrah > 0:
            karsilastirma.append(kiyas("Hesaplanan KDV (satış → 391)", "391",
                                       s_kdv, s_matrah, kdv_pozisyon["hesaplanan"]))
        if a_matrah > 0:
            karsilastirma.append(kiyas("İndirilecek KDV (alış → 191)", "191",
                                       a_kdv, a_matrah, kdv_pozisyon["indirilecek"]))

    bulgu = (sum(1 for k in karsilastirma if not k["uyumlu"])
             + len(oran_uyari) + len(satir_uyari))
    return {
        "kalem_sayisi": len(satirlar),
        "satirlar": satirlar,
        "satis": {"matrah": round(s_matrah, 2), "kdv": round(s_kdv, 2)},
        "alis": {"matrah": round(a_matrah, 2), "kdv": round(a_kdv, 2)},
        "karsilastirma": karsilastirma,
        "oran_uyari": oran_uyari,
        "satir_uyari": satir_uyari,
        "mizan_var": mizan_var,
        "bulgu": bulgu,
        "tolerans": {"yuzde": tol_yuzde, "tutar": tol_tutar},
    }
