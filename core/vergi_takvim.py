# -*- coding: utf-8 -*-
"""
Vergi takvimi & beyanname son tarihleri - hesaplama motoru.

Kapanisi yapilan donem (YYYY-MM) icin verilmesi gereken beyannamelerin yasal son
gunlerini uretir; hafta sonu/resmi tatile denk gelen son gunler core.takvim ile
ilk is gunune kaydirilir. "Bugun"e gore kalan gun ve aciliyet durumu hesaplanir.

Capraz besleme (baglam):
  - tevkifat_var  -> 2 No.lu KDV (KDV2) beyannamesi beklenir.
  - bordro_var    -> Muhtasar ve Prim Hizmet Beyannamesi (SGK) beklenir.
  - kdv_var       -> 1 No.lu KDV.
  - damga_var     -> Damga Vergisi beyannamesi.

Tarihler GIB cari uygulamasina gore (2024+):
  KDV1/KDV2 -> izleyen ayin 28'i  |  Muhtasar+SGK / Damga -> izleyen ayin 26'si
  Gecici vergi -> ceyregi izleyen 2. ayin 17'si (4. donem kaldirildi)
  (Ba/Bs bildirim formlari yururlukten kaldirildi -> takvimde yer almaz.)
SON TARIHLER MEVZUAT DEGISIKLIGINDE GUNCELLENMELIDIR.
"""
from datetime import date
from calendar import monthrange
from core import takvim


def _gun(yil, ay, gun):
    """Verilen gun ayda yoksa ay sonuna kirpar."""
    son = monthrange(yil, ay)[1]
    return date(yil, ay, min(gun, son))


def _izleyen_ay(yil, ay):
    return (yil + 1, 1) if ay == 12 else (yil, ay + 1)


def _ceyrek_son_tarih(yil, ay):
    """Donem ayinin ait oldugu gecici vergi ceyregi ve beyan son gunu."""
    if 1 <= ay <= 3:
        return "1. Dönem (Oca-Mar)", _gun(yil, 5, 17)
    if 4 <= ay <= 6:
        return "2. Dönem (Nis-Haz)", _gun(yil, 8, 17)
    if 7 <= ay <= 9:
        return "3. Dönem (Tem-Eyl)", _gun(yil, 11, 17)
    return "Yıllık (4. geçici dönem kaldırıldı)", _gun(yil + 1, 4, 30)


def _durum(kalan):
    if kalan < 0:
        return "gecti"
    if kalan <= 3:
        return "kritik"
    if kalan <= 10:
        return "yaklasiyor"
    return "var"


def _kayit(kod, ad, ilgili, yasal, bugun, tur="aylık", beklenir=True, not_=""):
    efektif, kaydi = takvim.kaydir(yasal)
    kalan = (efektif - bugun).days
    return {
        "kod": kod, "ad": ad, "ilgili": ilgili, "tur": tur,
        "yasal_tarih": yasal.isoformat(), "tarih": efektif.isoformat(),
        "kaydi_mi": kaydi, "kalan_gun": kalan, "durum": _durum(kalan),
        "beklenir": beklenir, "not": not_,
    }


def beyannameler(donem, baglam=None, bugun=None):
    baglam = baglam or {}
    bugun = bugun or date.today()
    yil, ay = int(donem[:4]), int(donem[5:7])
    iy, ia = _izleyen_ay(yil, ay)

    kdv_var = baglam.get("kdv_var", True)
    tevkifat_var = baglam.get("tevkifat_var", False)
    bordro_var = baglam.get("bordro_var", True)
    damga_var = baglam.get("damga_var", True)

    kayitlar = []
    if kdv_var:
        kayitlar.append(_kayit(
            "KDV1", "1 No.lu KDV Beyannamesi", "191/391", _gun(iy, ia, 28), bugun,
            not_="Beyan ve ödeme izleyen ayın 28'i."))
    kayitlar.append(_kayit(
        "KDV2", "2 No.lu KDV Beyannamesi (tevkifat)", "360", _gun(iy, ia, 28), bugun,
        beklenir=tevkifat_var,
        not_=("Tevkifatlı alış tespit edildi — sorumlu sıfatıyla beyan." if tevkifat_var
              else "Tevkifat yoksa verilmez.")))
    kayitlar.append(_kayit(
        "MUHSGK", "Muhtasar ve Prim Hizmet Beyannamesi", "360/361", _gun(iy, ia, 26), bugun,
        beklenir=bordro_var,
        not_=("Bordro/personel tespit edildi — gelir stopajı + SGK." if bordro_var
              else "Personel yoksa stopaj/SGK olmayabilir.")))
    if damga_var:
        kayitlar.append(_kayit(
            "DAMGA", "Damga Vergisi Beyannamesi", "360", _gun(iy, ia, 26), bugun,
            not_="Sürekli damga mükellefiyeti varsa muhtasar ile birlikte."))
    ceyrek_ad, gv_tarih = _ceyrek_son_tarih(yil, ay)
    kayitlar.append(_kayit(
        "GECICI", f"Geçici Vergi — {ceyrek_ad}", "—", gv_tarih, bugun, tur="3 aylık",
        not_="Kurum/gelir geçici vergi; çeyreği izleyen 2. ayın 17'si."))

    aktif = [k for k in kayitlar if k["beklenir"]]
    gecti = [k for k in aktif if k["durum"] == "gecti"]
    kritik = [k for k in aktif if k["durum"] in ("kritik", "yaklasiyor")]
    return {
        "donem": donem, "bugun": bugun.isoformat(),
        "kayitlar": kayitlar,
        "aktif_sayisi": len(aktif),
        "gecti": gecti, "kritik": kritik,
        "gecti_sayisi": len(gecti), "kritik_sayisi": len(kritik),
    }
