# -*- coding: utf-8 -*-
"""
Kiraci (tenant) kayit defteri - cok-kiracili giris.

Kiraci = sisteme giren ofis veya sirket. Her kiracinin verisi
veri/kiracilar/{id}/ altinda izole (bkz. depo.py). Bu modul yalnizca
KIRACI KAYITLARINI (kimlik + hash'li parola) tutar; kiraci-disi (registry)
oldugu icin kok veri dizinine yazar, depo'nun kiraci kapsamina girmez.

Yapi:
  veri/kiracilar.json   -> [{id, unvan, tip, eposta, parola_hash, paket, aktif, olusturma}, ...]

Parola: pbkdf2_sha256, "pbkdf2_sha256$iterasyon$salt_hex$hash_hex" formatinda saklanir.
Duz parola HICBIR yerde tutulmaz.
"""
import os
import hashlib
import secrets
from datetime import datetime

from core import depo

KIRACILAR_JSON = os.path.join(depo.ROOT_VERI, "kiracilar.json")

TIPLER = {"ofis": "Muhasebe Ofisi", "sirket": "Şirket"}
_ITERASYON = 200_000

# Satilabilir moduller (urunler). Kiracinin sahip oldugu modul kodlari
# kayittaki "moduller" listesinde tutulur; capraz satis = bu listeye ekleme.
MODULLER = {
    "ay_kapanis": "Ay Kapanış OS",
    "mutabakat": "Akıllı Mutabakat",
}
# Kaydinda "moduller" alani olmayan (eski) kiraci varsayilan olarak bunu alir.
VARSAYILAN_MODULLER = ["ay_kapanis"]


# --------------------------------------------------------------------------- #
# Parola hash
# --------------------------------------------------------------------------- #
def _hash_parola(parola, salt=None, iterasyon=_ITERASYON):
    salt = salt or secrets.token_bytes(16)
    ozet = hashlib.pbkdf2_hmac("sha256", parola.encode("utf-8"), salt, iterasyon)
    return f"pbkdf2_sha256${iterasyon}${salt.hex()}${ozet.hex()}"


def parola_dogrula(parola, saklanan):
    """Duz parola ile saklanan hash'i sabit-zamanli karsilastirir."""
    try:
        algo, iters, salt_hex, ozet_hex = saklanan.split("$")
        if algo != "pbkdf2_sha256":
            return False
        beklenen = hashlib.pbkdf2_hmac(
            "sha256", parola.encode("utf-8"), bytes.fromhex(salt_hex), int(iters))
        return secrets.compare_digest(beklenen.hex(), ozet_hex)
    except (ValueError, AttributeError):
        return False


# --------------------------------------------------------------------------- #
# Kiraci CRUD
# --------------------------------------------------------------------------- #
def kiracilari_getir():
    return depo._oku(KIRACILAR_JSON, [])


def kiraci_getir(kiraci_id):
    for k in kiracilari_getir():
        if k["id"] == kiraci_id:
            return k
    return None


def kiraci_getir_eposta(eposta):
    e = (eposta or "").strip().lower()
    for k in kiracilari_getir():
        if k.get("eposta", "").lower() == e:
            return k
    return None


def kiraci_ekle(unvan, eposta, parola, tip="ofis", paket="pilot", moduller=None):
    """Yeni kiraci olusturur. Eposta benzersiz olmali.
    moduller: sahip olunan urun kodlari; verilmezse VARSAYILAN_MODULLER."""
    eposta = (eposta or "").strip()
    if not eposta or not parola:
        raise ValueError("Eposta ve parola zorunlu.")
    if kiraci_getir_eposta(eposta):
        raise ValueError("Bu eposta ile kayitli bir kiraci zaten var.")
    kiracilar = kiracilari_getir()
    yeni_id = "T" + str(len(kiracilar) + 1).zfill(3)
    kayit = {
        "id": yeni_id,
        "unvan": unvan,
        "tip": tip if tip in TIPLER else "ofis",
        "eposta": eposta,
        "parola_hash": _hash_parola(parola),
        "paket": paket,
        "moduller": _temiz_moduller(moduller),
        "aktif": True,
        "olusturma": datetime.now().strftime("%Y-%m-%d"),
    }
    kiracilar.append(kayit)
    depo._yaz(KIRACILAR_JSON, kiracilar)
    return kayit


def kiraci_durum_ayarla(kiraci_id, aktif):
    """Kiraciyi aktif/pasif yapar. Pasif kiraci giris yapamaz (bkz. dogrula)."""
    kiracilar = kiracilari_getir()
    for k in kiracilar:
        if k["id"] == kiraci_id:
            k["aktif"] = bool(aktif)
            depo._yaz(KIRACILAR_JSON, kiracilar)
            return k
    return None


def kiraci_parola_guncelle(kiraci_id, yeni_parola):
    kiracilar = kiracilari_getir()
    for k in kiracilar:
        if k["id"] == kiraci_id:
            k["parola_hash"] = _hash_parola(yeni_parola)
            depo._yaz(KIRACILAR_JSON, kiracilar)
            return k
    return None


def kiraci_sil(kiraci_id):
    """Kiraciyi KALICI siler: kayit + veri/kiracilar/<id>/ altindaki TUM veri
    (musteriler, donemler, yuklenen dosyalar, mutabakat kayitlari).

    Korumalar:
      * 'varsayilan' silinemez (uygulama acilisinda yeniden seed edilir).
      * AKTIF kiraci silinemez — once Pasif yapilmali (pasif = arsiv;
        yanlislikla tek tikla silmeye karsi iki asamali akis).
    Cagiran taraf ayrica unvan-yazarak-onay almalidir (bkz. app.api_kiraci_sil)."""
    if kiraci_id == "varsayilan":
        return {"hata": "Varsayılan kiracı silinemez (açılışta yeniden oluşturulur)."}
    k = kiraci_getir(kiraci_id)
    if not k:
        return {"hata": "Kiracı bulunamadı."}
    if k.get("aktif", True):
        return {"hata": "Aktif kiracı silinemez — önce Pasif yapın (arşiv), sonra silin."}
    kalan = [x for x in kiracilari_getir() if x["id"] != kiraci_id]
    depo._yaz(KIRACILAR_JSON, kalan)
    kok = os.path.join(depo.ROOT_VERI, "kiracilar", kiraci_id)
    if os.path.isdir(kok):
        import shutil
        shutil.rmtree(kok, ignore_errors=True)
    return {"ok": True, "silinen": kiraci_id, "unvan": k.get("unvan", "")}


def dogrula(eposta, parola):
    """Giris: eposta+parola dogruysa kiraci kaydini, degilse None doner."""
    k = kiraci_getir_eposta(eposta)
    if not k or not k.get("aktif"):
        return None
    if parola_dogrula(parola, k.get("parola_hash", "")):
        return k
    return None


# --------------------------------------------------------------------------- #
# Moduller (sahip olunan urunler) - capraz satis bayragi
# --------------------------------------------------------------------------- #
def _temiz_moduller(liste):
    """Gecerli modul kodlarini sirayi koruyarak suzer; bos ise varsayilan."""
    if not liste:
        return list(VARSAYILAN_MODULLER)
    temiz = [m for m in liste if m in MODULLER]
    # tekrarlari at, sirayi koru
    gorulen, sonuc = set(), []
    for m in temiz:
        if m not in gorulen:
            gorulen.add(m)
            sonuc.append(m)
    return sonuc or list(VARSAYILAN_MODULLER)


def kiraci_moduller(kiraci_id):
    """Kiracinin sahip oldugu modul kodlari. Alan yoksa (eski kayit) varsayilan."""
    k = kiraci_getir(kiraci_id)
    if not k:
        return []
    return _temiz_moduller(k.get("moduller"))


def modul_var_mi(kiraci_id, modul_kod):
    return modul_kod in kiraci_moduller(kiraci_id)


def kiraci_moduller_ayarla(kiraci_id, moduller):
    """Kiracinin modul listesini gunceller (platform sahibi: capraz satis)."""
    kiracilar = kiracilari_getir()
    for k in kiracilar:
        if k["id"] == kiraci_id:
            k["moduller"] = _temiz_moduller(moduller)
            depo._yaz(KIRACILAR_JSON, kiracilar)
            return k
    return None
