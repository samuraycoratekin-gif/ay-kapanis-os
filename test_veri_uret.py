# -*- coding: utf-8 -*-
"""
Test verisi ureteci - Ay Kapanis OS'u MANUEL test etmek icin.

Her firma icin Mayis sonu (kumule Ocak-Mayis) gercekci dosyalar uretir:
  1_Mizan                -> M2 Mizan, M4 KDV, M9 Finansal, M7 Eksik
  2_Cari_Bizim / 3_Cari_Karsi  -> M3 Cari Mutabakat (120 alici + 320 satici)
  4_GIB_eFatura / 5_Defter_Alis -> M4 GIB karsilastirma, M7 eksik belge
  6_Banka_Ekstresi / 7_Banka_Defteri_102 -> M5 banka esleme, M6 komisyon fisi

Mizanlar DENK uretilir (borc=alacak): M9 finansal motoru donem sonucunu
gelir tablosu kariyla birebir esler, yapay "denklesmiyor" uyarisi cikmaz.

Calistirma:  python test_veri_uret.py
Cikti:       test_veri/<Firma>/...   + OKUBENI.txt
"""
import os
import calendar
from datetime import date
from openpyxl import Workbook

HERE = os.path.dirname(os.path.abspath(__file__))
COK = os.path.join(HERE, "test_veri")
AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs"]

FIRMALAR = [
    {"kod": "M001", "ad": "ÖRNEK SANAYİ A.Ş.", "kisa": "01_Ornek_Sanayi", "olcek": 1.0, "profil": "saglikli", "co": 0},
    {"kod": "M002", "ad": "DEMİR ÇELİK TİC. LTD.", "kisa": "02_Demir_Celik", "olcek": 2.2, "profil": "riskli", "co": 1},
    {"kod": "M003", "ad": "GÜL PLASTİK SAN. A.Ş.", "kisa": "03_Gul_Plastik", "olcek": 0.6, "profil": "eksik", "co": 2},
    {"kod": "M004", "ad": "CEYHAN LOJİSTİK A.Ş.", "kisa": "04_Ceyhan_Lojistik", "olcek": 0.9, "profil": "zarar", "co": 3},
]

ALICI_ADLARI = ["AKDENİZ GIDA A.Ş.", "BORA İNŞAAT LTD.", "CAN MARKET ZİNCİRİ A.Ş.",
                "DENİZ TEKSTİL LTD.", "EGE OTOMOTİV A.Ş."]
SATICI_ADLARI = ["FİLİZ AMBALAJ LTD.", "GÜNEŞ ENERJİ A.Ş.", "HAVUZ KİMYA LTD.",
                 "IŞIK NAKLİYE A.Ş.", "JET LOJİSTİK LTD."]

# Bordro icmal (M12) - tek ay (Mayis) puantaj ozeti. Her satir bir personel;
# net = brut - sgk_isci - issizlik_isci - gelir_vergisi - damga (ic tutarlilik OK).
# Saglikli firmada (M001) mizan 335/361 Mayis hareketi bu toplamlara hizalanir
# (asagida override) -> bordro<->mizan MUTABIK. Diger firmalar bilerek sapar.
BORDRO_PERSONEL = [
    # ad, brut, sgk_isci, issizlik_isci, gelir_vergisi, damga, sgk_isveren, issizlik_isveren, net
    ("Personel 01 - İdari Yönetici", 18_000, 2_520, 180, 1_900, 137, 3_735, 360, 13_263),
    ("Personel 02 - Muhasebe",       14_000, 1_960, 140, 1_400, 106, 2_905, 280, 10_394),
    ("Personel 03 - Üretim",         10_000, 1_400, 100,   950,  76, 2_075, 200,  7_474),
    ("Personel 04 - Destek",          8_000, 1_120,  80,   700,  61, 1_660, 160,  6_039),
]


def _yaz(yol, basliklar, satirlar, sayfa="Sayfa1"):
    wb = Workbook()
    ws = wb.active
    ws.title = sayfa
    ws.append(basliklar)
    for s in satirlar:
        ws.append(list(s))
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    wb.save(yol)


def _o(v, olcek):
    return round(v * olcek)


def _bordro_toplam():
    """BORDRO_PERSONEL'den base (olcek 1.0) toplamlari (net + sgk_toplam dahil)."""
    i = {"brut": 1, "sgk_isci": 2, "issizlik_isci": 3, "gelir_vergisi": 4,
         "damga": 5, "sgk_isveren": 6, "issizlik_isveren": 7, "net": 8}
    t = {k: sum(p[j] for p in BORDRO_PERSONEL) for k, j in i.items()}
    t["sgk_toplam"] = (t["sgk_isci"] + t["issizlik_isci"]
                       + t["sgk_isveren"] + t["issizlik_isveren"])
    return t


# --------------------------------------------------------------------------- #
# MIZAN
# --------------------------------------------------------------------------- #
def mizan_satirlari(firma):
    ol = firma["olcek"]
    prof = firma["profil"]
    sat = []  # (kod, ad, acilis, [m1..m5])

    def ekle(kod, ad, acilis, aylik):
        sat.append([kod, ad, _o(acilis, ol), [_o(x, ol) for x in aylik]])

    # ============================ AKTIF (borc +) ============================ #
    # --- 10 Hazir Degerler ---
    ekle("100", "KASA", 35_000, [3_000, 2_000, 4_000, 1_500, 2_500])
    ekle("108", "DİĞER HAZIR DEĞERLER", 5_000, [500, -300, 800, 0, 400])
    # 102 BANKALAR -> yaz_mizan() icinde DENGE PLUG olarak eklenir

    # --- 12 Ticari Alacaklar (120 ALICILAR detayli) ---
    for i, ad in enumerate(ALICI_ADLARI, 1):
        acilis = 90_000 + i * 12_000
        ay = [60_000 - i * 4_000, 55_000, 48_000, 52_000, 50_000]
        ay = [ay[0], ay[1] - 30_000, ay[2], ay[3] - 25_000, ay[4] - 20_000]
        ekle(f"120.0{i}", f"ALICI - {ad}", acilis, ay)
    ekle("121", "ALACAK SENETLERİ", 80_000, [10_000, -15_000, 5_000, 0, 8_000])
    ekle("126", "VERİLEN DEPOZİTO VE TEMİNATLAR", 22_000, [0, 0, 0, 3_000, 0])
    ekle("128", "ŞÜPHELİ TİCARİ ALACAKLAR", 30_000, [0, 0, 15_000, 0, 0])

    # --- 13 Diger Alacaklar (131 ESNEK -> ters bakiye taramasinda haric) ---
    ekle("131", "ORTAKLARDAN ALACAKLAR", 50_000, [10_000, 0, -5_000, 0, 8_000])

    # --- 15 Stoklar ---
    ekle("153", "TİCARİ MALLAR", 760_000, [40_000, -10_000, 30_000, -5_000, 20_000])
    ekle("157", "DİĞER STOKLAR", 40_000, [3_000, -2_000, 4_000, 0, 1_000])
    ekle("159", "VERİLEN SİPARİŞ AVANSLARI", 25_000, [0, 10_000, 0, -5_000, 0])

    # --- 18 Gelecek Aylara Ait Giderler (pesin gider, aylik itfa) ---
    ekle("180", "GELECEK AYLARA AİT GİDERLER", 60_000, [-5_000, -5_000, -5_000, -5_000, -5_000])

    # --- 19 Diger Donen / KDV (191 dönem sonu kapanmali -> gecici hesap bulgusu) ---
    ekle("190", "DEVREDEN KDV", 0, [0, 0, 0, 0, 0])   # ODENECEK firmalarda 0; zarar profilinde devir
    ekle("191", "İNDİRİLECEK KDV", 0, [92_000, 88_000, 95_000, 90_000, 96_000])
    ekle("193", "PEŞİN ÖDENEN VERGİLER VE FONLAR", 18_000, [2_000, 2_000, 2_000, 2_000, 2_000])

    # ===================== DURAN VARLIKLAR (borc +) ===================== #
    ekle("252", "BİNALAR", 900_000, [0, 0, 0, 0, 0])
    ekle("253", "TESİS MAKİNE VE CİHAZLAR", 650_000, [0, 0, 0, 0, 0])
    ekle("254", "TAŞITLAR", 320_000, [0, 0, 180_000, 0, 0])           # Mart araç alimi -> ani giris
    ekle("255", "DEMİRBAŞLAR", 280_000, [0, 0, 0, 12_000, 0])
    ekle("256", "DİĞER MADDİ DURAN VARLIKLAR", 60_000, [0, 0, 0, 0, 0])
    ekle("257", "BİRİKMİŞ AMORTİSMANLAR (-)", -240_000, [-8_000, -8_000, -8_000, -8_000, -8_000])
    ekle("260", "HAKLAR", 50_000, [0, 0, 0, 0, 0])
    ekle("268", "BİRİKMİŞ AMORTİSMANLAR (-)", -20_000, [-1_000, -1_000, -1_000, -1_000, -1_000])
    ekle("280", "GELECEK YILLARA AİT GİDERLER", 90_000, [-3_000, -3_000, -3_000, -3_000, -3_000])

    # ===================== PASİF — KV Yabanci Kaynak (alacak -) ===================== #
    ekle("300", "BANKA KREDİLERİ", -550_000, [-20_000, -20_000, -20_000, -20_000, -20_000])
    ekle("303", "UZUN VAD. KREDİ ANAPARA TAKSİT VE FAİZ", -120_000, [0, 0, 0, 0, 0])
    for i, ad in enumerate(SATICI_ADLARI, 1):
        acilis = -(70_000 + i * 9_000)
        ay = [-50_000, -42_000, -48_000, -45_000, -47_000]
        ay = [ay[0] + 35_000, ay[1], ay[2] + 30_000, ay[3], ay[4] + 28_000]  # odemeler
        ekle(f"320.0{i}", f"SATICI - {ad}", acilis, ay)
    ekle("321", "BORÇ SENETLERİ", -90_000, [-10_000, 5_000, -8_000, 0, -6_000])
    ekle("326", "ALINAN DEPOZİTO VE TEMİNATLAR", -15_000, [0, 0, 0, 0, 0])
    ekle("335", "PERSONELE BORÇLAR", -38_000, [-2_000, 3_000, -1_000, 2_000, -1_500])
    ekle("340", "ALINAN SİPARİŞ AVANSLARI", -30_000, [-10_000, 0, 5_000, 0, 0])
    ekle("360", "ÖDENECEK VERGİ VE FONLAR", -28_000, [-9_000, -8_500, -9_500, -8_000, -9_000])
    ekle("361", "ÖDENECEK SOSYAL GÜVENLİK KESİNTİLERİ", -24_000,
         [-12_000, -12_500, -11_800, -12_200, -12_000])
    ekle("368", "VADESİ GEÇMİŞ/ERTELENMİŞ VERGİ VE FONLAR", -12_000, [0, 0, 0, 0, 0])
    ekle("370", "DÖNEM KÂRI VERGİ VE DİĞER YÜK. KARŞILIKLARI", 0, [0, 0, 0, 0, 0])
    ekle("380", "GELECEK AYLARA AİT GELİRLER", -20_000, [-4_000, -4_000, -4_000, -4_000, -4_000])
    ekle("391", "HESAPLANAN KDV", 0, [-112_000, -108_000, -116_000, -110_000, -118_000])

    # ===================== UV Yabanci Kaynak (alacak -) ===================== #
    ekle("400", "BANKA KREDİLERİ", -500_000, [0, 0, 0, 0, 0])
    ekle("420", "SATICILAR", -100_000, [0, 0, 0, 0, 0])

    # ===================== ÖZKAYNAKLAR (alacak -) ===================== #
    ekle("500", "SERMAYE", -1_000_000, [0, 0, 0, 0, 0])
    ekle("570", "GEÇMİŞ YILLAR KÂRLARI", -300_000, [0, 0, 0, 0, 0])
    ekle("580", "GEÇMİŞ YILLAR ZARARLARI (-)", 0, [0, 0, 0, 0, 0])

    # ===================== GELİR / GİDER (7/A) ===================== #
    satis_ay = [-560_000, -540_000, -580_000, -555_000, -575_000]
    ekle("600", "YURTİÇİ SATIŞLAR", 0, satis_ay)
    ekle("601", "YURTDIŞI SATIŞLAR", 0, [-40_000, -38_000, -42_000, -40_000, -41_000])
    ekle("610", "SATIŞTAN İADELER (-)", 0, [5_000, 4_000, 6_000, 5_000, 5_000])
    ekle("620", "SATILAN TİCARİ MALLAR MALİYETİ", 0, [410_000, 395_000, 425_000, 405_000, 420_000])
    ekle("642", "FAİZ GELİRLERİ", 0, [-3_000, -3_000, -3_500, -3_000, -3_200])
    ekle("656", "KAMBİYO ZARARLARI", 0, [4_000, 3_000, 5_000, 4_000, 4_000])
    ekle("660", "KISA VAD. BORÇLANMA (FİNANSMAN) GİDERLERİ", 0, [15_000, 15_000, 16_000, 15_500, 16_000])
    ekle("689", "DİĞER OLAĞANDIŞI GİDER VE ZARARLAR", 0, [0, 0, 0, 0, 0])
    ekle("760", "PAZARLAMA SATIŞ VE DAĞITIM GİDERLERİ", 0, [25_000, 24_000, 26_000, 25_000, 25_000])
    ekle("770", "GENEL YÖNETİM GİDERLERİ", 0, [62_000, 60_000, 64_000, 61_000, 63_000])

    def bul(kod):
        for r in sat:
            if r[0] == kod:
                return r
        return None

    # NOT: Ters bakiye taramasi 3 haneli ANA HESAP duzeyinde calisir; tek bir alt
    # hesabi (or. 320.04) ters yapmak grup toplaminda netlesip GORUNMEZ. Bu yuzden
    # ters bakiyeler BUTUN hesap (100/159/340/360 gibi) uzerinde verilir.

    # ===================== PROFİL FARKLILAŞTIRMA ===================== #
    if prof == "saglikli":
        # Saglikli baseline: dusuk borc, guclu likidite -> belirgin risk yok
        bul("300")[2] = -150_000; bul("300")[3] = [-8_000] * 5
        bul("400")[2] = -250_000
        bul("153")[2] = 1_050_000                     # guclu stok
        bul("121")[2] = 180_000                       # alacak senetleri
        bul("100")[3] = [8_000, 7_000, 9_000, 6_000, 8_000]   # nakit girisi
        # BORDRO (M12) MUTABAKATI: Mayis net ucret -> 335, SGK -> 361 tahakkuku
        # bordro icmaliyle birebir (ol=1.0). 360 (vergi) Mayis -9.000 zaten
        # bordro vergisini (5.330) kapsar; 770/760 gideri personel giderini karsilar.
        tb = _bordro_toplam()
        bul("335")[3][4] = -tb["net"]            # Mayis net ucret tahakkuku (alacak)
        bul("361")[3][4] = -tb["sgk_toplam"]     # Mayis SGK tahakkuku (alacak)

    if prof == "riskli":
        # Yuksek kredi -> dusuk cari oran / yuksek kaldirac / sermaye asinmasi
        bul("300")[2] = _o(-1_400_000, ol); bul("300")[3] = [_o(-45_000, ol)] * 5
        bul("400")[2] = _o(-1_300_000, ol)
        # TERS BAKİYE 1: KASA negatif (alacak) -> imkansiz, veri/sayim hatasi
        bul("100")[2] = _o(-8_000, ol); bul("100")[3] = [_o(-2_000, ol)] * 5
        # TERS BAKİYE 2: 159 Verilen Siparis Avansi ALACAK bakiye (aktif hesap ters)
        bul("159")[2] = _o(-35_000, ol); bul("159")[3] = [_o(-5_000, ol), 0, 0, 0, 0]
        # ANORMAL SAPMA: Mayis'ta ani buyuk olagandisi gider
        bul("689")[3] = [0, 0, 0, 0, _o(220_000, ol)]

    if prof == "zarar":
        bul("600")[3] = [_o(-340_000, ol)] * 5      # dusuk satis
        bul("770")[3] = [_o(140_000, ol)] * 5       # yuksek gider
        bul("760")[3] = [_o(55_000, ol)] * 5
        bul("570")[2] = _o(-120_000, ol)            # birikmis kar az
        # Zarari finanse etmek icin agir borclanma (gercekci) + yuksek kaldirac bulgusu
        bul("300")[2] = _o(-1_500_000, ol); bul("300")[3] = [_o(-30_000, ol)] * 5
        # TERS BAKİYE: 340 Alinan Siparis Avansi BORC bakiye (pasif hesap ters)
        bul("340")[2] = _o(35_000, ol); bul("340")[3] = [_o(5_000, ol), 0, 0, 0, 0]
        # DEVREDEN KDV (190): gecen donemden tasinan devir + dusuk satislı dönem ->
        # indirilecek > hesaplanan, devir buyuyor. Mahsup fisi kesilmedigi icin 190
        # hala acilis devrini tasir (m4 "mahsup bekliyor" teyidi tetiklenir).
        bul("190")[2] = _o(80_000, ol)              # onceki donemden devreden KDV
        bul("391")[3][4] = _o(-70_000, ol)          # Mayis dusuk satis -> dusuk hesaplanan KDV

    if prof == "eksik":
        # M7 EKSİK BELGE / TAHAKKUK: duzenli kalemler MAYIS'ta gelmemis (fis girilmemis)
        bul("770")[3][4] = 0          # genel yonetim gideri Mayis yok (kira/elektrik tahakkuku?)
        bul("760")[3][4] = 0          # pazarlama gideri Mayis yok
        bul("660")[3][4] = 0          # kredi faiz tahakkuku unutulmus
        bul("361")[3][4] = _o(-300, ol)   # SGK tahakkuku Mayis neredeyse yok
        bul("360")[3][4] = _o(-200, ol)   # vergi tahakkuku Mayis neredeyse yok
        # TERS BAKİYE: 360 Odenecek Vergi BORC bakiye (fazla odeme/mahsup -> pasif ters)
        bul("360")[2] = _o(55_000, ol)
        bul("360")[3] = [_o(8_000, ol), _o(6_000, ol), 0, 0, _o(-200, ol)]

    return sat


def yaz_mizan(firma, klasor):
    ol = firma["olcek"]
    sat = mizan_satirlari(firma)
    # 102 BANKALAR: sabit, gercekci POZITIF bakiye (plug DEGIL)
    banka_aylik = [_o(x, ol) for x in (15_000, -8_000, 12_000, -5_000, 9_000)]
    sat.insert(1, ["102", "BANKALAR", _o(180_000, ol), banka_aylik])

    basliklar = ["Hesap Kodu", "Hesap Adı", "Açılış"] + AYLAR + ["Toplam"]
    rows = []
    denge = 0
    for kod, ad, acilis, aylik in sat:
        toplam = acilis + sum(aylik)
        denge += toplam
        rows.append([kod, ad, acilis] + aylik + [toplam])
    # DENGE PLUG -> ozkaynaga (likidite oranlarini bozmaz, ters bakiye uretmez):
    #   fazla borc (debit)  -> 580 Gecmis Yil Zararlari (-)  (kontra-borc, normal)
    #   fazla alacak(credit)-> 570 Gecmis Yil Karlari        (ozkaynak, normal)
    plug = -denge
    if plug >= 0:
        rows.append(["580", "GEÇMİŞ YILLAR ZARARLARI (-)", plug, 0, 0, 0, 0, 0, plug])
    else:
        rows.append(["570", "GEÇMİŞ YILLAR KÂRLARI", plug, 0, 0, 0, 0, 0, plug])
    yol = os.path.join(klasor, f"1_Mizan_2026-05.xlsx")
    _yaz(yol, basliklar, rows, "Mizan")


# --------------------------------------------------------------------------- #
# CARİ EKSTRELER (bizim defter + karsi taraf)
# --------------------------------------------------------------------------- #
CARI_BAS = ["Cari Kodu", "Cari Adı", "Tarih", "Belge No", "Belge Tipi", "Tutar", "Tip"]


def cari_hareketleri(firma):
    """Secili cariler icin bizim + karsi hareketleri (bazi farklarla)."""
    ol = firma["olcek"]
    bizim, karsi = [], []

    def hr(liste, kod, ad, gun, belge, btip, tutar, tip):
        liste.append([kod, ad, f"2026-05-{gun:02d}", belge, btip, _o(tutar, ol), tip])

    # 120.01 - TAM MUTABIK (alici)
    k, a = "120.01", f"ALICI - {ALICI_ADLARI[0]}"
    for liste in (bizim, karsi):
        hr(liste, k, a, 3, "STF2026-101", "Satış Faturası", 120_000, "Fatura")
        hr(liste, k, a, 12, "STF2026-118", "Satış Faturası", 95_000, "Fatura")
        hr(liste, k, a, 20, "THS-44", "Tahsilat", -150_000, "Tahsilat")

    # 120.02 - FARKLI: karsi tarafta bir fatura EKSIK
    k, a = "120.02", f"ALICI - {ALICI_ADLARI[1]}"
    hr(bizim, k, a, 5, "STF2026-105", "Satış Faturası", 88_000, "Fatura")
    hr(bizim, k, a, 15, "STF2026-130", "Satış Faturası", 64_000, "Fatura")   # karsida yok
    hr(bizim, k, a, 22, "THS-51", "Tahsilat", -90_000, "Tahsilat")
    hr(karsi, k, a, 5, "STF2026-105", "Satış Faturası", 88_000, "Fatura")
    hr(karsi, k, a, 22, "THS-51", "Tahsilat", -90_000, "Tahsilat")

    # 320.01 - FARKLI: tutar farki (satici)
    k, a = "320.01", f"SATICI - {SATICI_ADLARI[0]}"
    hr(bizim, k, a, 4, "AF2026-77", "Alış Faturası", 72_000, "Fatura")
    hr(bizim, k, a, 18, "AF2026-92", "Alış Faturası", 53_000, "Fatura")
    hr(bizim, k, a, 25, "ODM-23", "Ödeme", -100_000, "Ödeme")
    hr(karsi, k, a, 4, "AF2026-77", "Alış Faturası", 72_000, "Fatura")
    hr(karsi, k, a, 18, "AF2026-92", "Alış Faturası", 58_000, "Fatura")   # 5.000 fark
    hr(karsi, k, a, 25, "ODM-23", "Ödeme", -100_000, "Ödeme")

    # 320.02 - TAM MUTABIK (satici)
    k, a = "320.02", f"SATICI - {SATICI_ADLARI[1]}"
    for liste in (bizim, karsi):
        hr(liste, k, a, 7, "AF2026-80", "Alış Faturası", 64_000, "Fatura")
        hr(liste, k, a, 21, "ODM-30", "Ödeme", -64_000, "Ödeme")

    return bizim, karsi


def yaz_cari(firma, klasor):
    bizim, karsi = cari_hareketleri(firma)
    _yaz(os.path.join(klasor, "2_Cari_Bizim_Defter.xlsx"), CARI_BAS, bizim, "Cari")
    _yaz(os.path.join(klasor, "3_Cari_Karsi_Ekstre.xlsx"), CARI_BAS, karsi, "Cari")


# --------------------------------------------------------------------------- #
# GİB e-Fatura vs Defter Alis
# --------------------------------------------------------------------------- #
def yaz_gib(firma, klasor):
    ol = firma["olcek"]
    gib, defter = [], []

    def hr(liste, sat, ad, gun, belge, tutar, belge_tipi="e-Fatura"):
        liste.append([sat, ad, f"2026-05-{gun:02d}", belge, belge_tipi, _o(tutar, ol), "Fatura"])

    alislar = [
        ("320.01", SATICI_ADLARI[0], 4, "GIB2026-0077", 72_000),
        ("320.02", SATICI_ADLARI[1], 7, "GIB2026-0080", 64_000),
        ("320.03", SATICI_ADLARI[2], 9, "GIB2026-0085", 38_000),
        ("320.04", SATICI_ADLARI[3], 14, "GIB2026-0091", 51_000),
        ("320.05", SATICI_ADLARI[4], 19, "GIB2026-0099", 47_000),
        ("320.02", SATICI_ADLARI[1], 27, "GIB2026-0110", 29_000),
        ("320.01", SATICI_ADLARI[0], 29, "GIB2026-0118", 19_500),
    ]
    for kod, ad, gun, belge, tutar in alislar:
        hr(gib, kod, f"SATICI - {ad}", gun, belge, tutar)
    # defter: uc fatura ISLENMEMIS (GIB'de var, defterde yok = girilmemis fis)
    girilmemis = ("GIB2026-0085", "GIB2026-0110", "GIB2026-0118")
    for kod, ad, gun, belge, tutar in alislar:
        if belge in girilmemis:
            continue
        hr(defter, kod, f"SATICI - {ad}", gun, belge, tutar)
    # Defterde olup GIB e-Fatura listesinde OLMAYAN kayitlar:
    #  - e-Arsiv ve kagit: BEKLENEN (anomali degil) -> e-Arsiv ayrimi gosterir
    #  - normal e-Fatura ama GIB'de yok: GERCEK iptal/hayali suphesi
    hr(defter, "320.06", "SATICI - PERAKENDE TEDARIK", 22, "EAR2026-0007", 8_500, "e-Arşiv")
    hr(defter, "320.07", "SATICI - KIRTASIYE", 24, "KAG2026-0003", 3_200, "Kağıt Fatura")
    hr(defter, "320.08", "SATICI - SUPHELI", 26, "DFT2026-9001", 12_000, "e-Fatura")

    _yaz(os.path.join(klasor, "4_GIB_eFatura_Listesi.xlsx"), CARI_BAS, gib, "GIB")
    _yaz(os.path.join(klasor, "5_Defter_Alis_Faturalari.xlsx"), CARI_BAS, defter, "Defter")


# --------------------------------------------------------------------------- #
# BANKA EKSTRE vs ERP 102 DEFTERİ
# --------------------------------------------------------------------------- #
BANKA_BAS = ["Tarih", "Açıklama", "Borç", "Alacak"]


def yaz_banka(firma, klasor):
    ol = firma["olcek"]
    banka, defter = [], []

    def b(liste, gun, ack, borc, alacak):
        liste.append([f"2026-05-{gun:02d}", ack, _o(borc, ol) if borc else "", _o(alacak, ol) if alacak else ""])

    # Eslesen transferler (her ikisinde de) -- banka: alacak=giren, borc=cikan
    #                                          defter102: borc=giren, alacak=cikan
    eslesen = [
        (3, "MÜŞTERİ TAHSİLATI - CAN MARKET", 0, 150_000),
        (10, "TEDARİKÇİ ÖDEMESİ - FİLİZ AMBALAJ", 100_000, 0),
        (16, "MÜŞTERİ TAHSİLATI - AKDENİZ GIDA", 0, 90_000),
        (21, "TEDARİKÇİ ÖDEMESİ - GÜNEŞ ENERJİ", 64_000, 0),
        (24, "SGK ÖDEMESİ", 36_000, 0),
        (28, "KREDİ TAKSİT ÖDEMESİ", 20_000, 0),
    ]
    for gun, ack, borc, alacak in eslesen:
        b(banka, gun, ack, borc, alacak)
        # defter: ters yon (giren<->borc)
        b(defter, gun, ack, alacak, borc)

    # TOPLU TAHSILAT (1:N altkume eslesme): bankada tek 120.000'lik giris,
    # defterde iki ayri fatura tahsilati (70.000 + 50.000) olarak islenmis.
    # 1:1 eslesmez ama subset-sum ile eslesir -> "eksik kayit" alarmi VERILMEZ.
    b(banka, 14, "TOPLU MÜŞTERİ TAHSİLATI (2 fatura)", 0, 120_000)
    b(defter, 13, "TAHSİLAT - DENİZ TEKSTİL STF-130", 70_000, 0)
    b(defter, 15, "TAHSİLAT - EGE OTOMOTİV STF-141", 50_000, 0)

    # Sadece BANKADA olan komisyon/masraf (defterde yok) -> M5 komisyon, M6 fis
    b(banka, 5, "HAVALE KOMİSYONU", 250, 0)
    b(banka, 12, "EFT MASRAFI", 180, 0)
    b(banka, 18, "HESAP İŞLETİM ÜCRETİ + BSMV", 320, 0)
    b(banka, 30, "KREDİ KARTI POS KOMİSYONU", 1_450, 0)

    # Sadece DEFTERDE olan bir kayit (bankada yok) -> defter_fazla
    b(defter, 26, "KASA DEVİR (banka dekontu bekleniyor)", 12_000, 0)

    _yaz(os.path.join(klasor, "6_Banka_Ekstresi.xlsx"), BANKA_BAS, banka, "Banka")
    _yaz(os.path.join(klasor, "7_Banka_Defteri_102.xlsx"), BANKA_BAS, defter, "Defter102")


# --------------------------------------------------------------------------- #
# FAZ B: Demirbas (amortisman), Dovizli (kur farki), Senet (reeskont)
# --------------------------------------------------------------------------- #
def yaz_demirbas(firma, klasor):
    ol = firma["olcek"]
    bas = ["Demirbaş Adı", "Maliyet", "Oran (%)", "Birikmiş", "Gider Hesap", "Birikmiş Hesap"]
    kalemler = [
        ("Üretim Makinesi", 650_000, 20, 240_000, "770", "257"),
        ("Binek Araç", 320_000, 20, 64_000, "770", "257"),
        ("Ofis Mobilyası", 80_000, 20, 28_000, "770", "257"),
        ("Bilgisayar/Donanım", 120_000, 25, 60_000, "770", "257"),
        ("Yazılım Lisansı (Haklar)", 50_000, 20, 20_000, "770", "268"),
    ]
    rows = [[ad, _o(m, ol), o, _o(b, ol), g, bh] for ad, m, o, b, g, bh in kalemler]
    _yaz(os.path.join(klasor, "8_Demirbas_Listesi.xlsx"), bas, rows, "Demirbas")


def yaz_dovizli(firma, klasor):
    ol = firma["olcek"]
    bas = ["Hesap", "Açıklama", "Döviz", "Döviz Tutar", "Defter Kur", "Güncel Kur"]
    kalemler = [
        ("120.06", "İHRACAT ALICISI - EURO", "EUR", 50_000, 35.20, 36.40),
        ("320.06", "İTHALAT SATICISI - USD", "USD", 40_000, 32.10, 33.05),
        ("102.90", "DÖVİZ TEVDİAT - USD", "USD", 25_000, 32.40, 33.05),
        ("320.07", "İTHALAT SATICISI - EURO", "EUR", 18_000, 36.10, 36.40),
    ]
    rows = [[h, a, d, _o(t, ol), dk, gk] for h, a, d, t, dk, gk in kalemler]
    _yaz(os.path.join(klasor, "9_Dovizli_Bakiyeler.xlsx"), bas, rows, "Dovizli")


def yaz_senet(firma, klasor):
    ol = firma["olcek"]
    bas = ["Tip", "Açıklama", "Tutar", "Vade", "Faiz (%)"]
    kalemler = [
        ("Alacak", "Müşteri çeki - CAN MARKET", 180_000, "2026-08-15", ""),
        ("Alacak", "Alacak senedi - AKDENİZ GIDA", 95_000, "2026-07-30", ""),
        ("Borç", "Satıcı çeki - FİLİZ AMBALAJ", 120_000, "2026-09-10", ""),
        ("Borç", "Borç senedi - GÜNEŞ ENERJİ", 60_000, "2026-07-20", ""),
    ]
    rows = [[t, a, _o(tu, ol), v, f] for t, a, tu, v, f in kalemler]
    _yaz(os.path.join(klasor, "10_Senet_Cek_Listesi.xlsx"), bas, rows, "Senet")


def yaz_tevkifat(firma, klasor):
    ol = firma["olcek"]
    bas = ["İşlem Türü", "Matrah", "KDV Oranı (%)", "Tevkifat Oranı"]
    kalemler = [
        ("Temizlik hizmeti", 40_000, 20, "9/10"),
        ("İşgücü temin hizmeti", 60_000, 20, ""),       # bos -> varsayilan 9/10
        ("Servis taşımacılığı", 25_000, 20, "5/10"),
        ("Makine bakım onarım", 30_000, 20, ""),        # bos -> varsayilan 7/10
        ("Mali müşavirlik danışmanlık", 18_000, 20, "9/10"),
    ]
    rows = [[i, _o(mt, ol), ko, to] for i, mt, ko, to in kalemler]
    _yaz(os.path.join(klasor, "11_Tevkifat_Listesi.xlsx"), bas, rows, "Tevkifat")


def yaz_kdv_matrah(firma, klasor):
    """KDV matrah dokumu: satis/alis kalemleri matrah+oran (+yazilan KDV).
    Bilerek birkac anomali: oran disi (%18 eski), satir KDV hatasi, oran bos."""
    ol = firma["olcek"]
    bas = ["Tür", "Belge No", "Açıklama", "Matrah", "KDV Oranı (%)", "KDV Tutarı"]
    # (tur, belge, aciklama, matrah, oran, kdv) — kdv None ise matrah*oran kabul edilir
    kalemler = [
        ("Satış", "SF-1001", "Ürün satışı %20", 100_000, 20, 20_000),
        ("Satış", "SF-1002", "Ürün satışı %10", 50_000, 10, 5_000),
        ("Satış", "SF-1003", "Hatalı KDV (matrah×oran tutmuyor)", 40_000, 20, 5_500),  # olmasi gereken 8.000
        ("Satış", "SF-1004", "Eski/oran dışı %18", 30_000, 18, 5_400),                  # oran dogrula uyarisi
        ("Alış",  "AF-2001", "Mal alışı %20", 80_000, 20, 16_000),
        ("Alış",  "AF-2002", "Hizmet alışı %10", 25_000, 10, 2_500),
        ("Alış",  "AF-2003", "Oran boş kalem", 15_000, None, None),                     # oran bos uyarisi
    ]
    rows = [[t, b, a, _o(m, ol), (o if o is not None else ""),
             (_o(k, ol) if k is not None else "")] for t, b, a, m, o, k in kalemler]
    _yaz(os.path.join(klasor, "12_KDV_Matrah_Dokumu.xlsx"), bas, rows, "KDV Matrah")


def yaz_bordro(firma, klasor):
    """Bordro icmal (M12): personel bazli brut/kesinti/net, olcek ile olceklenir.
    Okuyucu 'TOPLAM' iceren satiri atladigi icin genel toplam satiri guvenli."""
    ol = firma["olcek"]
    bas = ["Personel", "Brüt Ücret", "SGK İşçi", "İşsizlik İşçi", "Gelir Vergisi",
           "Damga Vergisi", "SGK İşveren", "İşsizlik İşveren", "Net Ücret"]
    rows = []
    for ad, brut, si, ii, gv, dm, sv, iv, net in BORDRO_PERSONEL:
        rows.append([ad, _o(brut, ol), _o(si, ol), _o(ii, ol), _o(gv, ol),
                     _o(dm, ol), _o(sv, ol), _o(iv, ol), _o(net, ol)])
    toplam = ["GENEL TOPLAM"] + [sum(r[i] for r in rows) for i in range(1, 9)]
    rows.append(toplam)
    _yaz(os.path.join(klasor, "13_Bordro_Icmal.xlsx"), bas, rows, "Bordro")


# --------------------------------------------------------------------------- #
# KREDI ODEME PLANI (M5 Banka -> "Krediler" bolumu)
# Bir uzun vadeli TL kredi (400/303 reclass + donem faizi), bir kisa vadeli TL
# kredi (300) ve bir dovizli (USD) kredi (656/646 kur farki) iceren amortisman tablosu.
# --------------------------------------------------------------------------- #
def _ay_ekle(d, k):
    m = d.month - 1 + k
    y = d.year + m // 12
    m = m % 12 + 1
    gun = min(d.day, calendar.monthrange(y, m)[1])
    return date(y, m, gun)


def yaz_kredi(firma, klasor):
    ol = firma["olcek"]
    bas = ["Kredi", "Taksit No", "Vade", "Taksit Tutarı", "Anapara", "Faiz",
           "Kalan Anapara", "Döviz", "Defter Kur", "Güncel Kur"]
    rows = []

    def amort(ad, anapara_top, yillik, n, baslangic, doviz="TL", dk="", gk=""):
        r = yillik / 12 / 100.0
        bakiye = anapara_top
        taksit = anapara_top * r / (1 - (1 + r) ** (-n))
        for i in range(1, n + 1):
            faiz = bakiye * r
            ana = taksit - faiz
            bakiye -= ana
            vade = _ay_ekle(baslangic, i - 1)
            rows.append([ad, i, vade.isoformat(), round(taksit, 2), round(ana, 2),
                         round(faiz, 2), round(max(bakiye, 0), 2), doviz, dk, gk])

    # Uzun vadeli TL (24 ay) -> 400/303 reclass + dönem faizi
    amort("İş Bankası Yatırım Kredisi", _o(600_000, ol), 48, 24, date(2026, 1, 5))
    # Kısa vadeli TL (10 ay) -> 300
    amort("Ziraat İşletme Kredisi", _o(180_000, ol), 36, 10, date(2026, 2, 10))
    # Dövizli (USD, 18 ay) -> 656/646 kur farkı (anapara USD cinsinden)
    if firma["profil"] == "eksik":
        amort("Garanti USD Kredisi", 40_000, 9, 18, date(2026, 3, 15), doviz="USD")  # kur bos -> uyari
    else:
        amort("Garanti USD Kredisi", 40_000, 9, 18, date(2026, 3, 15),
              doviz="USD", dk=32.50, gk=34.20)

    _yaz(os.path.join(klasor, "14_Kredi_Odeme_Plani.xlsx"), bas, rows, "Kredi Plani")


# --------------------------------------------------------------------------- #
# SGK ISTIRAHAT / RAPOR LISTESI (M12 Bordro -> "SGK Rapor Kontrolu" bolumu)
# Bordrodaki personel adlariyla eslesen 2 istirahat + bordroda OLMAYAN 1 is kazasi.
# --------------------------------------------------------------------------- #
def yaz_sgk(firma, klasor):
    bas = ["Personel", "Rapor Türü", "Rapor Başlangıç", "Rapor Bitiş", "Rapor Gün Sayısı"]
    rows = [
        ["Personel 03 - Üretim", "İstirahat", "2026-05-04", "2026-05-08", 5],
        ["Personel 04 - Destek", "İstirahat", "2026-05-20", "2026-05-22", 3],
        # Bordro icmalinde OLMAYAN personel -> "bordroda yok" uyarisi; is kazasi -> ilk gunden SGK
        ["Personel 09 - Sevkiyat", "İş kazası", "2026-05-12", "2026-05-19", 8],
    ]
    _yaz(os.path.join(klasor, "15_SGK_Rapor_Listesi.xlsx"), bas, rows, "SGK Rapor")


# --------------------------------------------------------------------------- #
OKUBENI = """AY KAPANIS OS - TEST VERISI (Mayis 2026 / donem 2026-05)
============================================================

Her firma klasorunde 13 dosya var. Kokpitte ilgili sekmeye yukleyin:

  1_Mizan_2026-05.xlsx          -> "Mizan & Anomali" sekmesi (Yukle)
                                   (Ayni mizan KDV, Finansal Analiz ve
                                    Eksik Belge modullerini de otomatik besler)

  2_Cari_Bizim_Defter.xlsx      -> "Cari Mutabakat" sekmesi, BIZIM slotu
  3_Cari_Karsi_Ekstre.xlsx      -> "Cari Mutabakat" sekmesi, KARSI slotu

  4_GIB_eFatura_Listesi.xlsx    -> "e-Fatura & KDV" sekmesi, GIB slotu
  5_Defter_Alis_Faturalari.xlsx -> "e-Fatura & KDV" sekmesi, DEFTER slotu

  6_Banka_Ekstresi.xlsx         -> "Banka Ekstre Esleme" sekmesi, BANKA slotu
  7_Banka_Defteri_102.xlsx      -> "Banka Ekstre Esleme" sekmesi, DEFTER slotu

  8_Demirbas_Listesi.xlsx       -> "Fis Uretici" sekmesi, AMORTISMAN slotu
  9_Dovizli_Bakiyeler.xlsx      -> "Fis Uretici" sekmesi, KUR FARKI slotu
  10_Senet_Cek_Listesi.xlsx     -> "Fis Uretici" sekmesi, REESKONT slotu

  11_Tevkifat_Listesi.xlsx      -> "e-Fatura & KDV" sekmesi, TEVKIFAT slotu

  13_Bordro_Icmal.xlsx          -> "Bordro & Muhasebe Mutabakati" sekmesi (Yukle)
                                   (Mizan yuklu ise net<->335, SGK<->361,
                                    vergi<->360, personel gider<->720/760/770
                                    otomatik mutabik kilinir)

Sonra "Fis Uretici" (KDV mahsup + banka komisyon + amortisman + kur farki +
reeskont fisleri) ve
"Kapanis Dosyasi" (toplu rapor + audit) sekmelerine bakin.

MIZAN ICERIGI (~51 ana hesap, kumule Ocak-Mayis):
--------------------------------------------------
Hazir degerler (100,102,108), ticari alacaklar (120 ALICILAR x5, 121,126,128),
ortak cari (131), stoklar (153,157,159), GELECEK AYLARA AIT GIDERLER (180),
KDV (190 devreden,191,193), DURAN VARLIKLAR (252 binalar,253 makine,254 tasit,255 DEMIRBAS,
256,260 haklar) + BIRIKMIS AMORTISMANLAR (257,268), 280 gelecek yillara ait gider,
krediler (300,303,400), 320 SATICILAR x5, 321,326,335,340, ODENECEK VERGI/SGK
(360,361,368,370), 380 gelecek aya ait gelir, 391 hesaplanan KDV, ozkaynak
(500,570,580) ve gelir/gider (600,601,610,620,642,656,660,689,760,770).

BEKLENEN SONUCLAR (dogrulama icin):
-----------------------------------
[Mizan & Anomali]
* TERS BAKIYE: her firmada farkli ornek
   - 02 Demir Celik : 100 KASA alacak (negatif kasa) + 159 verilen avans alacak
   - 03 Gul Plastik : 360 Odenecek Vergi BORC bakiye (fazla odeme/mahsup)
   - 04 Ceyhan      : 340 Alinan Siparis Avansi BORC bakiye
* KAPANMAMIS GECICI HESAP: TUM firmalarda 191 Indirilecek + 391 Hesaplanan KDV
   donem sonu bakiye veriyor (KDV mahsup fisi kesilmemis).
* ANORMAL SAPMA: 02 Demir Celik'te 689 Olagandisi Gider sadece Mayis'ta ani giris
   (Mayis = kapanan ay oldugu icin BULGU olarak listelenir).
* AYLIK TREND: 254 Tasitlar Mart'ta 180.000 arac alimi -> "Aylik Hareket
   Yogunlugu" mini grafiginde Mart sutunu yukselir. NOT: anormal sapma taramasi
   yalnizca KAPANAN AYI (Mayis) denetler; gecmis ay sicramasi bulgu olarak cikmaz.

[Cari Mutabakat]  bizim(2) + karsi(3) dosyalari
* 120.01 ve 320.02 MUTABIK; 120.02 (karsida eksik fatura) ve 320.01
  (5.000 tutar farki) FARKLI cikar.

[e-Fatura & KDV]  GIB(4) + defter(5) + tevkifat(11) dosyalari
* 3 fatura "GIB'de var defterde yok" = GIRILMEMIS ALIS FATURASI (tahmini kayip KDV).
* KDV pozisyonu mizandan otomatik (191/391); beyanname taslagi.
* DEVREDEN KDV (190) TAKIBI:
   - 01/02/03 firmalari ODENECEK -> 190 hareketi yok (teyit gizli).
   - 04 Ceyhan: onceki donemden 190 devir 72.000 + dusuk satisli Mayis (hesaplanan
     63.000 < indirilecek 86.400) -> SONRAKI DONEME DEVREDEN 95.400. Mahsup fisi
     kesilmedigi icin 190 hala 72.000; m4 "mahsup bekliyor" teyidi: fis kesilince
     190 = 95.400 olmali (190/191/391 zinciri).
* TEVKIFAT(11): 5 kalem, matrah 173.000 -> hesaplanan KDV 34.600.
  Tevkif edilen 27.940 -> 360 (2 No.lu beyanname); indirilecek 6.660 -> 191.
  Oran bos olan 2 kalemde (isgucu temin 9/10, makine bakim 7/10) standart GIB
  tablosundan VARSAYILAN uygulanir -> "beyan oncesi dogrula" uyarisi.
  "2 No.lu Beyanname Taslagini Yazdir" ile ciktisi alinir (son onay kullanicida).

[Banka Ekstre Esleme]  banka(6) + defter102(7) dosyalari
* 6 birebir eslesen + 1 TOPLU eslesme (1:N -> banka 120.000 = defter 70.000+50.000;
  subset-sum sayesinde "eksik kayit" alarmi VERILMEZ), 4 komisyon
  (havale/eft/hesap isletim+bsmv/pos), 1 defterde fazla (kasa devir).

[Fis Uretici]  KDV mahsup fisi + 4 banka komisyon fisi onaya duser (ERP'ye
  gondermek icin KULLANICI ONAYI gerekir -> otomatik kayit YOK).

[Finansal Analiz]  bilanco DENK (denge_farki 0), gelir tablosu kari bilanco
  donem sonucuyla birebir esit (gt_sapma 0). Demirbas/duran amortismani,
  pesin giderler ve 7/A maliyetler dogru siniflanir.

[Eksik Belge Avcisi]  03 Gul Plastik (mizandan, ek dosya gerekmez):
* Duzenli Gider: 770 genel yonetim, 760 pazarlama, 660 kredi faizi Mayis'ta
  gelmemis -> kira/elektrik/faiz belgesi/fisi eksik olabilir.
* SGK/Vergi Tahakkuk: 361 SGK ve 360 gelir stopaji Mayis'ta durmus; operasyon
  surerken (gider hareketi var) tahakkuk yok -> muhtasar/SGK fisi unutulmus.
  (Ic tutarlilik uyarisi; kayit ONERILMEZ, son onay kullanicida.)

[Bordro & Muhasebe Mutabakati]  bordro(13) + mizan(1) dosyalari
* 01 Ornek Sanayi : MUTABIK -> net 37.170 = 335 Mayis, SGK 18.875 = 361 Mayis;
  vergi 5.330 <= 360 hareketi, personel gideri 61.375 <= 770+760 (bulgu 0).
* 02 / 04         : net/SGK Mayis hareketi bordrodan kucuk -> KESIN FARK cikar.
* 03 Gul Plastik  : 361/360 Mayis tahakkuku neredeyse yok -> SGK/vergi/gider
  tahakkuku EKSIK uyarilari (eksik profiliyle ortusur).
* Bordro icmal IC TUTARLILIGI: brut-kesinti=net her firmada tutar (uyari yok).

FIRMA PROFILLERI (panolar farkli gorunsun diye):
* 01 Ornek Sanayi   : SAGLIKLI (cari ~1,6 / belirgin risk YOK)
* 02 Demir Celik    : RISKLI (sermaye erimesi+likidite+asiri borc+ters bakiye+sapma)
* 03 Gul Plastik    : EKSIK BELGE/TAHAKKUK (Mayis duzenli giderler gelmemis, 360 ters)
* 04 Ceyhan Lojistik: DONEM ZARARI (4 kritik: likidite, negatif isletme serm.,
                      asiri borc, donem zarari)
"""


def main():
    os.makedirs(COK, exist_ok=True)
    with open(os.path.join(COK, "OKUBENI.txt"), "w", encoding="utf-8") as f:
        f.write(OKUBENI)
    for firma in FIRMALAR:
        klasor = os.path.join(COK, firma["kisa"])
        yaz_mizan(firma, klasor)
        yaz_cari(firma, klasor)
        yaz_gib(firma, klasor)
        yaz_banka(firma, klasor)
        yaz_demirbas(firma, klasor)
        yaz_dovizli(firma, klasor)
        yaz_senet(firma, klasor)
        yaz_tevkifat(firma, klasor)
        yaz_kdv_matrah(firma, klasor)
        yaz_bordro(firma, klasor)
        yaz_kredi(firma, klasor)
        yaz_sgk(firma, klasor)
        print(f"  OK  {firma['kod']} {firma['ad']}  -> {firma['kisa']}/ (15 dosya)")
    print(f"\nTest verisi hazir: {COK}")


if __name__ == "__main__":
    main()
