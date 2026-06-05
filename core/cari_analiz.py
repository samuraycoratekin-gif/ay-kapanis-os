# -*- coding: utf-8 -*-
"""
Cari mutabakat analizi - iki katman.

HAFIF MOD (Ay Kapanis OS tek basina, her zaman calisir):
  Her cari icin NET BAKIYE = sum(FATURA) - sum(ODEME). Bizim net ile karsi net
  toleransi asan farkliysa "FARKLI"; yalniz bir tarafta olan cari "TEK TARAF".
  Belge duzeyinde eslestirme YOK; kapanis icin "hangi cari incelenmeli" sinyali.

DERIN MOD (musteri Akilli Mutabakat urunune de sahipse):
  Akilli Mutabakat motoru (mutabakat_motoru.cari_esle) belge duzeyinde calisir:
  EXACT / FUZZY / TUTAR_FARKI / SUBSET_SUM / EKSIK belge. Tam triyaj uretir.

Isaret: net = borc(+) FATURA - alacak(-) ODEME. Iki defter de ayni isaret kurali.
"""
import os, sys
from datetime import datetime, date

TOLERANS = 1.0   # TL; bu altindaki net fark "mutabik" sayilir


def _net(kayitlar):
    return round(sum((k["tutar"] if k["tip"] != "ODEME" else -k["tutar"])
                     for k in kayitlar), 2)


# --------------------------------------------------------------------------- #
# HAFIF MOD
# --------------------------------------------------------------------------- #
def hafif(bizim_kayit, karsi_kayit, tolerans=TOLERANS):
    bizim = {}
    karsi = {}
    for k in bizim_kayit:
        bizim.setdefault(k["cari_kodu"], []).append(k)
    for k in karsi_kayit:
        karsi.setdefault(k["cari_kodu"], []).append(k)

    cariler = sorted(set(bizim) | set(karsi))
    mutabik, farkli, tek_taraf = [], [], []
    for ck in cariler:
        b, kr = bizim.get(ck, []), karsi.get(ck, [])
        adi = (b or kr)[0].get("cari_adi", "") or ck
        bn, kn = _net(b), _net(kr)
        if not b or not kr:
            tek_taraf.append({"cari_kodu": ck, "cari_adi": adi,
                              "taraf": "bizde" if b else "karsida",
                              "bizim_net": bn, "karsi_net": kn,
                              "kalem": len(b) + len(kr)})
        elif abs(bn - kn) > tolerans:
            farkli.append({"cari_kodu": ck, "cari_adi": adi,
                           "bizim_net": bn, "karsi_net": kn,
                           "fark": round(bn - kn, 2)})
        else:
            mutabik.append({"cari_kodu": ck, "cari_adi": adi, "net": bn})

    farkli.sort(key=lambda x: -abs(x["fark"]))
    tek_taraf.sort(key=lambda x: -abs(x["bizim_net"] - x["karsi_net"]))
    return {
        "mod": "hafif",
        "cari_sayisi": len(cariler),
        "mutabik": mutabik, "farkli": farkli, "tek_taraf": tek_taraf,
        "sorunlu": len(farkli) + len(tek_taraf),
        "toplam_acik": round(sum(abs(x["fark"]) for x in farkli)
                             + sum(abs(x["bizim_net"] - x["karsi_net"]) for x in tek_taraf), 2),
    }


# --------------------------------------------------------------------------- #
# CARI YASLANDIRMA (bizim defterden, FIFO tahsilat mantigi)
# --------------------------------------------------------------------------- #
KOVA_ETIKET = ["0-30", "31-60", "61-90", "90+", "tarihsiz"]


def _gun_kovasi(gun):
    if gun <= 30:
        return "0-30"
    if gun <= 60:
        return "31-60"
    if gun <= 90:
        return "61-90"
    return "90+"


def _tarihe(v):
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v).strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y.%m.%d"):
        try:
            return datetime.strptime(s[:10], fmt).date()
        except ValueError:
            continue
    return None


def yaslandirma(bizim_kayit, bugun=None):
    """Her cari icin acik bakiyeyi belge tarihine gore yaslandirir.
    Tahsilatlar EN ESKI faturadan baslayarak (FIFO) dusulur; kalan fatura
    tutarlari yas kovalarina dagitilir. Pozitif net = bizden alacak."""
    if bugun is None:
        bugun = date.today()
    elif not isinstance(bugun, date):
        bugun = _tarihe(bugun) or date.today()

    gruplu = {}
    for k in bizim_kayit:
        gruplu.setdefault(k["cari_kodu"], []).append(k)

    cariler = []
    toplam_kova = {e: 0.0 for e in KOVA_ETIKET}
    for ck, kayitlar in gruplu.items():
        adi = kayitlar[0].get("cari_adi", "") or ck
        # Tahsilat/odemeler defterde negatif saklanabilir; isaretten bagimsiz
        # mutlak deger kullanilir (odeme alacagi azaltir).
        faturalar, odeme = [], 0.0
        for k in kayitlar:
            if k["tip"] == "ODEME":
                odeme += abs(k["tutar"])
            else:
                faturalar.append({"tutar": abs(k["tutar"]), "tarih": _tarihe(k.get("tarih"))})
        faturalar.sort(key=lambda f: (f["tarih"] is None, f["tarih"] or date.max))
        # FIFO: en eski faturadan tahsilati dus
        for f in faturalar:
            if odeme <= 0:
                break
            dus = min(odeme, f["tutar"])
            f["tutar"] = round(f["tutar"] - dus, 2)
            odeme = round(odeme - dus, 2)
        kovalar = {e: 0.0 for e in KOVA_ETIKET}
        en_eski = 0
        for f in faturalar:
            if f["tutar"] <= 0.01:
                continue
            if f["tarih"] is None:
                kovalar["tarihsiz"] = round(kovalar["tarihsiz"] + f["tutar"], 2)
            else:
                gun = (bugun - f["tarih"]).days
                kovalar[_gun_kovasi(gun)] = round(kovalar[_gun_kovasi(gun)] + f["tutar"], 2)
                en_eski = max(en_eski, gun)
        net = round(sum(kovalar.values()), 2)
        if abs(net) < 0.01:
            continue
        for e in KOVA_ETIKET:
            toplam_kova[e] = round(toplam_kova[e] + kovalar[e], 2)
        cariler.append({"cari_kodu": ck, "cari_adi": adi, "net": net,
                        "kovalar": kovalar, "en_eski_gun": en_eski})

    cariler.sort(key=lambda c: -c["en_eski_gun"])
    return {
        "bugun": bugun.isoformat(),
        "kovalar": toplam_kova,
        "toplam": round(sum(toplam_kova.values()), 2),
        "vadesi_gecen": round(toplam_kova["61-90"] + toplam_kova["90+"], 2),
        "cariler": cariler,
    }


# --------------------------------------------------------------------------- #
# DERIN MOD (Akilli Mutabakat motoru kopru)
# --------------------------------------------------------------------------- #
def _motor():
    """Komsu Mutabakat_AI klasorunden motoru import eder; yoksa None."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # Ay_Kapanis_OS
    kok = os.path.dirname(here)                                         # YAPAY ZEKA...
    yol = os.path.join(kok, "Mutabakat_AI")
    if not os.path.isdir(yol):
        return None
    if yol not in sys.path:
        sys.path.insert(0, yol)
    try:
        import mutabakat_motoru as mm
        return mm
    except Exception:
        return None


def motor_var():
    return _motor() is not None


def derin(bizim_kayit, karsi_kayit):
    mm = _motor()
    if mm is None:
        return None
    bizim = {}
    karsi = {}
    for k in bizim_kayit:
        k["_eslesti"] = False
        bizim.setdefault(k["cari_kodu"], []).append(k)
    for k in karsi_kayit:
        k["_eslesti"] = False
        karsi.setdefault(k["cari_kodu"], []).append(k)

    cariler = sorted(set(bizim) | set(karsi))
    sonuc = []
    sayac = {"MUTABIK": 0, "TUTAR FARKLI": 0, "EKSIK BELGE": 0}
    for ck in cariler:
        bulgular = mm.cari_esle(bizim.get(ck, []), karsi.get(ck, []))
        adi = (bizim.get(ck) or karsi.get(ck))[0].get("cari_adi", "") or ck
        durum = mm.cari_durum(bulgular)
        sayac[durum] = sayac.get(durum, 0) + 1
        # bulgulari JSON-guvenli sadelestir (tek/coklu karsi kalem)
        sade = []
        for tip, b, k, ac in bulgular:
            sade.append({"tip": tip, "aciklama": ac,
                         "bizim": (b["belge_no"] if isinstance(b, dict) else None),
                         "karsi": (k["belge_no"] if isinstance(k, dict)
                                   else (", ".join(p["belge_no"] for p in k) if isinstance(k, (list, tuple)) else None))})
        sonuc.append({"cari_kodu": ck, "cari_adi": adi, "durum": durum,
                      "acik": mm.fark_tutari(bulgular), "bulgular": sade})

    sonuc.sort(key=lambda x: (x["durum"] == "MUTABIK", -x["acik"]))
    return {
        "mod": "derin",
        "cari_sayisi": len(cariler),
        "sayac": sayac,
        "sorunlu": sayac.get("TUTAR FARKLI", 0) + sayac.get("EKSIK BELGE", 0),
        "cariler": sonuc,
    }
