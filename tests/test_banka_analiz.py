# -*- coding: utf-8 -*-
"""M5 Banka esleme testleri (1:1 tarih+tutar, subset-sum 1:N, komisyon, fazlalar)."""
import unittest
from datetime import date

from core import banka_analiz as ba


def _b(tutar, gun, ack=""):
    return {"tutar": float(tutar), "tarih": date(2026, 5, gun), "aciklama": ack}


class TestBirebirEsleme(unittest.TestCase):
    def test_ayni_gun_tutar_eslesir(self):
        banka = [_b(150_000, 3, "TAHSILAT")]
        defter = [_b(-150_000, 3, "TAHSILAT")]
        r = ba.esle(banka, defter)
        self.assertEqual(r["eslesen"], 1)
        self.assertEqual(r["sorunlu"], 0)

    def test_gun_tolerans_disinda_eslesmez(self):
        banka = [_b(150_000, 3, "TAHSILAT")]
        defter = [_b(-150_000, 20, "TAHSILAT")]   # 17 gun fark > GUN_TOL(3)
        r = ba.esle(banka, defter)
        self.assertEqual(r["eslesen"], 0)
        self.assertEqual(r["sorunlu"], 2)


class TestAltkumeEsleme(unittest.TestCase):
    def test_birden_coka_subset_sum(self):
        banka = [_b(120_000, 14, "TOPLU TAHSILAT")]
        defter = [_b(70_000, 13, "FATURA-A"), _b(50_000, 15, "FATURA-B")]
        r = ba.esle(banka, defter)
        self.assertEqual(r["coklu_sayisi"], 1)
        self.assertEqual(r["coklu"][0]["yon"], "1:N")
        self.assertEqual(r["coklu"][0]["adet"], 2)
        self.assertEqual(r["sorunlu"], 0)        # eksik kayit alarmi VERILMEZ


class TestKomisyonVeFazla(unittest.TestCase):
    def test_komisyon_tespiti_ve_fazlalar(self):
        banka = [
            _b(150_000, 3, "TAHSILAT"),
            _b(-250, 5, "HAVALE KOMISYONU"),       # komisyon, defterde yok
        ]
        defter = [
            _b(-150_000, 3, "TAHSILAT"),           # eslesir
            _b(-12_000, 26, "KASA DEVIR"),         # defter fazla
        ]
        r = ba.esle(banka, defter)
        self.assertEqual(r["eslesen"], 1)
        self.assertEqual(len(r["komisyon"]), 1)
        self.assertEqual(len(r["banka_fazla"]), 0)   # komisyon ayri listede
        self.assertEqual(len(r["defter_fazla"]), 1)
        self.assertEqual(r["fis_sayisi"], 1)         # komisyon icin fis onerisi
        self.assertEqual(r["oneriler"][0]["tip"], "komisyon")


if __name__ == "__main__":
    unittest.main()
