# -*- coding: utf-8 -*-
"""
Veri deposu - JSON dosya tabanli (sifir kurulum, lokalde calisir).
Musteri portfoyu + her musterinin donem bazli kapanis durumu.

Yapilar:
  veri/musteriler.json                         -> musteri listesi
  veri/musteriler/{id}/{donem}/durum.json      -> o donemin modul durumlari
  veri/musteriler/{id}/{donem}/yuklenen/       -> yuklenen mizan/banka dosyalari
"""
import os, json, threading
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))      # .../Ay_Kapanis_OS/core
ROOT = os.path.dirname(HERE)                            # .../Ay_Kapanis_OS
# Railway/bulut: kalici disk (Volume) VERI_DIR ile verilir; yoksa yerel veri/.
VERI = os.environ.get("VERI_DIR") or os.path.join(ROOT, "veri")
MUSTERILER_JSON = os.path.join(VERI, "musteriler.json")
KULLANICILAR_JSON = os.path.join(VERI, "kullanicilar.json")
AKTIF_JSON = os.path.join(VERI, "aktif_kullanici.json")

os.makedirs(VERI, exist_ok=True)


# --------------------------------------------------------------------------- #
# Yardimcilar
# --------------------------------------------------------------------------- #
_KILIT = threading.RLock()


def _oku(yol, varsayilan):
    with _KILIT:
        if os.path.exists(yol):
            with open(yol, encoding="utf-8") as f:
                return json.load(f)
        return varsayilan


def _yaz(yol, obj):
    """JSON yazimi - atomik (gecici dosya + replace) ve thread-guvenli.
    Ayni anda birden cok istek ayni durum.json'a yazarsa veri bozulmasin diye."""
    with _KILIT:
        os.makedirs(os.path.dirname(yol), exist_ok=True)
        gecici = yol + ".tmp"
        with open(gecici, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        os.replace(gecici, yol)


def _donem_dizin(musteri_id, donem):
    return os.path.join(VERI, "musteriler", musteri_id, donem)


def yuklenen_dizin(musteri_id, donem):
    yol = os.path.join(_donem_dizin(musteri_id, donem), "yuklenen")
    os.makedirs(yol, exist_ok=True)
    return yol


def _onek(modul_kod, rol=None):
    return f"{modul_kod}__{rol}__" if rol else f"{modul_kod}__"


def yuklenen_kaydet(musteri_id, donem, modul_kod, dosya_adi, icerik, rol=None):
    """Modul icin yuklenen dosyayi kaydeder, yolu doner.
    rol verilirse cok-slotlu modul (or. cari: bizim/karsi) icin ayri saklanir."""
    guvenli = (_onek(modul_kod, rol) + os.path.basename(dosya_adi)).replace(" ", "_")
    yol = os.path.join(yuklenen_dizin(musteri_id, donem), guvenli)
    with open(yol, "wb") as f:
        f.write(icerik)
    return yol


def yuklenen_bul(musteri_id, donem, modul_kod, rol=None):
    """Modulun (varsa rol slotunun) yukledigi dosyanin yolunu doner; yoksa None."""
    d = yuklenen_dizin(musteri_id, donem)
    onek = _onek(modul_kod, rol)
    for ad in sorted(os.listdir(d)):
        if ad.startswith(onek):
            return os.path.join(d, ad)
    return None


# --------------------------------------------------------------------------- #
# Musteri portfoyu
# --------------------------------------------------------------------------- #
def musterileri_getir():
    return _oku(MUSTERILER_JSON, [])


def musteri_getir(musteri_id):
    for m in musterileri_getir():
        if m["id"] == musteri_id:
            return m
    return None


def musteri_ekle(unvan, vergi_no="", erp_tipi="Dosya Yükleme"):
    musteriler = musterileri_getir()
    yeni_id = "M" + str(len(musteriler) + 1).zfill(3)
    kayit = {"id": yeni_id, "unvan": unvan, "vergi_no": vergi_no,
             "erp_tipi": erp_tipi, "aktif": True,
             "akilli_mutabakat": False,
             "olusturma": datetime.now().strftime("%Y-%m-%d")}
    musteriler.append(kayit)
    _yaz(MUSTERILER_JSON, musteriler)
    return kayit


def musteri_guncelle(musteri_id, **alanlar):
    musteriler = musterileri_getir()
    for m in musteriler:
        if m["id"] == musteri_id:
            m.update(alanlar)
            _yaz(MUSTERILER_JSON, musteriler)
            return m
    return None


# --------------------------------------------------------------------------- #
# Kullanicilar + roller (yerel; parolasiz aktif kullanici secimi)
# Roller: "mudur" -> onay/gonder/kilit yetkisi; "eleman" -> sadece taslak uretir.
# --------------------------------------------------------------------------- #
ROLLER = {"mudur": "Muhasebe Müdürü", "eleman": "Muhasebe Elemanı"}


def kullanicilari_getir():
    return _oku(KULLANICILAR_JSON, [])


def kullanici_getir(kullanici_id):
    for k in kullanicilari_getir():
        if k["id"] == kullanici_id:
            return k
    return None


def kullanici_ekle(ad, rol="eleman"):
    kullanicilar = kullanicilari_getir()
    yeni_id = "K" + str(len(kullanicilar) + 1).zfill(3)
    kayit = {"id": yeni_id, "ad": ad, "rol": rol if rol in ROLLER else "eleman"}
    kullanicilar.append(kayit)
    _yaz(KULLANICILAR_JSON, kullanicilar)
    return kayit


def aktif_kullanici():
    """Secili aktif kullaniciyi doner; yoksa ilk kullaniciya duser."""
    kid = _oku(AKTIF_JSON, {}).get("id")
    k = kullanici_getir(kid) if kid else None
    if k:
        return k
    hepsi = kullanicilari_getir()
    return hepsi[0] if hepsi else None


def aktif_kullanici_ayarla(kullanici_id):
    if not kullanici_getir(kullanici_id):
        return None
    _yaz(AKTIF_JSON, {"id": kullanici_id})
    return aktif_kullanici()


def yetkili_mi(islem="onay"):
    """islem 'onay'/'kilit' icin aktif kullanicinin mudur olup olmadigini doner."""
    k = aktif_kullanici()
    return bool(k and k.get("rol") == "mudur")


# --------------------------------------------------------------------------- #
# Donem (kapanis) durumu
# --------------------------------------------------------------------------- #
def _durum_yol(musteri_id, donem):
    return os.path.join(_donem_dizin(musteri_id, donem), "durum.json")


def donem_getir(musteri_id, donem, modul_kodlari):
    """Donem durumunu okur; yoksa bos iskelet uretir (modul listesine gore)."""
    yol = _durum_yol(musteri_id, donem)
    durum = _oku(yol, None)
    if durum is None:
        durum = {
            "donem": donem, "durum": "acik",
            "son_tarih": None,
            "moduller": {k: {"durum": "bekliyor", "ilerleme": 0, "bulgu_sayisi": 0}
                         for k in modul_kodlari},
            "genel_ilerleme": 0,
        }
        _yaz(yol, durum)
    else:
        # Yeni eklenen modulleri sonradan tamamla
        for k in modul_kodlari:
            durum["moduller"].setdefault(
                k, {"durum": "bekliyor", "ilerleme": 0, "bulgu_sayisi": 0})
    return durum


def donem_kaydet(musteri_id, donem, durum):
    durum["genel_ilerleme"] = _genel_ilerleme(durum)
    _yaz(_durum_yol(musteri_id, donem), durum)
    return durum


def modul_durum_guncelle(musteri_id, donem, modul_kod, **alanlar):
    durum = _oku(_durum_yol(musteri_id, donem), None)
    if durum is None:
        return None
    durum["moduller"].setdefault(modul_kod, {})
    durum["moduller"][modul_kod].update(alanlar)
    return donem_kaydet(musteri_id, donem, durum)


def donem_kilitli_mi(musteri_id, donem):
    durum = _oku(_durum_yol(musteri_id, donem), None)
    return bool(durum and durum.get("kilitli"))


def donem_kilit_ayarla(musteri_id, donem, kilitli, kullanici_ad=""):
    """Donemi kilitler/acar; kim-ne-zaman izini durum.json'a yazar."""
    durum = _oku(_durum_yol(musteri_id, donem), None)
    if durum is None:
        return None
    durum["kilitli"] = bool(kilitli)
    durum["kilit_kullanici"] = kullanici_ad
    durum["kilit_zaman"] = datetime.now().strftime("%Y-%m-%d %H:%M") if kilitli else ""
    _yaz(_durum_yol(musteri_id, donem), durum)
    return durum


def fis_durumlari(musteri_id, donem):
    """Donem icin fis onay/gonderme durumlarini doner: {anahtar: {durum, zaman, kullanici}}."""
    durum = _oku(_durum_yol(musteri_id, donem), None)
    if durum is None:
        return {}
    return durum.get("fisler", {})


def fis_durum_guncelle(musteri_id, donem, anahtar, yeni_durum, kullanici_ad=""):
    """Tek fisin durumunu gunceller (taslak/onaylandi/gonderildi/reddedildi)."""
    durum = _oku(_durum_yol(musteri_id, donem), None)
    if durum is None:
        return None
    durum.setdefault("fisler", {})
    durum["fisler"][anahtar] = {"durum": yeni_durum,
                                "zaman": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                "kullanici": kullanici_ad}
    _yaz(_durum_yol(musteri_id, donem), durum)
    return durum["fisler"][anahtar]


def _genel_ilerleme(durum):
    m = durum.get("moduller", {})
    if not m:
        return 0
    return round(sum(x.get("ilerleme", 0) for x in m.values()) / len(m))
