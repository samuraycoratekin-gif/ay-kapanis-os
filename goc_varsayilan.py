# -*- coding: utf-8 -*-
"""
Tek seferlik goc: tek-kiracili veri -> cok-kiracili yapi.

veri/musteriler.json, kullanicilar.json, aktif_kullanici.json, musteriler/
  -> veri/kiracilar/varsayilan/  altina tasinir.

Ayrica kayit defterine (veri/kiracilar.json) "varsayilan" kiraci eklenir
(giris: VARSAYILAN_EPOSTA / GIRIS_PAROLASI). Idempotent: tekrar calistirmak guvenli.
"""
import os
import shutil

from core import depo, kiraci

ROOT_VERI = depo.ROOT_VERI
HEDEF = os.path.join(ROOT_VERI, "kiracilar", "varsayilan")

TASINACAK = ["musteriler.json", "kullanicilar.json", "aktif_kullanici.json", "musteriler"]


def goc():
    os.makedirs(HEDEF, exist_ok=True)
    tasinan = []
    for ad in TASINACAK:
        kaynak = os.path.join(ROOT_VERI, ad)
        hedef = os.path.join(HEDEF, ad)
        if os.path.exists(kaynak) and not os.path.exists(hedef):
            shutil.move(kaynak, hedef)
            tasinan.append(ad)
    return tasinan


def varsayilan_kiraci_seed():
    if kiraci.kiraci_getir("varsayilan"):
        return False
    eposta = os.environ.get("VARSAYILAN_EPOSTA", "ofis@aykapanis.local")
    parola = os.environ.get("GIRIS_PAROLASI") or "1234"
    kayitlar = kiraci.kiracilari_getir()
    kayitlar.append({
        "id": "varsayilan",
        "unvan": "Varsayılan Ofis",
        "tip": "ofis",
        "eposta": eposta,
        "parola_hash": kiraci._hash_parola(parola),
        "paket": "pilot",
        "aktif": True,
        "olusturma": __import__("datetime").datetime.now().strftime("%Y-%m-%d"),
    })
    depo._yaz(kiraci.KIRACILAR_JSON, kayitlar)
    return True


if __name__ == "__main__":
    tasinan = goc()
    seed = varsayilan_kiraci_seed()
    print("Tasinan dosyalar :", tasinan or "(zaten tasinmis)")
    print("Varsayilan kiraci:", "olusturuldu" if seed else "(zaten var)")
    k = kiraci.kiraci_getir("varsayilan")
    if k:
        print(f"Giris            :  {k['eposta']}  /  (GIRIS_PAROLASI veya 1234)")
