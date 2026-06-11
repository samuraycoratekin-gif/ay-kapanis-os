# -*- coding: utf-8 -*-
"""Kiraci kalici silme testleri (pasif sarti, varsayilan korumasi, klasor temizligi).

depo.ROOT_VERI ve kiraci.KIRACILAR_JSON gecici dizine yonlendirilir;
gercek veri/ klasorune dokunulmaz.
"""
import os
import sys
import tempfile
import shutil
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import depo, kiraci


class TestKiraciSil(unittest.TestCase):
    def setUp(self):
        self._eski_root = depo.ROOT_VERI
        self._eski_json = kiraci.KIRACILAR_JSON
        self._tmp = tempfile.mkdtemp(prefix="aykap_kiraci_")
        depo.ROOT_VERI = self._tmp
        kiraci.KIRACILAR_JSON = os.path.join(self._tmp, "kiracilar.json")
        depo.kiraci_ayarla(None)

    def tearDown(self):
        depo.ROOT_VERI = self._eski_root
        kiraci.KIRACILAR_JSON = self._eski_json
        depo.kiraci_ayarla(None)
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _kiraci_ve_veri(self):
        k = kiraci.kiraci_ekle("Test Ofis", "t@x.com", "1234")
        depo.kiraci_ayarla(k["id"])
        depo.kullanici_ekle("Yonetici", "yonetici")   # kiraci klasoru olussun
        return k

    def test_aktifken_silinemez(self):
        k = self._kiraci_ve_veri()
        r = kiraci.kiraci_sil(k["id"])
        self.assertIn("hata", r)
        self.assertIn("Pasif", r["hata"])

    def test_pasif_silinir_klasor_kalkar(self):
        k = self._kiraci_ve_veri()
        kok = os.path.join(depo.ROOT_VERI, "kiracilar", k["id"])
        self.assertTrue(os.path.isdir(kok))
        kiraci.kiraci_durum_ayarla(k["id"], False)
        r = kiraci.kiraci_sil(k["id"])
        self.assertTrue(r.get("ok"))
        self.assertEqual(r["unvan"], "Test Ofis")
        self.assertIsNone(kiraci.kiraci_getir(k["id"]))
        self.assertFalse(os.path.isdir(kok))

    def test_varsayilan_korunur(self):
        r = kiraci.kiraci_sil("varsayilan")
        self.assertIn("hata", r)

    def test_olmayan_kiraci(self):
        self.assertIn("hata", kiraci.kiraci_sil("T999"))


if __name__ == "__main__":
    unittest.main()
