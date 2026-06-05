# -*- coding: utf-8 -*-
"""Modul kayit (registry) duman testi: tum moduller import olur, sira ve panel calisir."""
import unittest

from core import moduller


class TestRegistry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        moduller.yukle_hepsi()

    def test_oniki_modul_kayitli(self):
        self.assertEqual(len(moduller.liste()), 12)

    def test_sira_artan(self):
        siralar = [m.sira for m in moduller.liste()]
        self.assertEqual(siralar, sorted(siralar))

    def test_m2_ilk_m8_son(self):
        kodlar = moduller.kodlar()
        self.assertEqual(kodlar[0], "m2_mizan")
        self.assertEqual(kodlar[-1], "m8_dosya")

    def test_yukleme_gateli_moduller_panel_uretir(self):
        # Dosya yukleme bekleyen moduller hazir=False'ta yukleme alani dondurur
        for kod in ("m2_mizan", "m3_cari", "m4_gib_kdv", "m5_banka"):
            html = moduller.getir(kod).panel_html({"hazir": False})
            self.assertIsInstance(html, str)
            self.assertGreater(len(html), 0)

    def test_mizan_yukleme_alani(self):
        m = moduller.getir("m2_mizan")
        html = m.panel_html({"hazir": False})
        self.assertIn("Mizan Seç", html)


if __name__ == "__main__":
    unittest.main()
