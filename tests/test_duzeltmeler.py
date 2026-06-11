# -*- coding: utf-8 -*-
"""2026-06-11 duzeltmelerinin regresyon testleri.

Kapsam:
  * metin.sayi      : binlik nokta / parantez negatif / TL eki
  * banka_analiz    : ayni-isaret sarti (1:1 ve altkume)
  * banka_oku       : metin tarihlerin date'e cevrilmesi
  * kdv_analiz      : devreden_onceki_190 (ara ay devri dahil, guncel ay haric)
  * fis_uret        : KDV mahsup fisinin ayni devir mantigini kullanmasi,
                      komisyon fis anahtarinin icerik-bazli (kararli) olmasi
  * mizan_oku       : grup(3 hane) + detay satiri birlikte -> cift sayim yok
  * tevkifat        : kdv_orani=0 gecerli oran (falsy-zero %20'ye dusmez)
  * portal token    : imza dogrulama / parametre oynama / rota allowlist
"""
import os
import sys
import tempfile
import unittest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import metin, banka_oku, banka_analiz as ba, kdv_analiz as ka, fis_uret, mizan_oku
from tests._yardim import hesap, mizan


class TestSayi(unittest.TestCase):
    def test_binlik_nokta(self):
        self.assertEqual(metin.sayi("1.234"), 1234.0)

    def test_binlik_coklu(self):
        self.assertEqual(metin.sayi("1.234.567"), 1234567.0)

    def test_ondalik_nokta(self):
        self.assertEqual(metin.sayi("1234.56"), 1234.56)

    def test_tr_format(self):
        self.assertEqual(metin.sayi("1.234,56"), 1234.56)

    def test_kucuk_ondalik(self):
        self.assertEqual(metin.sayi("0.5"), 0.5)

    def test_paren_negatif(self):
        self.assertEqual(metin.sayi("(1.234,56)"), -1234.56)

    def test_tl_eki(self):
        self.assertEqual(metin.sayi("12,50 TL"), 12.5)

    def test_bozuk_metin(self):
        self.assertIsNone(metin.sayi("ABC"))

    def test_sayi_tipi(self):
        self.assertEqual(metin.sayi(1234), 1234.0)


class TestBankaIsaret(unittest.TestCase):
    @staticmethod
    def _h(tutar, gun, ack=""):
        return {"tutar": float(tutar), "tarih": date(2026, 5, gun), "aciklama": ack}

    def test_zit_yon_eslesmez(self):
        r = ba.esle([self._h(500, 3, "GELEN")], [self._h(-500, 3, "GIDEN")])
        self.assertEqual(r["eslesen"], 0)
        self.assertEqual(r["sorunlu"], 2)

    def test_ayni_yon_tarih_toleransta_eslesir(self):
        r = ba.esle([self._h(500, 3)], [self._h(500, 4)])
        self.assertEqual(r["eslesen"], 1)

    def test_altkume_ayni_yon_kapatir(self):
        r = ba.esle([self._h(-1000, 10, "TOPLU ODEME")],
                    [self._h(-600, 9), self._h(-400, 11)])
        self.assertEqual(r["coklu_sayisi"], 1)
        self.assertEqual(r["sorunlu"], 0)

    def test_altkume_zit_yon_kapatamaz(self):
        r = ba.esle([self._h(1000, 10, "GIRIS")],
                    [self._h(-600, 9), self._h(-400, 11)])
        self.assertEqual(r["coklu_sayisi"], 0)
        self.assertEqual(r["sorunlu"], 3)


class TestBankaTarihMetin(unittest.TestCase):
    def test_metin_tarih_cozulur(self):
        self.assertEqual(banka_oku._tarih("15.05.2026"), date(2026, 5, 15))
        self.assertEqual(banka_oku._tarih("2026-05-15"), date(2026, 5, 15))

    def test_cozulemeyen_metin_korunur(self):
        self.assertEqual(banka_oku._tarih("bilinmiyor"), "bilinmiyor")


class TestKdvDevreden(unittest.TestCase):
    def test_ara_ay_devri_dahil(self):
        # Subat'ta 30.000 devir olusmus (190 borc hareketi); acilis 0.
        # Mayis hesabi bu devri 'onceki devreden' SAYMALI (eski kod yilbasi
        # acilisina bakip 0 goruyor, odenecek KDV'yi fazla cikariyordu).
        m = mizan(
            hesap("191", "INDIRILECEK KDV", toplam=50_000, aylik=[0, 0, 0, 0, 50_000]),
            hesap("391", "HESAPLANAN KDV", toplam=-40_000, aylik=[0, 0, 0, 0, -40_000]),
            hesap("190", "DEVREDEN KDV", toplam=30_000, acilis=0.0,
                  aylik=[0, 30_000, 0, 0, 0]),
        )
        self.assertAlmostEqual(ka.devreden_onceki_190(m), 30_000, places=2)
        r = ka.mizandan_kdv(m)
        self.assertEqual(r["sonuc_tip"], "DEVREDEN")
        # 40.000 - 50.000 - 30.000 = -40.000 -> 40.000 devreden
        self.assertAlmostEqual(r["sonuc_tutar"], 40_000, places=2)

    def test_guncel_ay_hareketi_dislanir(self):
        # Mayis mahsubu atilmis (190 mayis +23.400). Onceki devreden yine 72.000.
        m = mizan(
            hesap("191", toplam=0.0, aylik=[0, 0, 0, 0, 86_400]),
            hesap("391", toplam=0.0, aylik=[0, 0, 0, 0, -63_000]),
            hesap("190", toplam=95_400, acilis=72_000, aylik=[0, 0, 0, 0, 23_400]),
        )
        self.assertAlmostEqual(ka.devreden_onceki_190(m), 72_000, places=2)

    def test_fis_uret_ayni_devir_mantigi(self):
        m = mizan(
            hesap("191", toplam=50_000, aylik=[0, 0, 0, 0, 50_000]),
            hesap("391", toplam=-40_000, aylik=[0, 0, 0, 0, -40_000]),
            hesap("190", toplam=30_000, acilis=0.0, aylik=[0, 30_000, 0, 0, 0]),
        )
        f = fis_uret.kdv_mahsup_fisi(m, "2026-05-31")
        self.assertTrue(f["denk"])
        yeni_devir = [s for s in f["satirlar"] if s["hesap"] == "190" and s["borc"] > 0]
        self.assertEqual(len(yeni_devir), 1)
        self.assertAlmostEqual(yeni_devir[0]["borc"], 40_000, places=2)


class TestMizanCiftSayim(unittest.TestCase):
    def test_grup_ve_detay_birlikte(self):
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.append(["Hesap Kodu", "Hesap Adı", "Borç Bakiye", "Alacak Bakiye"])
        ws.append(["770", "GENEL YÖNETİM GİDERLERİ", 1000, 0])   # ozet satiri
        ws.append(["770.01", "KİRA", 600, 0])                    # detay
        ws.append(["770.02", "ELEKTRİK", 400, 0])                # detay
        ws.append(["100", "KASA", 500, 0])                       # detaysiz grup korunur
        with tempfile.TemporaryDirectory() as td:
            yol = os.path.join(td, "mizan.xlsx")
            wb.save(yol)
            m = mizan_oku.oku(yol)
        self.assertAlmostEqual(m["hesaplar"]["770"]["toplam"], 1000, places=2)
        self.assertAlmostEqual(m["hesaplar"]["100"]["toplam"], 500, places=2)
        self.assertEqual(m["hesaplar"]["770"]["ad"], "GENEL YÖNETİM GİDERLERİ")


class TestKomisyonAnahtar(unittest.TestCase):
    def test_icerik_bazli_kararli(self):
        h1 = {"tutar": -250, "tarih": "2026-05-05", "aciklama": "HAVALE KOMISYONU"}
        h2 = {"tutar": -90, "tarih": "2026-05-08", "aciklama": "EFT UCRETI"}
        a = {f["aciklama"]: f["anahtar"] for f in fis_uret.banka_komisyon_fisleri([h1, h2])}
        b = {f["aciklama"]: f["anahtar"] for f in fis_uret.banka_komisyon_fisleri([h2, h1])}
        self.assertEqual(a, b)   # sira degisse de ayni hareket ayni anahtari alir


class TestTevkifatSifirOran(unittest.TestCase):
    def test_sifir_kdv_orani_yirmiye_dusmez(self):
        r = ka.tevkifat([{"islem": "X", "matrah": 100_000,
                          "kdv_orani": 0, "oran_ham": "5/10"}])
        self.assertAlmostEqual(r["toplam_kdv"], 0, places=2)
        self.assertAlmostEqual(r["toplam_tevkif"], 0, places=2)


class TestPortalToken(unittest.TestCase):
    def test_imza_dogrulama_ve_oynama(self):
        from moduller.mutabakat import app_logic as al
        from core import kiraci as kr
        kayitlar = kr.kiracilari_getir()
        if not kayitlar:
            self.skipTest("yerel kiraci kaydi yok")
        kid = kayitlar[0]["id"]
        tok = al.portal_token("120.01", "MUK-001", kid=kid)
        q = {"tok": [tok], "cari": ["120.01"], "musteri": ["MUK-001"]}
        pub = al.portal_coz("/api/form", q)
        self.assertIsNotNone(pub)
        self.assertEqual(pub["kid"], kid)
        self.assertEqual(pub["cari"], "120.01")
        # cari degistirilirse imza tutmaz
        q2 = {"tok": [tok], "cari": ["120.99"], "musteri": ["MUK-001"]}
        self.assertIsNone(al.portal_coz("/api/form", q2))
        # public allowlist disindaki rota acilmaz
        self.assertIsNone(al.portal_coz("/api/gonder", q))
        # POST tarafinda govde dict'iyle ayni dogrulama
        govde = {"tok": tok, "cari": "120.01", "musteri": "MUK-001"}
        self.assertIsNotNone(al.portal_coz("/api/yanit", govde, post=True))
        self.assertIsNone(al.portal_coz("/api/manuel_esle", govde, post=True))


if __name__ == "__main__":
    unittest.main()
