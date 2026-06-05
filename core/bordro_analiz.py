# -*- coding: utf-8 -*-
"""
Bordro <-> Muhasebe mutabakati.

Bordro icmal toplamlarini mizan hesap hareketleriyle karsilastirir:
  Net ucret        <-> 335 Personele Borclar           (tahakkuk, alacak)
  SGK toplam       <-> 361 Odenecek Sosyal Guvenlik     (isci+isveren+issizlik)
  Gelir V.+Damga   <-> 360 Odenecek Vergi ve Fonlar     (KDV ile karisik -> soft)
  Personel gideri  <-> 720/730/740/760/770 gider hesap. (karisik -> soft)

Ayrica bordronun kendi ici tutarliligi: Brut - kesintiler = Net mi?

Mizan yoksa yalnizca ic tutarlilik + icmal ozeti sunulur.
Isaret kurali: pozitif = borc, negatif = alacak (mizan_oku ile ayni).
"""
from core import ayarlar

GIDER_PERSONEL = ["720", "730", "740", "760", "770"]


def _tol():
    try:
        return float(ayarlar.oku().get("bordro_tolerans", 1.0))
    except Exception:
        return 1.0


def _hareket(mizan, ana):
    """Donem (guncel ay) net hareketi; yoksa kumule bakiye."""
    h = mizan["hesaplar"].get(ana)
    if not h:
        return 0.0
    ay = mizan.get("guncel_ay")
    if ay and h.get("aylik"):
        return h["aylik"].get(ay, 0) or 0.0
    return h.get("toplam", 0.0) or 0.0


def _kiyas(kalem, hesap, icmal, mizan_deger, tol, yon_not=""):
    fark = round(icmal - abs(mizan_deger), 2)
    uyumlu = abs(fark) <= tol
    return {"kalem": kalem, "hesap": hesap, "icmal": round(icmal, 2),
            "mizan": round(abs(mizan_deger), 2), "fark": fark, "uyumlu": uyumlu,
            "seviye": "kesin", "not": yon_not}


def karsilastir(bordro, mizan=None, tol=None):
    tol = _tol() if tol is None else tol
    t = bordro["toplam"]
    karsilastirma, soft, ic_kontrol = [], [], []

    # Ic tutarlilik: brut - kesintiler = net
    net_fark = round(t["net"] - t["net_hesap"], 2)
    if t["net"] > 0 and abs(net_fark) > tol:
        ic_kontrol.append({
            "kalem": "Net ücret (iç tutarlılık)",
            "ac": f"Bordroda yazan net {t['net']:,.2f} TL, brüt − kesintiler hesabı "
                  f"{t['net_hesap']:,.2f} TL veriyor (fark {net_fark:,.2f} TL) — bordro icmalinde tutarsızlık."})

    mizan_var = bool(mizan and mizan.get("hesaplar"))
    if mizan_var:
        karsilastirma.append(_kiyas("Net Ücret", "335", t["net"], _hareket(mizan, "335"), tol,
                                    "335 Personele Borçlar dönem tahakkuku."))
        karsilastirma.append(_kiyas("SGK (işçi+işveren+işsizlik)", "361", t["sgk_toplam"],
                                    _hareket(mizan, "361"), tol,
                                    "361 Ödenecek Sosyal Güvenlik dönem tahakkuku."))
        # 360 (KDV ile karisik) -> soft: en az vergi_toplam kadar olmali
        h360 = abs(_hareket(mizan, "360"))
        if t["vergi_toplam"] > tol:
            yeterli = h360 + tol >= t["vergi_toplam"]
            soft.append({"kalem": "Gelir V. + Damga", "hesap": "360",
                         "icmal": t["vergi_toplam"], "mizan": round(h360, 2),
                         "uyumlu": yeterli,
                         "ac": (f"360 dönem hareketi {h360:,.2f} TL, bordro vergisi {t['vergi_toplam']:,.2f} TL'yi "
                                f"karşılıyor (360 KDV'yi de içerir, fazlası normal)." if yeterli
                                else f"360 dönem hareketi {h360:,.2f} TL, bordro gelir vergisi+damga "
                                     f"{t['vergi_toplam']:,.2f} TL'den AZ — vergi tahakkuku eksik olabilir.")})
        # Personel gideri -> soft: ilgili gider hesaplari personel giderini karsilamali
        gider = sum(abs(_hareket(mizan, g)) for g in GIDER_PERSONEL)
        if t["personel_gider"] > tol:
            yeterli = gider + tol >= t["personel_gider"]
            soft.append({"kalem": "Personel Gideri (brüt+işveren)", "hesap": "/".join(GIDER_PERSONEL),
                         "icmal": t["personel_gider"], "mizan": round(gider, 2),
                         "uyumlu": yeterli,
                         "ac": (f"İlgili gider hesapları {gider:,.2f} TL, personel gideri {t['personel_gider']:,.2f} TL'yi "
                                f"karşılıyor (gider hesapları başka kalemleri de içerir)." if yeterli
                                else f"İlgili gider hesapları {gider:,.2f} TL, bordro personel gideri "
                                     f"{t['personel_gider']:,.2f} TL'den AZ — gider tahakkuku eksik olabilir.")})

    kesin_uyumsuz = [k for k in karsilastirma if not k["uyumlu"]]
    soft_uyumsuz = [k for k in soft if not k["uyumlu"]]
    bulgu = len(kesin_uyumsuz) + len(soft_uyumsuz) + len(ic_kontrol)
    return {
        "mizan_var": mizan_var,
        "personel_sayisi": bordro["personel_sayisi"],
        "toplam": t,
        "karsilastirma": karsilastirma,
        "soft": soft,
        "ic_kontrol": ic_kontrol,
        "bulgu": bulgu,
        "tolerans": tol,
    }
