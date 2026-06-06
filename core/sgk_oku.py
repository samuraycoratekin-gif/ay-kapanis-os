# -*- coding: utf-8 -*-
"""
SGK istirahat / rapor (gecici is goremezlik) listesi okuyucu + bordro capraz kontrol.

Veri kaynagi: musavirin SGK'dan (e-Devlet/MEDULA) ELLE indirdigi istirahat raporu
dokumu — site KAZIMA YOK (KVKK/ToS riski). Sistemin genel deseni: yuklenen belgeyi
okuyup bordro ile capraz kontrol etmek.

Beklenen kolonlar (esnek baslik tanima):
  Personel/Ad Soyad (veya TC) | Rapor Baslangic | Rapor Bitis | Rapor Gun Sayisi
  (istege bagli: Rapor Turu — istirahat / is kazasi / analik)

Uretilenler:
  * raporlu personel + rapor gunu,
  * isveren (ilk 2 gun) / SGK gun ayrimi (gecici is goremezlik odenegi),
  * SGK'ya eksik gun (kod 01 Istirahat) bildirimi,
  * bordro icmali ile eslesme (raporlu ama bordroda olmayan personel uyarisi).
"""
from core.mizan_oku import _ham_satirlar, _nrm, _sayi
from core.varlik_oku import _bul, _baslik_bul, _hucre, _metin, _tarihe
from core.metin import tr_upper as _up


def oku(yol):
    satirlar = _ham_satirlar(yol)
    gerekli = [lambda c: "PERSONEL" in c or "ADSOYAD" in c or "ISIM" in c or
               c in ("AD", "ADI") or "TC" in c,
               lambda c: "GUN" in c or "ISTIRAHAT" in c or "RAPOR" in c or
               "BASLANGIC" in c or "BITIS" in c or "TARIH" in c]
    hi, nrm = _baslik_bul(satirlar, gerekli)
    if hi is None:
        raise ValueError("SGK rapor listesi başlığı tanınamadı (personel + rapor günü/tarih sütunları yok).")
    h = {
        "ad": _bul(nrm, lambda c: "PERSONEL" in c or "ADSOYAD" in c or "ISIM" in c or c in ("AD", "ADI")),
        "tc": _bul(nrm, lambda c: c == "TC" or "TCKIMLIK" in c or "TCNO" in c),
        "baslangic": _bul(nrm, lambda c: "BASLANGIC" in c or ("ILK" in c and "TARIH" in c) or "BASLAMA" in c),
        "bitis": _bul(nrm, lambda c: "BITIS" in c or "SON" in c and "TARIH" in c),
        "gun": _bul(nrm, lambda c: "GUN" in c),
        "tur": _bul(nrm, lambda c: "TUR" in c or "TIP" in c or "VASIF" in c or "ACIKLAMA" in c),
    }
    satir_list = []
    toplam_gun = 0
    for r in satirlar[hi + 1:]:
        ad = _metin(_hucre(r, h["ad"])) or _metin(_hucre(r, h["tc"]))
        if "TOPLAM" in _nrm(ad):
            continue
        bas = _tarihe(_hucre(r, h["baslangic"]))
        bit = _tarihe(_hucre(r, h["bitis"]))
        gun = _sayi(_hucre(r, h["gun"]))
        if gun is None and bas and bit:
            gun = (bit - bas).days + 1
        if not ad and gun is None:
            continue
        if gun is None or gun <= 0:
            continue
        satir_list.append({
            "ad": ad or "Personel",
            "baslangic": bas.isoformat() if bas else None,
            "bitis": bit.isoformat() if bit else None,
            "gun": int(gun),
            "tur": _metin(_hucre(r, h["tur"])),
        })
        toplam_gun += int(gun)
    if not satir_list:
        raise ValueError("SGK rapor listesinde geçerli rapor satırı bulunamadı.")
    return {
        "kaynak": "SGK İstirahat/Rapor Listesi",
        "satirlar": satir_list,
        "personel_sayisi": len({s["ad"] for s in satir_list}),
        "toplam_gun": toplam_gun,
    }


# --------------------------------------------------------------------------- #
def _tur_sinifla(tur):
    t = _up(tur or "")
    if "KAZA" in t or "MESLEK" in t:
        return "is_kazasi", "İş kazası/meslek hast."
    if "ANALIK" in t or "DOGUM" in t or "HAMILE" in t or "GEBE" in t:
        return "analik", "Analık (doğum)"
    return "istirahat", "İstirahat (hastalık)"


def analiz(sgk, bordro=None):
    """SGK rapor dokumunu bordro ile capraz kontrol eder; uyari/oneri uretir."""
    bordro_adlar = set()
    if bordro:
        for p in bordro.get("satirlar", []):
            bordro_adlar.add(_up(p.get("ad", "")))

    satirlar = []
    t_gun = t_isveren = t_sgk = t_eksik = 0
    eslesmeyen = []
    for s in sgk["satirlar"]:
        tur_kod, tur_et = _tur_sinifla(s["tur"])
        gun = s["gun"]
        # Istirahatte ilk 2 gun isveren oder; is kazasi/analik ilk gunden SGK.
        isveren_gun = min(2, gun) if tur_kod == "istirahat" else 0
        sgk_gun = gun - isveren_gun
        eksik = min(gun, 30)     # SGK'ya eksik gun (kod 01) — ayda en fazla 30
        bordroda = _up(s["ad"]) in bordro_adlar if bordro else None
        if bordro and not bordroda:
            eslesmeyen.append(s["ad"])
        satirlar.append({**s, "tur_kod": tur_kod, "tur_etiket": tur_et,
                         "isveren_gun": isveren_gun, "sgk_gun": sgk_gun,
                         "eksik_gun": eksik, "bordroda": bordroda})
        t_gun += gun
        t_isveren += isveren_gun
        t_sgk += sgk_gun
        t_eksik += eksik

    uyarilar = []
    if t_eksik > 0:
        uyarilar.append({
            "tip": "eksik_gun",
            "ac": f"Toplam {t_eksik} gün rapor — SGK aylık prim ve hizmet belgesinde "
                  f"eksik gün kodu '01 İstirahat' ile bildirilmeli; bordro prim günleri buna göre düşürülmeli."})
    if t_sgk > 0:
        uyarilar.append({
            "tip": "calisilmadi",
            "ac": f"SGK'nın ödeyeceği {t_sgk} gün için 'Çalışılmadığına Dair Bildirim' girilmeli "
                  f"(girilmezse geçici iş göremezlik ödeneği ödenmez)."})
        uyarilar.append({
            "tip": "odenek_mahsup",
            "ac": f"Geçici iş göremezlik ödeneği SGK tarafından personele ödenir; bordroda bu {t_sgk} güne "
                  f"karşılık brüt/net üzerinden mahsup yapılıp 335/136 hesaplarında izlenmeli (mükerrer ödeme olmasın)."})
    if t_isveren > 0:
        uyarilar.append({
            "tip": "isveren_gun",
            "ac": f"İstirahatlerin ilk 2 günleri toplam {t_isveren} gün işveren yükümlülüğü "
                  f"(SGK ödemez); bu günlerin ücreti işverence karşılanır."})
    for ad in eslesmeyen:
        uyarilar.append({
            "tip": "eslesmeyen",
            "ac": f"'{ad}' SGK raporunda var ama bordro icmalinde yok — işten çıkış/eksik bordro olabilir, kontrol edin."})

    return {
        "satirlar": satirlar,
        "personel_sayisi": len({s["ad"] for s in satirlar}),
        "toplam_gun": t_gun,
        "toplam_isveren_gun": t_isveren,
        "toplam_sgk_gun": t_sgk,
        "toplam_eksik_gun": t_eksik,
        "eslesmeyen": eslesmeyen,
        "bordro_var": bordro is not None,
        "uyarilar": uyarilar,
        "bulgu": len(uyarilar),
    }
