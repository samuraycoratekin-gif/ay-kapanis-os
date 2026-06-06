# -*- coding: utf-8 -*-
"""
Banka kredisi analiz motoru — donem sonu (kapanis) odakli.

Her kredi icin odeme planindan (amortisman) su kontrolleri uretir:
  * Vade yapisina gore siniflama: kisa vadeli kredi -> 300, uzun vadeli -> 400.
  * UZUN vadeli kredide gelecek 12 ay icinde odenecek ANAPARA "cari kisim"dir;
    donem sonunda 400 -> 303'e SINIFLAMA (reclass) onerilir.
  * Donem icinde vadesi gelen taksitin FAIZ kismi 780/660 gider; bankadan odendi
    mi teyidi (kayit otomatik atilmaz).
  * Dovizli kredide donem sonu kuru ile kalan anapara degerlemesi -> 656/646.

Cikti: dönem fis ONERILERIDIR; son onay ve kayit musavirdedir (otomatik kayit YOK).
"""
from datetime import date, timedelta


# --------------------------------------------------------------------------- #
def _onceki_gun(d):
    return d - timedelta(days=1)


def _ay_son(donem):
    """'YYYY-MM' -> o ayin son gunu (date)."""
    y, m = (int(x) for x in donem.split("-")[:2])
    if m == 12:
        return date(y, 12, 31)
    return _onceki_gun(date(y, m + 1, 1))


def _yil_sonra(d):
    """d'den 12 ay sonrasinin AY SONU (cari/uzun ayrim ufku)."""
    y, m = d.year + 1, d.month
    if m == 12:
        return date(y, 12, 31)
    return _onceki_gun(date(y, m + 1, 1))


def _gun(iso):
    if not iso:
        return None
    try:
        return date.fromisoformat(iso[:10])
    except ValueError:
        return None


def _tl(v):
    return f"{v:,.2f} TL".replace(",", "X").replace(".", ",").replace("X", ".")


# --------------------------------------------------------------------------- #
def analiz(krediler, donem, bugun=None):
    son = _ay_son(donem)
    ufuk = _yil_sonra(son)            # cari kisim siniri: son + 12 ay
    yil = son.year
    ay = son.month

    sonuc_krediler = []
    oneriler = []
    top = {"kalan": 0.0, "cari": 0.0, "uzun": 0.0, "donem_faiz": 0.0, "donem_anapara": 0.0}

    for k in krediler:
        taksitler = k["taksitler"]
        vadeli = [t for t in taksitler if _gun(t["vade"])]
        if not vadeli:
            sonuc_krediler.append({
                "ad": k["ad"], "doviz": k.get("doviz", "TL"), "tip": "?",
                "kalan": 0.0, "cari": 0.0, "uzun": 0.0,
                "donem_taksiti": [], "donem_faiz": 0.0, "donem_anapara": 0.0,
                "kur_farki": None,
                "uyarilar": ["Vade tarihleri okunamadı — sınıflama yapılamadı."]})
            continue

        ilk_v = min(_gun(t["vade"]) for t in vadeli)
        son_v = max(_gun(t["vade"]) for t in vadeli)
        uzun_mu = (son_v - ilk_v).days > 366    # orijinal vade > 1 yil

        # Donem sonunda HENUZ odenmemis taksitler (vade > donem sonu)
        kalanlar = [t for t in vadeli if _gun(t["vade"]) > son]
        kalan_anapara = round(sum(t["anapara"] for t in kalanlar), 2)
        cari = round(sum(t["anapara"] for t in kalanlar if _gun(t["vade"]) <= ufuk), 2)
        uzun = round(sum(t["anapara"] for t in kalanlar if _gun(t["vade"]) > ufuk), 2)

        # Donem icinde (kapanan ay) vadesi gelen taksitler
        donem_t = [t for t in vadeli if _gun(t["vade"]).year == yil and _gun(t["vade"]).month == ay]
        donem_faiz = round(sum(t["faiz"] for t in donem_t), 2)
        donem_anapara = round(sum(t["anapara"] for t in donem_t), 2)

        uyarilar = []
        # --- Siniflama / reclass ---
        if uzun_mu:
            ana_hesap = "400"
            if cari > 0:
                oneriler.append({
                    "tip": "reclass", "hesap": "400 → 303",
                    "tutar": cari,
                    "ac": f"{k['ad']}: gelecek 12 ayda ödenecek anapara {_tl(cari)} — "
                          f"dönem sonunda 400 (B) / 303 (A) sınıflama (reclass) fişi önerilir."})
                uyarilar.append(f"Cari kısım {_tl(cari)} → 303'e taşınmalı (kalan {_tl(uzun)} 400'de).")
        else:
            ana_hesap = "300"
            uyarilar.append(f"Kısa vadeli kredi — kalan anapara {_tl(kalan_anapara)} 300'de izlenir.")

        # --- Donem faizi ---
        if donem_faiz > 0:
            oneriler.append({
                "tip": "faiz", "hesap": "780/660",
                "tutar": donem_faiz,
                "ac": f"{k['ad']}: dönem faizi {_tl(donem_faiz)} — 780/660 (B) gider olarak "
                      f"kayda alındı mı? (ödenmediyse 381 Gider Tahakkukları)."})

        # --- Dovizli kredi kur farki ---
        kur_farki = None
        doviz = (k.get("doviz") or "TL").upper()
        if doviz not in ("TL", "TRY", ""):
            dk = k.get("defter_kur")
            gk = k.get("guncel_kur")
            if dk and gk:
                # plandaki anapara doviz cinsinden kabul edilir
                kur_farki = round(kalan_anapara * (gk - dk), 2)
                yon = "zarar 656 (B)" if kur_farki > 0 else "gelir 646 (A)"
                oneriler.append({
                    "tip": "kur", "hesap": "656/646",
                    "tutar": abs(kur_farki),
                    "ac": f"{k['ad']} ({doviz}): dönem sonu kuru ile kalan anapara değerlemesi "
                          f"kur farkı {_tl(abs(kur_farki))} — {yon}."})
                uyarilar.append(f"Dövizli: kur farkı {_tl(abs(kur_farki))} ({doviz} {dk}→{gk}).")
            else:
                kur_farki = "kur_yok"
                oneriler.append({
                    "tip": "kur", "hesap": "656/646", "tutar": 0.0,
                    "ac": f"{k['ad']} ({doviz}): dövizli kredi — dönem sonu TCMB kuru ile "
                          f"656/646 kur farkı değerlemesi gerekli (defter/güncel kur girilmemiş)."})
                uyarilar.append(f"Dövizli kredi ({doviz}) — kur farkı için kur bilgisi gerekli.")

        sonuc_krediler.append({
            "ad": k["ad"], "doviz": doviz, "tip": ("uzun" if uzun_mu else "kisa"),
            "ana_hesap": ana_hesap,
            "kalan": kalan_anapara, "cari": cari, "uzun": uzun,
            "donem_taksiti": donem_t, "donem_faiz": donem_faiz, "donem_anapara": donem_anapara,
            "kur_farki": kur_farki, "uyarilar": uyarilar})
        top["kalan"] += kalan_anapara
        top["cari"] += cari
        top["uzun"] += uzun
        top["donem_faiz"] += donem_faiz
        top["donem_anapara"] += donem_anapara

    top = {a: round(v, 2) for a, v in top.items()}
    return {
        "donem_sonu": son.isoformat(),
        "krediler": sonuc_krediler,
        "oneriler": oneriler,
        "toplam": top,
        "bulgu": len(oneriler),
        "kredi_sayisi": len(sonuc_krediler),
    }
