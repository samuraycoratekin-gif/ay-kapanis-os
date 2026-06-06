# -*- coding: utf-8 -*-
"""Toplanti demosu hazirligi: test_veri/ altindaki 4 firmanin dosyalarini
uygulama deposuna (veri/) dogru modul+rol slotlarina yukler. Boylece demoda
her modul tiklayinca dolu gelir. Calistir:  python -X utf8 demo_hazirla.py
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from core import depo

DONEM = "2026-05"

# Klasor -> musteri id (seed sirasi: Ornek=M001, Demir=M002, Gul=M003, Ceyhan=M004)
KLASOR_MUSTERI = {
    "01_Ornek_Sanayi": "M001",
    "02_Demir_Celik": "M002",
    "03_Gul_Plastik": "M003",
    "04_Ceyhan_Lojistik": "M004",
}

# Dosya adi oneki -> (modul_kod, rol)
DOSYA_SLOT = {
    "1_Mizan": ("m2_mizan", None),
    "2_Cari_Bizim_Defter": ("m3_cari", "bizim"),
    "3_Cari_Karsi_Ekstre": ("m3_cari", "karsi"),
    "4_GIB_eFatura_Listesi": ("m4_gib_kdv", "gib"),
    "5_Defter_Alis_Faturalari": ("m4_gib_kdv", "defter"),
    "6_Banka_Ekstresi": ("m5_banka", "banka"),
    "7_Banka_Defteri_102": ("m5_banka", "defter"),
    "8_Demirbas_Listesi": ("m6_fis", "demirbas"),
    "9_Dovizli_Bakiyeler": ("m6_fis", "dovizli"),
    "10_Senet_Cek_Listesi": ("m6_fis", "senet"),
    "11_Tevkifat_Listesi": ("m4_gib_kdv", "tevkifat"),
    "12_KDV_Matrah_Dokumu": ("m4_gib_kdv", "kdv_matrah"),
    "13_Bordro_Icmal": ("m12_bordro", "icmal"),
    "14_Kredi_Odeme_Plani": ("m5_banka", "kredi"),
    "15_SGK_Rapor_Listesi": ("m12_bordro", "sgk"),
}

# GIB eFatura ayni dosya m7_eksik icin de gib/defter rol bekliyor; m4 ile ortak.
# m6_fis rolleri (senet) m9_finansal'da da kullaniliyor — ayni slot.


def _slot_bul(dosya_adi):
    for onek, slot in DOSYA_SLOT.items():
        if dosya_adi.startswith(onek):
            return slot
    return None


def main():
    kok = os.path.join(HERE, "test_veri")
    if not os.path.isdir(kok):
        print("test_veri/ bulunamadi."); return
    musteriler = {m["id"] for m in depo.musterileri_getir()}
    toplam = 0
    for klasor, mid in KLASOR_MUSTERI.items():
        yol = os.path.join(kok, klasor)
        if not os.path.isdir(yol):
            print(f"  ATLA {klasor}: klasor yok"); continue
        if mid not in musteriler:
            print(f"  UYARI {mid} ({klasor}) musteri listesinde yok — once app.py seed olmali")
        n = 0
        for ad in sorted(os.listdir(yol)):
            if not ad.lower().endswith((".xlsx", ".xls")):
                continue
            slot = _slot_bul(ad)
            if not slot:
                continue
            kod, rol = slot
            with open(os.path.join(yol, ad), "rb") as f:
                icerik = f.read()
            depo.yuklenen_kaydet(mid, DONEM, kod, ad, icerik, rol=rol)
            n += 1
        # Ek: m4 gib/defter rolleri m7_eksik tarafindan da kullaniliyor (ayni kod) — zaten yuklendi.
        print(f"  {mid} <- {klasor}: {n} dosya yuklendi")
        toplam += n
    print(f"TOPLAM {toplam} dosya yuklendi. Donem={DONEM}")
    print("Tarayicida sayfayi yenile; modullere tiklayinca dolu gelecek.")


if __name__ == "__main__":
    main()
