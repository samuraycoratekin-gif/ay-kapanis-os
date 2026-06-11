# -*- coding: utf-8 -*-
"""
Kapanis fisi ureticisi.

Mevcut verilerden (mizan, banka) yevmiye fisi TASLAGI uretir. Fis ASLA otomatik
kaydedilmez/gonderilmez; her fis onizlenir, kullanici onaylar, sonra ERP'ye gonderilir.
(Akilli Mutabakat'taki "asla insan onayi olmadan kayit atma" ilkesiyle ayni.)

Fis semasi:
  {"anahtar": str (donem icinde stabil), "tip": str, "baslik": str, "tarih": str,
   "aciklama": str, "satirlar": [{"hesap","ad","borc","alacak"}, ...],
   "borc_toplam","alacak_toplam","denk": bool}
"""

import hashlib
from datetime import datetime

TOL = 0.01


def _toplamlar(satirlar):
    b = round(sum(s["borc"] for s in satirlar), 2)
    a = round(sum(s["alacak"] for s in satirlar), 2)
    return b, a


def _fis(anahtar, tip, baslik, tarih, aciklama, satirlar):
    b, a = _toplamlar(satirlar)
    return {"anahtar": anahtar, "tip": tip, "baslik": baslik, "tarih": tarih,
            "aciklama": aciklama, "satirlar": satirlar,
            "borc_toplam": b, "alacak_toplam": a, "denk": abs(b - a) <= TOL}


# --------------------------------------------------------------------------- #
# KDV mahsup fisi (mizandan)
# --------------------------------------------------------------------------- #
def kdv_mahsup_fisi(mizan, tarih):
    from core import kdv_analiz
    h = mizan["hesaplar"]

    def bak(ana):
        o = h.get(ana)
        return abs(o["toplam"]) if o else 0.0

    b391 = bak("391")   # hesaplanan (alacak bakiye)
    b191 = bak("191")   # indirilecek (borc bakiye)
    b190 = kdv_analiz.devreden_onceki_190(mizan)   # gecen ay sonu devri (acilis degil)
    if b391 <= TOL and b191 <= TOL:
        return None

    satirlar = []
    if b391 > TOL:
        satirlar.append({"hesap": "391", "ad": "Hesaplanan KDV", "borc": round(b391, 2), "alacak": 0.0})
    if b191 > TOL:
        satirlar.append({"hesap": "191", "ad": "İndirilecek KDV", "borc": 0.0, "alacak": round(b191, 2)})
    if b190 > TOL:
        satirlar.append({"hesap": "190", "ad": "Devreden KDV (önceki dönem)", "borc": 0.0, "alacak": round(b190, 2)})

    fark = round(b391 - b191 - b190, 2)
    if fark > TOL:
        satirlar.append({"hesap": "360", "ad": "Ödenecek Vergi ve Fonlar (KDV)", "borc": 0.0, "alacak": fark})
    elif fark < -TOL:
        satirlar.append({"hesap": "190", "ad": "Devreden KDV (sonraki döneme)", "borc": -fark, "alacak": 0.0})

    ay = mizan.get("guncel_ay") or ""
    return _fis("kdv_mahsup", "kdv_mahsup", f"KDV Mahsup Fişi — {ay}", tarih,
                "Dönem KDV hesaplarının mahsuplaştırılması (191/391 → 360/190).", satirlar)


# --------------------------------------------------------------------------- #
# Banka komisyon/masraf gider fisleri (M5 sonucundan)
# --------------------------------------------------------------------------- #
def banka_komisyon_fisleri(komisyon_hareketleri):
    fisler = []
    gorulen = set()
    for h in komisyon_hareketleri:
        tutar = round(abs(h["tutar"]), 2)
        if tutar <= TOL:
            continue
        # Anahtar icerikten turetilir (tarih+tutar+aciklama): dosya yeniden
        # yuklendiginde sira degisse bile onay durumu DOGRU fise yapisik kalir.
        kimlik = hashlib.sha1(
            f"{h.get('tarih','')}|{tutar}|{h.get('aciklama','')}".encode("utf-8")).hexdigest()[:10]
        if kimlik in gorulen:            # birebir ayni hareket (cift satir) -> tek fis
            kimlik = hashlib.sha1(
                f"{kimlik}|{len(gorulen)}".encode("utf-8")).hexdigest()[:10]
        gorulen.add(kimlik)
        satirlar = [
            {"hesap": "770", "ad": "Genel Yönetim Gideri (banka masrafı)", "borc": tutar, "alacak": 0.0},
            {"hesap": "102", "ad": "Bankalar", "borc": 0.0, "alacak": tutar},
        ]
        fisler.append(_fis(f"banka_komisyon_{kimlik}", "banka_komisyon",
                           f"Banka Masraf Fişi — {h.get('aciklama','') or 'komisyon'}",
                           str(h.get("tarih", "")),
                           h.get("aciklama", "") or "Banka komisyon/masraf gideri.", satirlar))
    return fisler


# --------------------------------------------------------------------------- #
# Amortisman fisi (demirbas listesinden) — aylik
# --------------------------------------------------------------------------- #
def amortisman_fisi(demirbaslar, tarih):
    """Demirbas listesinden tek bir aylik amortisman mahsup fisi uretir.
    Gider hesaplari borc, birikmis amortisman hesaplari alacak olarak gruplanir."""
    gider, birikmis = {}, {}
    for d in demirbaslar:
        ay = round(d.get("aylik") or 0, 2)
        if ay <= TOL:
            continue
        gider[d["gider_hesap"]] = round(gider.get(d["gider_hesap"], 0) + ay, 2)
        birikmis[d["birikmis_hesap"]] = round(birikmis.get(d["birikmis_hesap"], 0) + ay, 2)
    if not gider:
        return None
    satirlar = [{"hesap": k, "ad": "Amortisman Gideri", "borc": v, "alacak": 0.0}
                for k, v in sorted(gider.items())]
    satirlar += [{"hesap": k, "ad": "Birikmiş Amortismanlar", "borc": 0.0, "alacak": v}
                 for k, v in sorted(birikmis.items())]
    return _fis("amortisman", "amortisman", "Amortisman Fişi (aylık)", tarih,
                f"{len(demirbaslar)} sabit kıymet için dönem amortisman ayrımı.", satirlar)


# --------------------------------------------------------------------------- #
# Kur farki degerleme fisi (dovizli liste + kur)
# --------------------------------------------------------------------------- #
def kur_farki_fisi(dovizli, tarih):
    """Dovizli hesap bakiyelerinin donem sonu kur degerlemesi.
    Lehte fark (artis) -> hesap borc / 646; aleyhte (azalis) -> 656 / hesap alacak."""
    satirlar, kar, zarar = [], 0.0, 0.0
    for d in dovizli:
        fark = round(d.get("fark") or 0, 2)
        if abs(fark) <= TOL:
            continue
        ad = (d.get("ad") or d["hesap"]) + (f" ({d['doviz']})" if d.get("doviz") else "")
        if fark > 0:
            satirlar.append({"hesap": d["hesap"], "ad": ad, "borc": fark, "alacak": 0.0})
            kar = round(kar + fark, 2)
        else:
            satirlar.append({"hesap": d["hesap"], "ad": ad, "borc": 0.0, "alacak": -fark})
            zarar = round(zarar - fark, 2)
    if not satirlar:
        return None
    if kar > TOL:
        satirlar.append({"hesap": "646", "ad": "Kambiyo Kârları", "borc": 0.0, "alacak": kar})
    if zarar > TOL:
        satirlar.append({"hesap": "656", "ad": "Kambiyo Zararları", "borc": zarar, "alacak": 0.0})
    return _fis("kur_farki", "kur_farki", "Kur Farkı Değerleme Fişi", tarih,
                "Dövizli hesapların dönem sonu kuru ile değerlemesi (646/656).", satirlar)


# --------------------------------------------------------------------------- #
# Reeskont fisi (vadeli senet/cek listesi)
# --------------------------------------------------------------------------- #
def reeskont_fisi(senetler, donem_sonu, varsayilan_faiz):
    """Vadeli senet/ceklerin reeskontu. Ic iskonto: reeskont = nominal*faiz*gun/
    (36000 + faiz*gun). Alacak senedi -> 657 gider/122; borc senedi -> 322/647 gelir."""
    from datetime import date as _d
    ds = donem_sonu if isinstance(donem_sonu, _d) else None
    if ds is None:
        try:
            ds = datetime.strptime(str(donem_sonu)[:10], "%Y-%m-%d").date()
        except Exception:
            return None
    a_re, b_re = 0.0, 0.0
    for s in senetler:
        try:
            vade = datetime.strptime(s["vade"][:10], "%Y-%m-%d").date()
        except Exception:
            continue
        gun = (vade - ds).days
        if gun <= 0:
            continue
        faiz = s.get("faiz") if s.get("faiz") else varsayilan_faiz
        nominal = s["tutar"]
        re = round(nominal * faiz * gun / (36000 + faiz * gun), 2)
        if re <= TOL:
            continue
        if s["tip"] == "borc":
            b_re = round(b_re + re, 2)
        else:
            a_re = round(a_re + re, 2)
    satirlar = []
    if a_re > TOL:
        satirlar.append({"hesap": "657", "ad": "Reeskont Faiz Gideri", "borc": a_re, "alacak": 0.0})
        satirlar.append({"hesap": "122", "ad": "Alacak Senetleri Reeskontu (-)", "borc": 0.0, "alacak": a_re})
    if b_re > TOL:
        satirlar.append({"hesap": "322", "ad": "Borç Senetleri Reeskontu (-)", "borc": b_re, "alacak": 0.0})
        satirlar.append({"hesap": "647", "ad": "Reeskont Faiz Geliri", "borc": 0.0, "alacak": b_re})
    if not satirlar:
        return None
    return _fis("reeskont", "reeskont", "Reeskont Fişi", str(ds),
                f"Vadeli senet/çeklerin dönem sonu reeskontu (faiz %{varsayilan_faiz}).", satirlar)


# --------------------------------------------------------------------------- #
# 7/A maliyet hesaplarinin donem sonu virmani (yansitma + kapatma)
# --------------------------------------------------------------------------- #
# 7x0 gider/maliyet -> (7x1 yansitma, sonuc hesabi, ad)
# Uretim giderleri (71x/730) once 151 Yari Mamul'e; faaliyet/finansman giderleri
# dogrudan gelir tablosu sonuc hesaplarina (62x/63x/660) yansir.
YEDI_A = {
    "710": ("711", "151", "Direkt İlk Madde ve Malzeme Giderleri"),
    "720": ("721", "151", "Direkt İşçilik Giderleri"),
    "730": ("731", "151", "Genel Üretim Giderleri"),
    "740": ("741", "622", "Hizmet Üretim Maliyeti"),
    "750": ("751", "630", "Araştırma ve Geliştirme Giderleri"),
    "760": ("761", "631", "Pazarlama, Satış ve Dağıtım Giderleri"),
    "770": ("771", "632", "Genel Yönetim Giderleri"),
    "780": ("781", "660", "Finansman Giderleri"),
}

SONUC_AD = {
    "151": "Yarı Mamuller - Üretim", "622": "Satılan Hizmet Maliyeti",
    "630": "Araştırma ve Geliştirme Giderleri", "631": "Pazarlama Satış ve Dağıtım Gid.",
    "632": "Genel Yönetim Giderleri", "660": "Kısa Vadeli Borçlanma Giderleri",
}


def yedi_a_virman_fisleri(mizan, tarih):
    """7/A'ya gore tutulan maliyet/gider hesaplarinin (710-780) donem sonu
    virmanini iki fis halinde uretir:
      1) Yansitma : Borc sonuc hesabi (151/62x/63x/660), Alacak 7x1 yansitma
      2) Kapatma  : Borc 7x1 yansitma,                   Alacak 7x0 gider
    Yalniz mizanda bakiyesi olan 7x0 hesaplari icin satir uretilir. Donem
    sonucu degismez; sadece gider hesaplari kapanir (son onay kullanicida)."""
    h = mizan.get("hesaplar", {})

    aktif = []  # (kod7x0, yansitma, sonuc, ad, bakiye)
    for kod, (yans, sonuc, ad) in YEDI_A.items():
        o = h.get(kod)
        bak = round(abs(o["toplam"]), 2) if o else 0.0
        if bak > TOL:
            aktif.append((kod, yans, sonuc, ad, bak))
    if not aktif:
        return []

    # 1) Yansitma fisi: sonuc hesaplarini grupla (birden fazla 7x0 ayni sonuca gidebilir)
    sonuc_top = {}
    yans_borc = []
    for kod, yans, sonuc, ad, bak in aktif:
        sonuc_top[sonuc] = round(sonuc_top.get(sonuc, 0) + bak, 2)
        yans_borc.append({"hesap": yans, "ad": f"{ad} Yansıtma", "borc": 0.0, "alacak": bak})
    yans_satir = [{"hesap": s, "ad": SONUC_AD.get(s, "Sonuç/Maliyet Hesabı"),
                   "borc": v, "alacak": 0.0} for s, v in sorted(sonuc_top.items())]
    yans_satir += sorted(yans_borc, key=lambda x: x["hesap"])
    fis_yans = _fis("yedi_a_yansitma", "yedi_a",
                    "7/A Yansıtma Fişi (dönem sonu)", tarih,
                    "7/A gider/maliyet hesaplarının yansıtma hesapları üzerinden "
                    "sonuç hesaplarına aktarımı (7x1 → 151/62x/63x/660).",
                    yans_satir)

    # 2) Kapatma fisi: yansitma hesaplarini 7x0 gider hesaplarina kapat
    kap_satir = []
    for kod, yans, sonuc, ad, bak in aktif:
        kap_satir.append({"hesap": yans, "ad": f"{ad} Yansıtma", "borc": bak, "alacak": 0.0})
    for kod, yans, sonuc, ad, bak in aktif:
        kap_satir.append({"hesap": kod, "ad": ad, "borc": 0.0, "alacak": bak})
    fis_kap = _fis("yedi_a_kapatma", "yedi_a",
                   "7/A Kapatma Fişi (dönem sonu)", tarih,
                   "Yansıtma hesaplarının ilgili 7/A gider hesaplarıyla "
                   "kapatılması (7x1 → 7x0); gider hesapları sıfırlanır.",
                   kap_satir)
    return [fis_yans, fis_kap]
