# -*- coding: utf-8 -*-
"""Musteri arsivleme / kalici silme / ID uretimi testleri.

depo.ROOT_VERI gecici dizine yonlendirilir; gercek veri/ klasorune dokunulmaz.
"""
import os
import sys
import tempfile
import shutil
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import depo


class TestMusteriYonetim(unittest.TestCase):
    def setUp(self):
        self._eski_root = depo.ROOT_VERI
        self._tmp = tempfile.mkdtemp(prefix="aykap_test_")
        depo.ROOT_VERI = self._tmp
        depo.kiraci_ayarla("testkiraci")

    def tearDown(self):
        depo.ROOT_VERI = self._eski_root
        depo.kiraci_ayarla(None)
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_id_silme_sonrasi_cakismaz(self):
        m1 = depo.musteri_ekle("Firma Bir")
        m2 = depo.musteri_ekle("Firma Iki")
        self.assertEqual([m1["id"], m2["id"]], ["M001", "M002"])
        r = depo.musteri_sil("M001")
        self.assertTrue(r.get("ok"))
        m3 = depo.musteri_ekle("Firma Uc")
        # len+1 olsaydi M002 ile CAKISIRDI; max+1 ile M003 gelmeli.
        self.assertEqual(m3["id"], "M003")

    def test_arsivle_ve_geri_al(self):
        m = depo.musteri_ekle("Arsiv Firma")
        depo.musteri_arsiv_ayarla(m["id"], True)
        self.assertFalse(depo.musteri_getir(m["id"]).get("aktif"))
        depo.musteri_arsiv_ayarla(m["id"], False)
        self.assertTrue(depo.musteri_getir(m["id"]).get("aktif"))

    def test_kilitli_donem_silmeyi_engeller(self):
        m = depo.musteri_ekle("Kilitli Firma")
        depo.donem_getir(m["id"], "2026-05", ["m2_mizan"])
        depo.donem_kilit_ayarla(m["id"], "2026-05", True, "Test Mudur")
        r = depo.musteri_sil(m["id"])
        self.assertIn("hata", r)
        self.assertIn("2026-05", r["hata"])
        # kilidi ac -> silinebilir; klasor de kalkmali
        depo.donem_kilit_ayarla(m["id"], "2026-05", False, "Test Mudur")
        r2 = depo.musteri_sil(m["id"])
        self.assertTrue(r2.get("ok"))
        self.assertIsNone(depo.musteri_getir(m["id"]))
        kok = os.path.join(depo._kveri(), "musteriler", m["id"])
        self.assertFalse(os.path.isdir(kok))

    def test_olmayan_musteri(self):
        self.assertIn("hata", depo.musteri_sil("M999"))


if __name__ == "__main__":
    unittest.main()
