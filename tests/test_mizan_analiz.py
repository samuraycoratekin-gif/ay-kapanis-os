# -*- coding: utf-8 -*-
"""M2 Mizan analiz motoru testleri (ters bakiye, gecici, sapma, zorunlu hesap)."""
import unittest

from core import mizan_analiz as ma
from tests._yardim import hesap, mizan


class TestBeklenenYon(unittest.TestCase):
    def test_aktif_borc(self):
        self.assertEqual(ma.beklenen_yon("100"), "+")
        self.assertEqual(ma.beklenen_yon("153"), "+")
        self.assertEqual(ma.beklenen_yon("254"), "+")

    def test_pasif_ozkaynak_alacak(self):
        self.assertEqual(ma.beklenen_yon("300"), "-")
        self.assertEqual(ma.beklenen_yon("320"), "-")
        self.assertEqual(ma.beklenen_yon("500"), "-")

    def test_gelir_gider_6(self):
        self.assertEqual(ma.beklenen_yon("600"), "-")   # gelir -> alacak
        self.assertEqual(ma.beklenen_yon("620"), "+")   # gider -> borc

    def test_yansitma_7_alacak(self):
        self.assertEqual(ma.beklenen_yon("711"), "-")
        self.assertEqual(ma.beklenen_yon("770"), "+")   # gider, yansitma degil

    def test_esnek_kontrol_etmez(self):
        self.assertIsNone(ma.beklenen_yon("131"))
        self.assertIsNone(ma.beklenen_yon("690"))

    def test_kontra_hesaplar(self):
        self.assertEqual(ma.beklenen_yon("257"), "-")   # kontra-aktif
        self.assertEqual(ma.beklenen_yon("501"), "+")   # kontra-pasif

    def test_isimde_eksi_isareti_kontra(self):
        # Aktif grupta adinda "(-)" gecen hesap -> alacak normal
        self.assertEqual(ma.beklenen_yon("255", "DEMIRBAS (-)"), "-")


class TestTersBakiye(unittest.TestCase):
    def test_aktif_alacak_ters(self):
        m = mizan(hesap("100", "KASA", toplam=-8_000))
        r = ma.analiz_et(m)
        kodlar = [x["ana"] for x in r["bulgular"]["ters"]]
        self.assertIn("100", kodlar)

    def test_pasif_borc_ters(self):
        m = mizan(hesap("340", "ALINAN AVANS", toplam=35_000))
        r = ma.analiz_et(m)
        self.assertIn("340", [x["ana"] for x in r["bulgular"]["ters"]])

    def test_esnek_ters_uretmez(self):
        m = mizan(hesap("131", "ORTAKLAR", toplam=-50_000))
        r = ma.analiz_et(m)
        self.assertEqual(r["bulgular"]["ters"], [])

    def test_normal_yon_temiz(self):
        m = mizan(hesap("100", "KASA", toplam=35_000),
                  hesap("320", "SATICI", toplam=-90_000))
        r = ma.analiz_et(m)
        self.assertEqual(r["bulgular"]["ters"], [])


class TestGecici(unittest.TestCase):
    def test_191_391_kapanmamis(self):
        m = mizan(hesap("191", "INDIRILECEK KDV", toplam=96_000),
                  hesap("391", "HESAPLANAN KDV", toplam=-118_000))
        r = ma.analiz_et(m)
        kodlar = [x["ana"] for x in r["bulgular"]["gecici"]]
        self.assertIn("191", kodlar)
        self.assertIn("391", kodlar)

    def test_yansitma_711_gecici(self):
        m = mizan(hesap("711", "YANSITMA", toplam=-50_000))
        r = ma.analiz_et(m)
        self.assertIn("711", [x["ana"] for x in r["bulgular"]["gecici"]])

    def test_kapanmis_gecici_temiz(self):
        m = mizan(hesap("191", "INDIRILECEK KDV", toplam=0.0))
        r = ma.analiz_et(m)
        self.assertEqual(r["bulgular"]["gecici"], [])


class TestSapma(unittest.TestCase):
    def test_ani_giris_onceki_yok(self):
        m = mizan(hesap("689", "OLAGANDISI GIDER",
                        aylik=[0, 0, 0, 0, 220_000]))
        r = ma.analiz_et(m)
        s = [x for x in r["bulgular"]["sapma"] if x["ana"] == "689"]
        self.assertEqual(len(s), 1)
        self.assertIsNone(s[0]["kat"])           # onceki yok -> kat None
        self.assertEqual(s[0]["seri"], [0, 0, 0, 0, 220_000])

    def test_ortalama_kati_sapma(self):
        m = mizan(hesap("153", "TICARI MALLAR",
                        aylik=[50_000, 50_000, 50_000, 50_000, 200_000]))
        r = ma.analiz_et(m)
        s = [x for x in r["bulgular"]["sapma"] if x["ana"] == "153"]
        self.assertEqual(len(s), 1)
        self.assertAlmostEqual(s[0]["kat"], 4.0, places=1)

    def test_min_tutar_altinda_uyari_yok(self):
        m = mizan(hesap("770", "GENEL YONETIM",
                        aylik=[0, 0, 0, 0, 50_000]))   # < 100.000
        r = ma.analiz_et(m)
        self.assertEqual([x for x in r["bulgular"]["sapma"] if x["ana"] == "770"], [])

    def test_normal_artis_sapma_degil(self):
        # Mayis onceki ortalamanin 1.5 kati -> esik %100'u asmaz
        m = mizan(hesap("600", "SATISLAR",
                        aylik=[-100_000, -100_000, -100_000, -100_000, -150_000]))
        r = ma.analiz_et(m)
        self.assertEqual([x for x in r["bulgular"]["sapma"] if x["ana"] == "600"], [])

    def test_gecmis_ay_sicramasi_bulgu_degil(self):
        # 254 Tasitlar Mart'ta 180.000 -> kapanan ay (Mayis) degil, BULGU CIKMAZ
        m = mizan(hesap("254", "TASITLAR", acilis=320_000,
                        aylik=[0, 0, 180_000, 0, 0]))
        r = ma.analiz_et(m)
        self.assertEqual([x for x in r["bulgular"]["sapma"] if x["ana"] == "254"], [])


class TestAylikHareketVeSeri(unittest.TestCase):
    def test_aylik_hareket_toplami(self):
        m = mizan(hesap("100", "KASA", aylik=[10_000, 8_000, 12_000, 9_000, 11_000]),
                  hesap("600", "SATIS", aylik=[0, 0, 0, 0, -5_000]))
        r = ma.analiz_et(m)
        self.assertEqual(r["aylik_hareket"], [10_000, 8_000, 12_000, 9_000, 16_000])


class TestZorunluHesap(unittest.TestCase):
    def test_eksik_hesap_yok_bulgusu(self):
        m = mizan(hesap("100", "KASA", toplam=35_000))
        bulgular = ma.zorunlu_hesap_kontrol(m, zorunlu={"102": "Bankalar"})
        self.assertEqual(len(bulgular), 1)
        self.assertEqual(bulgular[0]["durum"], "yok")

    def test_hareketsiz_hesap_bulgusu(self):
        m = mizan(hesap("770", "GENEL YONETIM", toplam=0.0,
                        aylik=[0, 0, 0, 0, 0]))
        bulgular = ma.zorunlu_hesap_kontrol(m, zorunlu={"770": "Genel Yonetim"})
        self.assertEqual(len(bulgular), 1)
        self.assertEqual(bulgular[0]["durum"], "hareketsiz")

    def test_dolu_hesap_temiz(self):
        m = mizan(hesap("100", "KASA", toplam=35_000, aylik=[1_000, 0, 0, 0, 0]))
        bulgular = ma.zorunlu_hesap_kontrol(m, zorunlu={"100": "Kasa"})
        self.assertEqual(bulgular, [])


if __name__ == "__main__":
    unittest.main()
