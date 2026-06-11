# -*- coding: utf-8 -*-
"""M4 KDV motoru testleri (190 devreden zinciri, GIB karsilastirma, tevkifat, matrah/oran)."""
import unittest

from core import kdv_analiz as ka
from tests._yardim import hesap, mizan


class TestMizandanKDV(unittest.TestCase):
    def test_odenecek_pozisyon(self):
        m = mizan(
            hesap("191", "INDIRILECEK KDV", toplam=96_000, aylik=[0, 0, 0, 0, 96_000]),
            hesap("391", "HESAPLANAN KDV", toplam=-118_000, aylik=[0, 0, 0, 0, -118_000]),
            hesap("190", "DEVREDEN KDV", toplam=0.0, acilis=0.0),
        )
        r = ka.mizandan_kdv(m)
        self.assertEqual(r["sonuc_tip"], "ODENECEK")
        self.assertAlmostEqual(r["sonuc_tutar"], 22_000, places=2)
        self.assertEqual(r["devir_durum"], "yok")

    def test_devreden_mahsup_bekliyor(self):
        m = mizan(
            hesap("191", "INDIRILECEK KDV", toplam=86_400, aylik=[0, 0, 0, 0, 86_400]),
            hesap("391", "HESAPLANAN KDV", toplam=-63_000, aylik=[0, 0, 0, 0, -63_000]),
            hesap("190", "DEVREDEN KDV", toplam=72_000, acilis=72_000),
        )
        r = ka.mizandan_kdv(m)
        self.assertEqual(r["sonuc_tip"], "DEVREDEN")
        self.assertAlmostEqual(r["sonuc_tutar"], 95_400, places=2)
        self.assertEqual(r["devir_durum"], "bekliyor")
        self.assertFalse(r["mahsup_yapildi"])
        self.assertAlmostEqual(r["beklenen_devreden"], 95_400, places=2)

    def test_devreden_mahsup_uygun(self):
        # 191/391 kapanmis (mahsup yapilmis), 190 = beklenen devir.
        # Gercek kumule mizanda mahsup, 190'in MAYIS hareketinde gorunur
        # (72.000 acilis + 23.400 mayis = 95.400); onceki devreden = 72.000.
        m = mizan(
            hesap("191", "INDIRILECEK KDV", toplam=0.0, aylik=[0, 0, 0, 0, 86_400]),
            hesap("391", "HESAPLANAN KDV", toplam=0.0, aylik=[0, 0, 0, 0, -63_000]),
            hesap("190", "DEVREDEN KDV", toplam=95_400, acilis=72_000,
                  aylik=[0, 0, 0, 0, 23_400]),
        )
        r = ka.mizandan_kdv(m)
        self.assertTrue(r["mahsup_yapildi"])
        self.assertEqual(r["devir_durum"], "uygun")

    def test_191_391_acik_mahsup_uyarisi(self):
        m = mizan(
            hesap("191", "INDIRILECEK KDV", toplam=96_000, aylik=[0, 0, 0, 0, 96_000]),
            hesap("391", "HESAPLANAN KDV", toplam=-118_000, aylik=[0, 0, 0, 0, -118_000]),
        )
        r = ka.mizandan_kdv(m)
        tipler = [u["tip"] for u in r["uyarilar"]]
        self.assertIn("mahsup", tipler)


class TestGibKarsilastir(unittest.TestCase):
    def setUp(self):
        self.gib = [
            {"belge_no": "GIB-1", "tutar": 72_000, "cari_adi": "A"},
            {"belge_no": "GIB-2", "tutar": 64_000, "cari_adi": "B"},
            {"belge_no": "GIB-3", "tutar": 38_000, "cari_adi": "C"},   # defterde yok
        ]
        self.defter = [
            {"belge_no": "GIB-1", "tutar": 72_000},                    # eslesen
            {"belge_no": "GIB-2", "tutar": 58_000},                    # tutar farki
            {"belge_no": "EAR-9", "tutar": 8_500, "belge_tipi": "e-Arşiv"},   # beklenen
            {"belge_no": "DFT-9", "tutar": 12_000, "belge_tipi": "e-Fatura"}, # supheli
        ]

    def test_eslesme_dagilimi(self):
        r = ka.gib_karsilastir(self.gib, self.defter)
        self.assertEqual(r["eslesen"], 1)
        self.assertEqual(len(r["eksik_defter"]), 1)
        self.assertEqual(r["eksik_defter"][0]["belge_no"], "GIB-3")
        self.assertEqual(len(r["tutar_farki"]), 1)
        self.assertEqual(len(r["fazla_defter"]), 1)
        self.assertEqual(r["fazla_defter"][0]["belge_no"], "DFT-9")
        self.assertEqual(len(r["earsiv_defter"]), 1)

    def test_kayip_kdv_tahmini(self):
        r = ka.gib_karsilastir(self.gib, self.defter)
        # 38.000 * 0.20 / 1.20
        self.assertAlmostEqual(r["tahmini_kayip_kdv"], 6_333.33, places=2)


class TestTevkifat(unittest.TestCase):
    def test_listede_oran_ve_varsayilan(self):
        kalemler = [
            {"islem": "Temizlik hizmeti", "matrah": 40_000, "kdv_orani": 0.20, "oran_ham": "9/10"},
            {"islem": "İşgücü temin hizmeti", "matrah": 60_000, "kdv_orani": 0.20, "oran_ham": ""},
        ]
        r = ka.tevkifat(kalemler)
        self.assertAlmostEqual(r["toplam_tevkif"], 18_000, places=2)
        self.assertAlmostEqual(r["toplam_indirilecek"], 2_000, places=2)
        self.assertEqual(r["satirlar"][0]["kaynak"], "liste")
        self.assertEqual(r["satirlar"][1]["kaynak"], "varsayilan")
        self.assertTrue(any(u["tip"] == "varsayilan" for u in r["uyarilar"]))


class TestMatrahOranDenetim(unittest.TestCase):
    def test_oran_ve_satir_uyarilari(self):
        kalemler = [
            {"tur": "satis", "matrah": 100_000, "oran": 20, "kdv": 20_000, "aciklama": "dogru"},
            {"tur": "satis", "matrah": 40_000, "oran": 20, "kdv": 5_500, "aciklama": "hatali"},
            {"tur": "satis", "matrah": 30_000, "oran": 18, "kdv": 5_400, "aciklama": "eski"},
            {"tur": "alis", "matrah": 15_000, "oran": None, "kdv": None, "aciklama": "bos"},
        ]
        r = ka.matrah_oran_denetim(kalemler)
        self.assertEqual(len(r["satir_uyari"]), 1)
        self.assertEqual(len(r["oran_uyari"]), 2)   # %18 dogrula + bos oran_disi
        self.assertFalse(r["mizan_var"])
        self.assertEqual(r["bulgu"], 3)


if __name__ == "__main__":
    unittest.main()
