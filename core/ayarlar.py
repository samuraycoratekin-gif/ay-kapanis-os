# -*- coding: utf-8 -*-
"""
Dinamik ayarlar - kod icinde sabit kodlanan esik/liste degerlerinin tek
noktadan (veri/ayarlar.json) yonetimi. Dosya yoksa VARSAYILAN kullanilir;
kullanici ofis panosundan degistirdiginde JSON'a yazilir.

Su an yalnizca Bos Zorunlu Hesap kontrolu icin gerekli alanlar tanimli;
diger moduller de zamanla bu katmana tasinabilir.
"""
import os, json

from core import depo


def _ayar_json():
    """Aktif kiracinin ayar dosyasi (cok-kiracili izolasyon)."""
    return os.path.join(depo._kveri(), "ayarlar.json")

VARSAYILAN = {
    # Kiraci kurulum (onboarding) durumu. Yeni kiraci ilk girisinde sihirbaz
    # acilir; tamamlaninca kurulum_tamam=True olur ve dogrudan panoya gecilir.
    "kurulum_tamam": False,
    "ofis_adi": "Ay Kapanış OS",       # kiraci goruntuleme adi (panoda baslik)
    "erp_tipi": "",                    # en sik kullanilan muhasebe programi (varsayilan)
    "erp_paket": "",                  # ERP alt-paketi (orn. luca: malimusavir | koza)
    "erp_baglanti": "",               # baglama yontemi: api | oauth | dosya | yakinda
    "erp_baglanti_ozet": {},          # SIR olmayan alanlar (endpoint, kullanici) - ekranda gosterilebilir
    "erp_kimlik_sifreli": "",         # SIR alanlar (sifre/secret) -> kasa ile sifreli; geri dondurulmez

    # Donem sonunda mizanda mutlaka hareket/bakiye beklenen kontrol hesaplari.
    # ana_kod -> insana okunur etiket. "Bos" ise SOFT uyari uretilir.
    "zorunlu_hesaplar": {
        "100": "Kasa",
        "102": "Bankalar",
        "320": "Satıcılar",
        "360": "Ödenecek Vergi ve Fonlar",
        "361": "Ödenecek Sosyal Güvenlik Kesintileri",
        "770": "Genel Yönetim Giderleri",
    },
    "zorunlu_hesap_tolerans": 1.0,   # TL; bu altindaki bakiye/hareket "bos" sayilir

    # Mizan anormal sapma taramasi (M2): guncel ay net hareketi onceki aylar
    # ortalamasini bu yuzde kadar asarsa VE tutar alt limiti gecerse uyari.
    "mizan_sapma_yuzde": 100,            # %; 100 = onceki ort.'nin 2 kati
    "mizan_sapma_min_tutar": 100000.0,   # TL; bu altindaki sapma raporlanmaz

    # KDV tevkifat (M4): listede oran bulunamayan kaleme uygulanacak varsayilan.
    "tevkifat_varsayilan_pay": 5,
    "tevkifat_varsayilan_payda": 10,

    # KDV matrah/oran tutarlilik denetimi (M4). Yanlis-pozitifi azaltmak icin
    # hem yuzde band hem min TL esigi birlikte uygulanir: ikisi de asilirsa uyari.
    "kdv_oran_tolerans_yuzde": 2.0,    # %; efektif KDV beklenenden bu kadar saparsa
    "kdv_tutar_tolerans": 1000.0,      # TL; ve fark bu tutari da gecerse uyari
    # Gecerli sayilan KDV oranlari (% ). Bu liste disindaki oran "oran disi" uyarisi
    # uretir; eski oranlar (8/18) "dogrula" seviyesinde isaretlenir.
    "kdv_gecerli_oranlar": [0, 1, 10, 20],
    "kdv_eski_oranlar": [8, 18],

    # Stok / Maliyet kontrolu (M13). Mizandan beslenir, ek yukleme gerekmez.
    "stok_brut_kar_alt_yuzde": 0.0,    # %; brut kar marji bunun altinda -> zararina satis uyarisi
    "stok_brut_kar_ust_yuzde": 85.0,   # %; bunun ustunde -> maliyet eksik kaydi suphesi
    "stok_devir_ay_esik": 12.0,        # ay; donem sonu stok / aylik ort. SMM bunu asarsa atil stok
    "stok_min_tutar": 1000.0,          # TL; bu altindaki stok/maliyet bakiyesi denetlenmez

    # Enflasyon duzeltmesi (M10). Yi-UFE tablosu enflasyon.py icinde sabit.
    "enflasyon_uygula": True,          # donem enflasyon duzeltmesi kapsaminda mi
    "enflasyon_onem_tutar": 1000.0,    # TL; bu altindaki duzeltme farki raporlanmaz

    # Bordro <-> Muhasebe mutabakati (M12).
    "bordro_tolerans": 1.0,            # TL; icmal ile mizan farki bunu asarsa uyari
}


def _derin_birlestir(taban, ust):
    """ust degerleri taban uzerine biner; dict ise ic ice birlestirir."""
    sonuc = dict(taban)
    for k, v in (ust or {}).items():
        if isinstance(v, dict) and isinstance(sonuc.get(k), dict):
            sonuc[k] = _derin_birlestir(sonuc[k], v)
        else:
            sonuc[k] = v
    return sonuc


def oku():
    """VARSAYILAN ustune veri/ayarlar.json'daki kullanici degerlerini bindirir."""
    kayitli = {}
    yol = _ayar_json()
    if os.path.exists(yol):
        try:
            with open(yol, encoding="utf-8") as f:
                kayitli = json.load(f)
        except Exception:
            kayitli = {}
    sonuc = _derin_birlestir(VARSAYILAN, kayitli)
    # zorunlu_hesaplar kullanici tarafindan kaydedildiyse TAMAMEN onunki gecerli:
    # deep-merge varsayilan hesaplari geri getirmesin, kullanici silebilsin.
    if isinstance(kayitli.get("zorunlu_hesaplar"), dict):
        sonuc["zorunlu_hesaplar"] = kayitli["zorunlu_hesaplar"]
    return sonuc


def yaz(yeni):
    """Kullanici ayarlarini JSON'a yazar (yalnizca verilen alanlar)."""
    yol = _ayar_json()
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    with open(yol, "w", encoding="utf-8") as f:
        json.dump(yeni, f, ensure_ascii=False, indent=2)
    return oku()
