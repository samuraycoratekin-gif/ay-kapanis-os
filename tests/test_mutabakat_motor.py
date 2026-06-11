# -*- coding: utf-8 -*-
"""Mutabakat motoru regresyon testleri (2026-06-11 incelemesi).

Kapsam:
  * yardimcilar : norm_belge / sayi_cekirdek / yakin toleransi
  * cari_esle   : EXACT, FUZZY (format + tarih kaymasi), TUTAR_FARKI,
                  SUBSET_SUM (parcali odeme), EKSIK_KARSIDA / EKSIK_BIZDE,
                  tip (FATURA/ODEME) ayrimi
  * cari_durum  : triyaj onceligi (EKSIK BELGE > TUTAR FARKLI > MUTABIK)
  * fark_tutari : kaba acik gostergesi
  * gib.kontrol : GIB hakemli 3 asamali kontrol - hata sahibi etiketi
                  (ASAMA0/BIZ, ASAMA1/KARSI, UYARI, ASAMA2 yonlendirmesi)

Senaryolar prototipteki veri_uret.py kurgusundan uyarlanmistir
(120.01 exact, 120.03 fuzzy, 120.04 tutar farki, 120.05 subset-sum,
120.07 eksik belge).
"""
import os
import sys
import tempfile
import unittest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from moduller.mutabakat import motor as m
from moduller.mutabakat import gib


def kayit(belge_no, tutar, tip="FATURA", belge_tipi="e-Arsiv",
          tarih=None, cari="120.99", adi="Test Cari A.S."):
    """cari_esle'nin bekledigi bicimde (motor.oku ciktisina denk) tek kayit."""
    return {
        "cari_kodu": cari, "cari_adi": adi,
        "tarih": tarih or date(2026, 5, 10),
        "belge_no": belge_no, "belge_tipi": belge_tipi,
        "aciklama": "", "tutar": float(tutar), "tip": tip,
        "_id": 0, "_eslesti": False,
    }


def tipler(bulgular):
    return [b[0] for b in bulgular]


class TestYardimcilar(unittest.TestCase):
    def test_norm_belge(self):
        self.assertEqual(m.norm_belge(" ft-2026/00318 "), "FT202600318")

    def test_sayi_cekirdek_format_yutar(self):
        # 'FT-2026-00318' ile '318' ayni cekirdege iner (bastaki sifirlar atilir)
        self.assertEqual(m.sayi_cekirdek("FT-2026-00318"), 318)
        self.assertEqual(m.sayi_cekirdek("318"), 318)

    def test_sayi_cekirdek_rakamsiz(self):
        self.assertIsNone(m.sayi_cekirdek("ABC"))

    def test_yakin_toleransi(self):
        # TOL = 0.01 TL; tam sinir (100.01) float acilimina hassas oldugundan
        # sozlesme sinirin net icinden ve disindan test edilir.
        self.assertTrue(m.yakin(100.00, 100.005))
        self.assertFalse(m.yakin(100.00, 100.02))


class TestCariEsle(unittest.TestCase):
    def test_exact(self):
        b = [kayit("FT-2026-00101", 12500.0, belge_tipi="e-Fatura")]
        k = [kayit("FT-2026-00101", 12500.0, belge_tipi="e-Fatura")]
        bulgular = m.cari_esle(b, k)
        self.assertEqual(tipler(bulgular), ["EXACT"])
        self.assertEqual(m.cari_durum(bulgular), "MUTABIK")

    def test_exact_normalize_format_farki(self):
        # Ayni evrak no farkli yazimla: normalize ikisini esitler
        b = [kayit("FT 2026-00101", 12500.0)]
        k = [kayit("ft-2026/00101", 12500.0)]
        self.assertEqual(tipler(m.cari_esle(b, k)), ["EXACT"])

    def test_fuzzy_cekirdek_ve_tarih_kaymasi(self):
        # 120.03 kurgusu: bizde 'FT-2026-00318', karsida '318', 3 gun kayma
        b = [kayit("FT-2026-00318", 7400.0, tarih=date(2026, 5, 12))]
        k = [kayit("318", 7400.0, tarih=date(2026, 5, 15))]
        bulgular = m.cari_esle(b, k)
        self.assertEqual(tipler(bulgular), ["FUZZY"])
        self.assertIn("tarih", bulgular[0][3])
        self.assertEqual(m.cari_durum(bulgular), "MUTABIK")

    def test_tutar_farki(self):
        # 120.04 kurgusu: ayni belge, 900 TL fark
        b = [kayit("FT-2026-00451", 12500.0)]
        k = [kayit("FT-2026-00451", 11600.0)]
        bulgular = m.cari_esle(b, k)
        self.assertEqual(tipler(bulgular), ["TUTAR_FARKI"])
        self.assertEqual(m.cari_durum(bulgular), "TUTAR FARKLI")
        self.assertAlmostEqual(m.fark_tutari(bulgular), 900.0, places=2)

    def test_subset_sum_parcali_odeme(self):
        # 120.05 kurgusu: bizde 3 parca odeme, karsida tek toplu tahsilat
        b = [kayit("ODM-1", 10000.0, tip="ODEME", belge_tipi="Dekont"),
             kayit("ODM-2", 15000.0, tip="ODEME", belge_tipi="Dekont"),
             kayit("ODM-3", 25000.0, tip="ODEME", belge_tipi="Dekont")]
        k = [kayit("DEK-77001", 50000.0, tip="ODEME", belge_tipi="Dekont")]
        bulgular = m.cari_esle(b, k)
        self.assertEqual(tipler(bulgular), ["SUBSET_SUM"])
        self.assertEqual(m.cari_durum(bulgular), "MUTABIK")

    def test_eksik_karsida(self):
        # 120.07 kurgusu: fatura bizde var, karsi ekstrede yok
        bulgular = m.cari_esle([kayit("FT-2026-00777", 5000.0)], [])
        self.assertEqual(tipler(bulgular), ["EKSIK_KARSIDA"])
        self.assertEqual(m.cari_durum(bulgular), "EKSIK BELGE")
        self.assertAlmostEqual(m.fark_tutari(bulgular), 5000.0, places=2)

    def test_eksik_bizde(self):
        bulgular = m.cari_esle([], [kayit("FT-2026-00888", 3000.0)])
        self.assertEqual(tipler(bulgular), ["EKSIK_BIZDE"])
        self.assertEqual(m.cari_durum(bulgular), "EKSIK BELGE")

    def test_tip_ayrimi_fatura_odeme_eslesmez(self):
        # Ayni belge no + tutar bile olsa FATURA ile ODEME eslestirilmez
        b = [kayit("X1", 5000.0, tip="FATURA")]
        k = [kayit("X1", 5000.0, tip="ODEME", belge_tipi="Dekont")]
        self.assertEqual(sorted(tipler(m.cari_esle(b, k))),
                         ["EKSIK_BIZDE", "EKSIK_KARSIDA"])

    def test_durum_onceligi_eksik_agir_basar(self):
        # Ayni caride hem tutar farki hem eksik belge -> durum EKSIK BELGE
        b = [kayit("FT-1", 1000.0), kayit("FT-2", 2000.0)]
        k = [kayit("FT-1", 900.0)]
        bulgular = m.cari_esle(b, k)
        self.assertEqual(sorted(tipler(bulgular)), ["EKSIK_KARSIDA", "TUTAR_FARKI"])
        self.assertEqual(m.cari_durum(bulgular), "EKSIK BELGE")


SUTUNLAR = ["cari_kodu", "cari_adi", "tarih", "belge_no", "belge_tipi",
            "aciklama", "tutar", "tip"]
GIB_SUTUNLAR = ["cari_kodu", "cari_adi", "tarih", "belge_no", "belge_tipi", "tutar"]


def _satir(cari, belge_no, tutar, tip="FATURA", belge_tipi="e-Fatura"):
    return {"cari_kodu": cari, "cari_adi": "Test Cari A.S.",
            "tarih": date(2026, 5, 10), "belge_no": belge_no,
            "belge_tipi": belge_tipi, "aciklama": "", "tutar": tutar, "tip": tip}


def _gib_satir(cari, belge_no, tutar):
    return {"cari_kodu": cari, "cari_adi": "Test Cari A.S.",
            "tarih": date(2026, 5, 10), "belge_no": belge_no,
            "belge_tipi": "e-Fatura", "tutar": tutar}


def _xlsx_yaz(yol, satirlar, sutunlar):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(sutunlar)
    for r in satirlar:
        ws.append([r.get(s) for s in sutunlar])
    wb.save(yol)


class TestGibKontrol(unittest.TestCase):
    """GIB hakemli 3 asama: dosya tabanli kontrol() ucundan ucuna.

    Kurgu (cari 120.90 sorunlu, 120.91 temiz):
      GIB     : EF-1 10000, EF-2 8000, EF-3 5000
      bizim   : EF-1 tam; EF-2 YOK (ASAMA0 BIZ); EF-3 4900 (ASAMA0 BIZ tutar);
                EF-9 GIB'de yok (UYARI); AR-1 e-Arsiv karsida yok (ASAMA2 KARSI);
                DK-5 dekont 700 (karsida 750 -> ASAMA2 BELIRSIZ)
      karsi   : EF-1 tam; EF-2 9000 (ASAMA1 KARSI tutar); EF-3 YOK (ASAMA1 KARSI);
                DK-5 dekont 750
    """
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        kok = cls.tmp.name
        gib_rows = [_gib_satir("120.90", "EF-1", 10000.0),
                    _gib_satir("120.90", "EF-2", 8000.0),
                    _gib_satir("120.90", "EF-3", 5000.0),
                    _gib_satir("120.91", "EF-7", 4000.0)]
        bizim = [_satir("120.90", "EF-1", 10000.0),
                 _satir("120.90", "EF-3", 4900.0),
                 _satir("120.90", "EF-9", 1000.0),
                 _satir("120.90", "AR-1", 2000.0, belge_tipi="e-Arsiv"),
                 _satir("120.90", "DK-5", 700.0, tip="ODEME", belge_tipi="Dekont"),
                 _satir("120.91", "EF-7", 4000.0)]
        karsi = [_satir("120.90", "EF-1", 10000.0),
                 _satir("120.90", "EF-2", 9000.0),
                 _satir("120.90", "DK-5", 750.0, tip="ODEME", belge_tipi="Dekont"),
                 _satir("120.91", "EF-7", 4000.0)]
        bz = os.path.join(kok, "bizim.xlsx")
        kr = os.path.join(kok, "karsi.xlsx")
        gb = os.path.join(kok, "gib.xlsx")
        _xlsx_yaz(bz, bizim, SUTUNLAR)
        _xlsx_yaz(kr, karsi, SUTUNLAR)
        _xlsx_yaz(gb, gib_rows, GIB_SUTUNLAR)
        cls.sonuc = gib.kontrol(bz, kr, gb)
        cls.bulgular = cls.sonuc["120.90"]["bulgular"]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _filtre(self, asama=None, sahip=None, kesinlik=None):
        out = []
        for a, s, kk, ac in self.bulgular:
            if asama and a != asama:
                continue
            if sahip and s != sahip:
                continue
            if kesinlik and kk != kesinlik:
                continue
            out.append((a, s, kk, ac))
        return out

    def test_asama0_gibde_var_bizde_yok(self):
        b = [x for x in self._filtre("ASAMA0", "BIZ", "GIB-KESIN") if "EF-2" in x[3]]
        self.assertEqual(len(b), 1)
        self.assertIn("BIZDE YOK", b[0][3])

    def test_asama0_bizim_tutar_gibden_farkli(self):
        b = [x for x in self._filtre("ASAMA0", "BIZ", "GIB-KESIN") if "EF-3" in x[3]]
        self.assertEqual(len(b), 1)
        self.assertIn("GIB'den farkli", b[0][3])

    def test_asama1_gibde_var_karsida_yok(self):
        b = [x for x in self._filtre("ASAMA1", "KARSI", "GIB-KESIN") if "EF-3" in x[3]]
        self.assertEqual(len(b), 1)
        self.assertIn("KARSIDA YOK", b[0][3])

    def test_asama1_karsi_tutar_gibden_farkli(self):
        b = [x for x in self._filtre("ASAMA1", "KARSI", "GIB-KESIN") if "EF-2" in x[3]]
        self.assertEqual(len(b), 1)

    def test_uyari_bizde_efatura_gibde_yok(self):
        b = [x for x in self._filtre("ASAMA0", "BIZ", "UYARI") if "EF-9" in x[3]]
        self.assertEqual(len(b), 1)

    def test_asama2_eksik_karsida_sahibi_karsi(self):
        b = [x for x in self._filtre("ASAMA2", "KARSI") if "AR-1" in x[3]]
        self.assertEqual(len(b), 1)

    def test_asama2_tutar_farki_sahibi_belirsiz(self):
        # TUTAR_FARKI mesaji belge no degil tutarlari icerir
        b = self._filtre("ASAMA2", "BELIRSIZ")
        self.assertEqual(len(b), 1)
        self.assertIn("750.00", b[0][3])

    def test_efatura_asama2ye_sizmaz(self):
        # e-Fatura satirlari GIB asamasinda cozulur; ASAMA2'de EF-* gorunmemeli
        for _, _, _, ac in self._filtre("ASAMA2"):
            self.assertNotIn("EF-", ac)

    def test_temiz_cari_bulgusuz(self):
        self.assertEqual(self.sonuc["120.91"]["bulgular"], [])


if __name__ == "__main__":
    unittest.main()
