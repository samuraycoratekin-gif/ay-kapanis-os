# -*- coding: utf-8 -*-
"""
GIB e-Fatura tabanli 3 asamali mutabakat kontrolu (prototip).

Oncelik: e-Fatura icin GIB OTORITEDIR. Once GIB ile kesin kontrol yapilir,
sonra ekstre karsilastirmasi yalnizca GIB'in kapsamadigi yerde devreye girer.

  ASAMA 0 - Gonderim oncesi SELF-KONTROL
      Bizim defter vs GIB e-Fatura.
      "GIB'de var, bizde yok" -> BIZ girmemisiz (formu gondermeden once tamamla).
      "Bizim tutar != GIB"    -> bizim kayit hatali.

  ASAMA 1 - Karsi taraf KONTROLU
      Karsi ekstre vs GIB e-Fatura.
      "GIB'de var, karsida yok" -> KARSI girmemis -> bildirim karsiya.
      "Karsi tutar != GIB"      -> karsi kaydi hatali -> bildirim karsiya.

  ASAMA 2 - e-Arsiv + ODEMELER (GIB kapsam disi)
      GIB'de olmayan her sey (e-Arsiv, Matbu, tum odemeler) -> ekstre
      karsilastirmasi (mevcut motor). Otorite yok; delil iki ekstredir.

Her bulgu HATA SAHIBI ile etiketlenir; bildirim kuyrugu otomatik olusur.
Bagimlilik: openpyxl + mutabakat_motoru (saf python).
"""
import os
from . import motor as m

KLASOR = "Mutabakat_AI"
TOL = m.TOL


def _efatura_listesi(rows):
    """Sadece e-Fatura tipi FATURA satirlari."""
    return [r for r in rows
            if str(r.get("belge_tipi")) == "e-Fatura" and r.get("tip", "FATURA") == "FATURA"]


def _esle_bul(g, havuz, kullanilan):
    """GIB satirini havuzdaki bir e-faturaya bagla: once tam norm, sonra sayi cekirdegi
    (FT-2026-00318 <-> 318 format farkini yutar). Eslesen satiri 'kullanilan' isaretler."""
    gno = m.norm_belge(g["belge_no"])
    gcore = m.sayi_cekirdek(g["belge_no"])
    for r in havuz:
        if id(r) in kullanilan:
            continue
        if m.norm_belge(r["belge_no"]) == gno:
            kullanilan.add(id(r))
            return r
    for r in havuz:
        if id(r) in kullanilan:
            continue
        if gcore is not None and m.sayi_cekirdek(r["belge_no"]) == gcore:
            kullanilan.add(id(r))
            return r
    return None


def kontrol(bz=None, kr=None, gb=None):
    bz = bz or os.path.join(KLASOR, "bizim_ekstreler.xlsx")
    kr = kr or os.path.join(KLASOR, "karsi_ekstreler.xlsx")
    gb = gb or os.path.join(KLASOR, "gib_efatura_kayitlari.xlsx")
    bizim = m.grupla(m.oku(bz))
    karsi = m.grupla(m.oku(kr))
    gib   = m.grupla(m.oku(gb))
    cariler = sorted(set(bizim) | set(karsi) | set(gib))

    sonuc = {}
    for ck in cariler:
        b_rows = bizim.get(ck, [])
        k_rows = karsi.get(ck, [])
        g_rows = gib.get(ck, [])
        adi = (b_rows or k_rows or g_rows)[0]["cari_adi"]

        b_ef = _efatura_listesi(b_rows)
        k_ef = _efatura_listesi(k_rows)

        bulgular = []   # (asama, hata_sahibi, kesinlik, aciklama)
        b_kull, k_kull = set(), set()

        # --- ASAMA 0 + 1: GIB hakemli e-Fatura kontrolu -------------------
        for g in g_rows:
            tut = float(g["tutar"])
            b = _esle_bul(g, b_ef, b_kull)
            k = _esle_bul(g, k_ef, k_kull)
            # bizim taraf
            if b is None:
                bulgular.append(("ASAMA0", "BIZ", "GIB-KESIN",
                    f"GIB'de var, BIZDE YOK: {g['belge_no']} = {tut:,.2f} TL "
                    f"-> biz defterimize almamisiz (gondermeden once tamamla)"))
            elif not m.yakin(b["tutar"], tut):
                bulgular.append(("ASAMA0", "BIZ", "GIB-KESIN",
                    f"Bizim tutar GIB'den farkli: {g['belge_no']} bizde "
                    f"{float(b['tutar']):,.2f} / GIB {tut:,.2f} -> bizim kayit hatali"))
            # karsi taraf
            if k is None:
                bulgular.append(("ASAMA1", "KARSI", "GIB-KESIN",
                    f"GIB'de var, KARSIDA YOK: {g['belge_no']} = {tut:,.2f} TL "
                    f"-> karsi taraf islememis (bildirim gonderilecek)"))
            elif not m.yakin(k["tutar"], tut):
                bulgular.append(("ASAMA1", "KARSI", "GIB-KESIN",
                    f"Karsi tutar GIB'den farkli: {g['belge_no']} karsida "
                    f"{float(k['tutar']):,.2f} / GIB {tut:,.2f} -> karsi kayit hatali"))

        # e-Fatura olarak kayitli ama hicbir GIB kaydiyla eslesmeyen (supheli)
        for b in b_ef:
            if id(b) not in b_kull:
                bulgular.append(("ASAMA0", "BIZ", "UYARI",
                    f"Bizde e-Fatura olarak kayitli ama GIB'de yok: {b['belge_no']} "
                    f"-> yanlis belge tipi ya da hayali kayit olabilir"))

        # --- ASAMA 2: e-Arsiv + Matbu + ODEMELER (ekstre karsilastirmasi) -
        # Tum e-Fatura FATURA satirlari GIB alanindadir; ekstre asamasina girmez.
        def disarda(rows):
            secili = []
            for r in rows:
                ef = (str(r.get("belge_tipi")) == "e-Fatura" and r.get("tip") == "FATURA")
                if ef:
                    continue  # e-faturalar GIB asamasinda cozuldu
                secili.append(dict(r))
            return secili

        ekstre_bulgu = m.cari_esle(disarda(b_rows), disarda(k_rows))
        for tip, bb, kk, ac in ekstre_bulgu:
            if tip in ("EXACT", "FUZZY", "SUBSET_SUM"):
                continue
            if tip == "EKSIK_KARSIDA":
                bulgular.append(("ASAMA2", "KARSI", "EKSTRE", ac))
            elif tip == "EKSIK_BIZDE":
                bulgular.append(("ASAMA2", "BIZ", "EKSTRE", ac))
            else:  # TUTAR_FARKI - otorite yok
                bulgular.append(("ASAMA2", "BELIRSIZ", "EKSTRE", ac))

        sonuc[ck] = {"adi": adi, "bulgular": bulgular}
    return sonuc


def rapor(sonuc):
    biz_gorev, karsi_bildirim = [], []
    print("=" * 74)
    print("  GIB TABANLI MUTABAKAT KONTROLU - HATA SAHIBI ETIKETLI")
    print("=" * 74)
    for ck, d in sonuc.items():
        b = d["bulgular"]
        if not b:
            print(f"\n  [TEMIZ] {ck} - {d['adi']}  (GIB + ekstre uyumlu)")
            continue
        print(f"\n  {ck} - {d['adi']}")
        for asama, sahip, kesinlik, ac in b:
            etiket = {"GIB-KESIN": "GIB-KESIN", "EKSTRE": "ekstre", "UYARI": "UYARI"}[kesinlik]
            print(f"     [{sahip:8}] ({etiket}) {ac}")
            if sahip == "BIZ":
                biz_gorev.append((ck, ac))
            elif sahip == "KARSI":
                karsi_bildirim.append((ck, ac))

    print("\n" + "=" * 74)
    print(f"  BIZE DUSEN GOREVLER (gondermeden once tamamla) : {len(biz_gorev)}")
    for ck, ac in biz_gorev:
        print(f"     - {ck}: {ac}")
    print(f"\n  KARSI TARAFA BILDIRIM (mail/WhatsApp)          : {len(karsi_bildirim)}")
    for ck, ac in karsi_bildirim:
        print(f"     - {ck}: {ac}")
    print("=" * 74)


if __name__ == "__main__":
    rapor(kontrol())
