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
ROOT_VERI = os.environ.get("VERI_DIR") or os.path.join(ROOT, "veri")
VERI = ROOT_VERI            # geriye donuk ad; kiraci-disi (registry) erisimi icin kok

os.makedirs(ROOT_VERI, exist_ok=True)

# --------------------------------------------------------------------------- #
# Cok-kiracililik (multi-tenant): aktif kiraci istek basina thread-local'da.
# Tum musteri/kullanici/donem verisi  veri/kiracilar/{kiraci_id}/  altinda izole.
# Kiraci ayarlanmamissa "varsayilan" kiraciya duser (tek-kiracili/gocten once uyum).
# --------------------------------------------------------------------------- #
_CTX = threading.local()


def kiraci_ayarla(kiraci_id):
    """Istek baslangicinda cagrilir; bu thread'in sonraki tum depo erisimlerini kapsar."""
    _CTX.kiraci = kiraci_id or "varsayilan"


def aktif_kiraci():
    return getattr(_CTX, "kiraci", None) or "varsayilan"


def _kveri():
    """Aktif kiracinin veri kok dizini."""
    return os.path.join(ROOT_VERI, "kiracilar", aktif_kiraci())


def _musteriler_json():
    return os.path.join(_kveri(), "musteriler.json")


def _kullanicilar_json():
    return os.path.join(_kveri(), "kullanicilar.json")


def _aktif_json():
    return os.path.join(_kveri(), "aktif_kullanici.json")


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
    return os.path.join(_kveri(), "musteriler", musteri_id, donem)


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
    return _oku(_musteriler_json(), [])


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
    _yaz(_musteriler_json(), musteriler)
    return kayit


def musteri_guncelle(musteri_id, **alanlar):
    musteriler = musterileri_getir()
    for m in musteriler:
        if m["id"] == musteri_id:
            m.update(alanlar)
            _yaz(_musteriler_json(), musteriler)
            return m
    return None


# --------------------------------------------------------------------------- #
# Kullanicilar + roller (kiraci icindeki personel; aktif kullanici secimi)
# Roller (yetki azalan sirada):
#   "yonetici" -> Ofis Yoneticisi: kullanici/ayar yonetimi + onay/kilit (sirket admini)
#   "mudur"    -> Muhasebe Muduru: onay/gonder/kilit
#   "eleman"   -> Muhasebe Elemani: sadece taslak uretir
# --------------------------------------------------------------------------- #
ROLLER = {
    "yonetici": "Ofis Yöneticisi",
    "mudur": "Muhasebe Müdürü",
    "eleman": "Muhasebe Elemanı",
}
# onay/kilit yetkisi olan roller
_YETKILI_ROLLER = {"yonetici", "mudur"}


def kullanicilari_getir():
    return _oku(_kullanicilar_json(), [])


def kullanici_getir(kullanici_id):
    for k in kullanicilari_getir():
        if k["id"] == kullanici_id:
            return k
    return None


def kullanici_ekle(ad, rol="eleman"):
    kullanicilar = kullanicilari_getir()
    # Cakismayan id: mevcut en buyuk numaranin bir fazlasi (silme sonrasi guvenli)
    mevcut = [int(k["id"][1:]) for k in kullanicilar if k["id"][1:].isdigit()]
    yeni_id = "K" + str((max(mevcut) + 1) if mevcut else 1).zfill(3)
    kayit = {"id": yeni_id, "ad": ad, "rol": rol if rol in ROLLER else "eleman"}
    kullanicilar.append(kayit)
    _yaz(_kullanicilar_json(), kullanicilar)
    return kayit


def kullanici_rol_guncelle(kullanici_id, rol):
    if rol not in ROLLER:
        return None
    kullanicilar = kullanicilari_getir()
    for k in kullanicilar:
        if k["id"] == kullanici_id:
            k["rol"] = rol
            _yaz(_kullanicilar_json(), kullanicilar)
            return k
    return None


def kullanici_sil(kullanici_id):
    """Kullaniciyi siler. Son yoneticiyi silmeyi engeller (kilitlenme onlemi)."""
    kullanicilar = kullanicilari_getir()
    hedef = next((k for k in kullanicilar if k["id"] == kullanici_id), None)
    if not hedef:
        return {"hata": "Kullanıcı bulunamadı."}
    if hedef.get("rol") == "yonetici":
        yonetici_sayisi = sum(1 for k in kullanicilar if k.get("rol") == "yonetici")
        if yonetici_sayisi <= 1:
            return {"hata": "Son Ofis Yöneticisi silinemez."}
    kalan = [k for k in kullanicilar if k["id"] != kullanici_id]
    _yaz(_kullanicilar_json(), kalan)
    # Aktif kullanici silindiyse ilk kullaniciya dus
    if _oku(_aktif_json(), {}).get("id") == kullanici_id:
        _yaz(_aktif_json(), {"id": kalan[0]["id"]} if kalan else {})
    return {"ok": True}


def aktif_kullanici():
    """Secili aktif kullaniciyi doner; yoksa ilk kullaniciya duser."""
    kid = _oku(_aktif_json(), {}).get("id")
    k = kullanici_getir(kid) if kid else None
    if k:
        return k
    hepsi = kullanicilari_getir()
    return hepsi[0] if hepsi else None


def aktif_kullanici_ayarla(kullanici_id):
    if not kullanici_getir(kullanici_id):
        return None
    _yaz(_aktif_json(), {"id": kullanici_id})
    return aktif_kullanici()


def yetkili_mi(islem="onay"):
    """islem 'onay'/'kilit' icin aktif kullanicinin yetkili (yonetici/mudur) olup
    olmadigini doner."""
    k = aktif_kullanici()
    return bool(k and k.get("rol") in _YETKILI_ROLLER)


def yonetici_mi():
    """Aktif kullanici Ofis Yoneticisi mi (kullanici/ayar yonetimi yetkisi)."""
    k = aktif_kullanici()
    return bool(k and k.get("rol") == "yonetici")


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


def gecici_vergi_oku(musteri_id, donem):
    """Donem icin gecici vergi KKEG/parametre girislerini doner (musavir girisi)."""
    durum = _oku(_durum_yol(musteri_id, donem), None)
    if durum is None:
        return {}
    return durum.get("gecici_vergi", {})


def gecici_vergi_yaz(musteri_id, donem, veri, kullanici_ad=""):
    """Musavirin girdigi KKEG tutarlari + indirim/mahsup parametrelerini saklar."""
    durum = _oku(_durum_yol(musteri_id, donem), None)
    if durum is None:
        return None
    mevcut = durum.get("gecici_vergi", {})
    mevcut.update(veri)
    mevcut["_guncelleyen"] = kullanici_ad
    mevcut["_zaman"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    durum["gecici_vergi"] = mevcut
    _yaz(_durum_yol(musteri_id, donem), durum)
    return mevcut


def _genel_ilerleme(durum):
    m = durum.get("moduller", {})
    if not m:
        return 0
    return round(sum(x.get("ilerleme", 0) for x in m.values()) / len(m))
