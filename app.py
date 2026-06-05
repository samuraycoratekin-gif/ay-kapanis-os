# -*- coding: utf-8 -*-
"""
Ay Kapanis OS - yerel web uygulamasi (sifir kurulum).

Python stdlib http.server uzerinde calisir; Flask/pandas GEREKMEZ.
(Akilli Mutabakat demosuyla ayni desen.)

Iki katman:
  KATMAN 1  Ofis Panosu      /            -> tum musteriler
  KATMAN 2  Kapanis Kokpiti  /kokpit      -> tek musteri, modul menusu

Asama 0: cok-musteri iskelet + modul registry + durum JSON.
Moduller henuz placeholder; Asama 1'den itibaren ic dolar.

Calistirma: baslat.bat  (ya da: python app.py)  ->  http://localhost:5050
"""
import os, sys, json, base64, threading, webbrowser, secrets, http.cookies
from datetime import datetime
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from core import depo
from core import cari_analiz
from core import ayarlar
from core import moduller as M

M.yukle_hepsi()                      # moduller/ icindeki tum modulleri kaydet
AKTIF_DONEM = "2026-05"              # varsayilan donem
DONEMLER = ["2026-05", "2026-04", "2026-03", "2026-02", "2026-01"]  # secilebilir donemler

TPL = os.path.join(HERE, "templates")
STATIC = os.path.join(HERE, "static")

# --------------------------------------------------------------------------- #
# Giris (auth) — tek ortak parola. Parola yalniz env'de tutulur (GIRIS_PAROLASI).
# Env yoksa (yerel calistirma) kapi kapali: sifir kurulum korunur.
# Bulutta (Railway) env'i MUTLAKA ayarla — yoksa gercek veri korumasiz kalir.
# --------------------------------------------------------------------------- #
GIRIS_PAROLASI = os.environ.get("GIRIS_PAROLASI", "")
BULUT = bool(os.environ.get("PORT"))
_OTURUMLAR = set()                    # gecerli oturum token'lari (process bellekte)


def _auth_aktif():
    return bool(GIRIS_PAROLASI)


def _oturum_gecerli(handler):
    if not _auth_aktif():
        return True
    ck = http.cookies.SimpleCookie(handler.headers.get("Cookie", ""))
    t = ck.get("oturum")
    return bool(t and t.value in _OTURUMLAR)


def _giris_sayfa(hata=False):
    uyari = ('<p style="color:#c0392b;margin-top:8px;">Parola hatalı, tekrar deneyin.</p>'
             if hata else "")
    return f"""<!DOCTYPE html><html lang="tr"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Giriş — Ay Kapanış OS</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700;800&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<link rel="stylesheet" href="/static/stil.css">
</head><body><div class="container" style="max-width:420px;margin:12vh auto;">
  <section class="panel" style="text-align:center;">
    <h1 style="margin-bottom:6px;"><i class="fa-solid fa-lock"></i> Ay Kapanış OS</h1>
    <p style="color:var(--text-muted);margin-bottom:18px;">Devam etmek için ofis parolasını girin.</p>
    <form method="POST" action="/giris">
      <input type="password" name="parola" placeholder="Ofis parolası" required autofocus
             style="width:100%;padding:12px;border-radius:10px;border:1px solid #cbd5e1;font-size:15px;">
      <button class="btn" type="submit" style="width:100%;margin-top:12px;">
        <i class="fa-solid fa-right-to-bracket"></i> Giriş</button>
    </form>{uyari}
  </section>
  <footer style="text-align:center;"><p>Ay Kapanış OS &copy; 2026</p></footer>
</div></body></html>"""


# --------------------------------------------------------------------------- #
# API fonksiyonlari (hepsi JSON/dict dondurur)
# --------------------------------------------------------------------------- #
def api_ofis(donem=None):
    """Ofis panosu: tum musteriler + secili donem ozetleri."""
    donem = donem or AKTIF_DONEM
    kodlar = M.kodlar()
    out = []
    for m in depo.musterileri_getir():
        d = depo.donem_getir(m["id"], donem, kodlar)
        bulgu = sum(x.get("bulgu_sayisi", 0) for x in d["moduller"].values())
        out.append({**m, "genel_ilerleme": d["genel_ilerleme"],
                    "bulgu": bulgu, "son_tarih": d.get("son_tarih")})
    return {"donem": donem, "donemler": DONEMLER, "musteriler": out}


def api_kokpit(musteri_id, donem):
    m = depo.musteri_getir(musteri_id)
    if not m:
        return {"hata": "Musteri bulunamadi."}
    durum = depo.donem_getir(musteri_id, donem, M.kodlar())
    moduller = [{"kod": x.kod, "ad": x.ad, "ikon": x.ikon} for x in M.liste()]
    return {"musteri": m, "donem": donem, "donemler": DONEMLER, "durum": durum, "moduller": moduller,
            "kilitli": bool(durum.get("kilitli")),
            "kilit_kullanici": durum.get("kilit_kullanici", ""),
            "aktif_kullanici": depo.aktif_kullanici()}


def api_kullanicilar():
    return {"kullanicilar": depo.kullanicilari_getir(),
            "aktif": depo.aktif_kullanici(), "roller": depo.ROLLER}


def api_aktif_kullanici(body):
    k = depo.aktif_kullanici_ayarla(body.get("id"))
    if not k:
        return {"hata": "Kullanıcı bulunamadı."}
    return {"ok": True, "aktif": k}


def api_donem_kilit(body):
    """Donemi kilitler/acar. Sadece mudur yetkili."""
    if not depo.yetkili_mi("kilit"):
        return {"hata": "Dönem kilitleme yetkisi yalnızca Muhasebe Müdüründe."}
    musteri_id = body.get("m"); donem = body.get("d")
    kilitli = bool(body.get("kilitli"))
    k = depo.aktif_kullanici()
    depo.donem_kilit_ayarla(musteri_id, donem, kilitli, k["ad"] if k else "")
    return {"ok": True, "kilitli": kilitli}


def api_modul(musteri_id, donem, kod):
    mod = M.getir(kod)
    if not mod:
        return {"hata": "Modul bulunamadi."}
    sonuc = mod.calistir(musteri_id, donem)
    return {"html": mod.panel_html(sonuc)}


def api_ayarlar_oku():
    return {"ok": True, "ayarlar": ayarlar.oku(), "varsayilan": ayarlar.VARSAYILAN}


def _sayi(v, vars):
    try:
        return float(v)
    except (TypeError, ValueError):
        return vars


def api_ayarlar_yaz(body):
    """Ofis genelindeki esik/listeleri gunceller. Yalniz bilinen alanlar
    yazilir; tipler dogrulanir. Son onay kullanicida — bu yalniz tarama
    esiklerini ayarlar, otomatik kayit YOK."""
    if not depo.yetkili_mi("kilit"):
        return {"hata": "Ayarları değiştirme yetkisi yalnızca Muhasebe Müdüründe."}
    mevcut = ayarlar.oku()
    yeni = dict(mevcut)

    zh = body.get("zorunlu_hesaplar")
    if isinstance(zh, dict):
        temiz = {}
        for kod, et in zh.items():
            k = str(kod).strip()[:3]
            if k.isdigit() and len(k) == 3:
                temiz[k] = str(et).strip() or k
        if temiz:
            yeni["zorunlu_hesaplar"] = temiz

    if "mizan_sapma_yuzde" in body:
        yeni["mizan_sapma_yuzde"] = max(0.0, _sayi(body["mizan_sapma_yuzde"], mevcut["mizan_sapma_yuzde"]))
    if "mizan_sapma_min_tutar" in body:
        yeni["mizan_sapma_min_tutar"] = max(0.0, _sayi(body["mizan_sapma_min_tutar"], mevcut["mizan_sapma_min_tutar"]))
    if "zorunlu_hesap_tolerans" in body:
        yeni["zorunlu_hesap_tolerans"] = max(0.0, _sayi(body["zorunlu_hesap_tolerans"], mevcut["zorunlu_hesap_tolerans"]))
    if "tevkifat_varsayilan_pay" in body:
        yeni["tevkifat_varsayilan_pay"] = max(0, int(_sayi(body["tevkifat_varsayilan_pay"], mevcut["tevkifat_varsayilan_pay"])))
    if "tevkifat_varsayilan_payda" in body:
        pd = int(_sayi(body["tevkifat_varsayilan_payda"], mevcut["tevkifat_varsayilan_payda"]))
        yeni["tevkifat_varsayilan_payda"] = pd if pd > 0 else mevcut["tevkifat_varsayilan_payda"]
    if "kdv_oran_tolerans_yuzde" in body:
        yeni["kdv_oran_tolerans_yuzde"] = max(0.0, _sayi(body["kdv_oran_tolerans_yuzde"], mevcut["kdv_oran_tolerans_yuzde"]))
    if "kdv_tutar_tolerans" in body:
        yeni["kdv_tutar_tolerans"] = max(0.0, _sayi(body["kdv_tutar_tolerans"], mevcut["kdv_tutar_tolerans"]))

    return {"ok": True, "ayarlar": ayarlar.yaz(yeni)}


def api_musteri_ekle(body):
    m = depo.musteri_ekle(body.get("unvan", "Yeni Musteri"),
                          body.get("vergi_no", ""))
    depo.donem_getir(m["id"], AKTIF_DONEM, M.kodlar())   # ilk donemi ac
    return {"ok": True, "musteri": m}


def api_yukle(body):
    """Modul icin dosya yukler (base64). Kaydeder; modulu hemen calistirir.
    rol verilirse cok-slotlu modul (or. cari bizim/karsi) icin ayri slot."""
    musteri_id = body.get("m"); donem = body.get("d"); kod = body.get("kod")
    if depo.donem_kilitli_mi(musteri_id, donem):
        return {"hata": "Dönem kilitli — yeni dosya yüklenemez. Önce kilidi açın."}
    rol = body.get("rol")
    ad = body.get("dosya_adi"); b64 = body.get("dosya_b64", "")
    if "," in b64:
        b64 = b64.split(",", 1)[1]
    icerik = base64.b64decode(b64)
    depo.yuklenen_kaydet(musteri_id, donem, kod, ad, icerik, rol=rol)
    mod = M.getir(kod)
    sonuc = mod.calistir(musteri_id, donem) if mod else {}
    return {"ok": True, "html": mod.panel_html(sonuc) if mod else ""}


def rapor_sayfa(musteri_id, donem, tip):
    """Finansal raporu (gelir/bilanco) AYRI tam sayfa olarak uretir."""
    m = depo.musteri_getir(musteri_id)
    if not m:
        return "<h2>Müşteri bulunamadı.</h2>"
    from moduller import m9_finansal
    sonuc = m9_finansal.calistir(musteri_id, donem)
    govde = m9_finansal.rapor_govde(sonuc, tip)
    bas = "Gelir Tablosu" if tip == "gelir" else "Bilanço"
    return f"""<!DOCTYPE html><html lang="tr"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{bas} — {m['unvan']}</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700;800&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<link rel="stylesheet" href="/static/stil.css">
<style>@media print{{.no-print{{display:none}}}}</style>
</head><body><div class="container">
  <header><div class="logo-area"><h1><i class="fa-solid fa-chart-line"></i> {bas}</h1>
    <p>{m['unvan']} · {m['id']} · Dönem: {donem}</p></div>
    <div class="header-meta no-print">
      <button class="btn-sec" onclick="window.close()"><i class="fa-solid fa-xmark"></i> Kapat</button>
      <button class="btn" onclick="window.print()"><i class="fa-solid fa-print"></i> Yazdır / PDF</button>
    </div></header>
  <main class="content-container"><section class="panel">{govde}</section></main>
  <footer><p>Ay Kapanış OS &copy; 2026 · Finansal Analiz Raporu</p></footer>
</div></body></html>"""


def kapanis_rapor_sayfa(musteri_id, donem):
    """Tum modulleri birlestiren kapanis raporunu AYRI tam sayfa olarak uretir."""
    m = depo.musteri_getir(musteri_id)
    if not m:
        return "<h2>Müşteri bulunamadı.</h2>"
    from moduller import m8_dosya
    sonuc = m8_dosya.calistir(musteri_id, donem)
    govde = m8_dosya.kapanis_rapor_govde(sonuc)
    return f"""<!DOCTYPE html><html lang="tr"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Kapanış Raporu — {m['unvan']}</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700;800&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<link rel="stylesheet" href="/static/stil.css">
<style>@media print{{.no-print{{display:none}}}}</style>
</head><body><div class="container">
  <header><div class="logo-area"><h1><i class="fa-solid fa-folder-tree"></i> Kapanış Raporu</h1>
    <p>{m['unvan']} · {m['id']} · Dönem: {donem}</p></div>
    <div class="header-meta no-print">
      <button class="btn-sec" onclick="window.close()"><i class="fa-solid fa-xmark"></i> Kapat</button>
      <button class="btn" onclick="window.print()"><i class="fa-solid fa-print"></i> Yazdır / PDF</button>
    </div></header>
  <main class="content-container"><section class="panel">{govde}</section></main>
  <footer><p>Ay Kapanış OS &copy; 2026 · Dönem Kapanış Raporu</p></footer>
</div></body></html>"""


def _mektup_govde(m, donem, cari, y):
    """Tek cari icin mutabakat mektubu govdesi."""
    from moduller.m3_cari import _tl
    k = depo.aktif_kullanici()
    imza = k["ad"] if k else ""
    bugun = y.get("bugun", donem)
    bakiye = cari["net"]
    yon = "borçlu" if bakiye >= 0 else "alacaklı"
    return f"""
    <div style="max-width:720px;margin:0 auto;">
      <p style="text-align:right;color:var(--text-muted);">Tarih: {bugun}</p>
      <p style="margin-top:10px;"><strong>Sayın {cari['cari_adi']}</strong> ({cari['cari_kodu']})</p>
      <p style="margin-top:16px;line-height:1.7;">
        {m['unvan']} ({m['id']}) defter kayıtlarımıza göre, <strong>{bugun}</strong> tarihi itibarıyla
        firmanız ile aramızdaki cari hesap bakiyesi <strong>{_tl(abs(bakiye))}</strong>
        ({yon} bakiye) olarak görünmektedir.</p>
      <p style="margin-top:10px;line-height:1.7;">
        Söz konusu bakiyenin kayıtlarınızla mutabık olup olmadığını, mutabık değilse farkın
        kaynağını belirten dökümü tarafımıza bildirmenizi rica ederiz.</p>
      <table style="margin-top:16px;width:100%;">
        <tr><th style="text-align:left">Yaş Aralığı</th><th style="text-align:right">Tutar</th></tr>
        {"".join(f'<tr><td>{e} gün</td><td style="text-align:right">{_tl(cari["kovalar"][e])}</td></tr>' for e in cari_analiz.KOVA_ETIKET if cari["kovalar"][e])}
        <tr style="font-weight:700;"><td>Toplam</td><td style="text-align:right">{_tl(bakiye)}</td></tr>
      </table>
      <div style="margin-top:40px;display:flex;justify-content:space-between;">
        <div><p style="border-top:1px solid var(--text-muted);padding-top:6px;">{m['unvan']}<br>{imza}</p></div>
        <div><p style="border-top:1px solid var(--text-muted);padding-top:6px;">Karşı Taraf Onayı<br>(Kaşe / İmza)</p></div>
      </div>
      <p style="margin-top:24px;font-size:11px;color:var(--text-muted);">
        Bu mektup bilgilendirme amaçlıdır; defter kayıtlarımız esas alınarak hazırlanmıştır.</p>
    </div>"""


def cari_mektup_sayfa(musteri_id, donem, cari_kodu):
    """Cari mutabakat mektubu — tek cari veya '__hepsi__' icin toplu, ayri sayfa."""
    m = depo.musteri_getir(musteri_id)
    if not m:
        return "<h2>Müşteri bulunamadı.</h2>"
    mod = M.getir("m3_cari")
    sonuc = mod.calistir(musteri_id, donem) if mod else {}
    y = sonuc.get("yaslandirma") or {}
    cariler = y.get("cariler", [])
    if not cariler:
        govde = "<p>Yaşlandırılacak cari bakiye bulunamadı. Önce bizim defter dosyasını yükleyin.</p>"
    elif cari_kodu == "__hepsi__":
        govde = ('<div style="page-break-after:always;"></div>'.join(
            _mektup_govde(m, donem, c, y) for c in cariler))
    else:
        sec = next((c for c in cariler if c["cari_kodu"] == cari_kodu), None)
        govde = (_mektup_govde(m, donem, sec, y) if sec
                 else f"<p>{cari_kodu} kodlu cari için açık bakiye bulunamadı.</p>")
    return f"""<!DOCTYPE html><html lang="tr"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Mutabakat Mektubu — {m['unvan']}</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700;800&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<link rel="stylesheet" href="/static/stil.css">
<style>@media print{{.no-print{{display:none}}}}</style>
</head><body><div class="container">
  <header><div class="logo-area"><h1><i class="fa-solid fa-envelope-open-text"></i> Mutabakat Mektubu</h1>
    <p>{m['unvan']} · {m['id']} · Dönem: {donem}</p></div>
    <div class="header-meta no-print">
      <button class="btn-sec" onclick="window.close()"><i class="fa-solid fa-xmark"></i> Kapat</button>
      <button class="btn" onclick="window.print()"><i class="fa-solid fa-print"></i> Yazdır / PDF</button>
    </div></header>
  <main class="content-container"><section class="panel">{govde}</section></main>
  <footer><p>Ay Kapanış OS &copy; 2026 · Cari Mutabakat Mektubu</p></footer>
</div></body></html>"""


def tevkifat_beyan_sayfa(musteri_id, donem):
    """2 No.lu KDV (tevkifat) beyanname taslagi — yazdirilabilir sayfa."""
    from moduller.m4_gib_kdv import _tl
    m = depo.musteri_getir(musteri_id)
    if not m:
        return "<h2>Müşteri bulunamadı.</h2>"
    mod = M.getir("m4_gib_kdv")
    sonuc = mod.calistir(musteri_id, donem) if mod else {}
    tev = sonuc.get("tevkifat")
    if not tev or tev.get("hata"):
        govde = "<p>Tevkifat listesi bulunamadı veya okunamadı. Önce tevkifat dosyasını yükleyin.</p>"
    else:
        sat = "".join(
            f'<tr><td>{s["islem"]}</td><td style="text-align:right">{_tl(s["matrah"])}</td>'
            f'<td style="text-align:center">%{int(s["kdv_orani"])}</td>'
            f'<td style="text-align:right">{_tl(s["kdv"])}</td>'
            f'<td style="text-align:center">{s["oran_metin"]}</td>'
            f'<td style="text-align:right">{_tl(s["tevkif"])}</td>'
            f'<td style="text-align:right">{_tl(s["indirilecek"])}</td></tr>'
            for s in tev["satirlar"])
        govde = f"""
        <div style="max-width:840px;margin:0 auto;">
          <h2 style="margin-bottom:4px;">KDV Tevkifatı — 2 No.lu Beyanname Taslağı</h2>
          <p style="color:var(--text-muted);">{m['unvan']} ({m['id']}) · Dönem: {donem}</p>
          <p style="margin-top:14px;line-height:1.7;">Aşağıdaki kısmi tevkifata tabi alış hizmetleri için
            alıcı sorumlu sıfatıyla tevkif edilen KDV, <strong>360 Ödenecek Vergi ve Fonlar</strong>
            hesabına kaydedilir ve 2 No.lu KDV beyannamesi ile beyan edilir. Satıcıya ödenen kısım
            <strong>191 İndirilecek KDV</strong>'dir.</p>
          <table style="margin-top:16px;width:100%;">
            <tr><th style="text-align:left">İşlem Türü</th><th style="text-align:right">Matrah</th>
                <th style="text-align:center">KDV%</th><th style="text-align:right">Hesaplanan KDV</th>
                <th style="text-align:center">Tevkifat Oranı</th><th style="text-align:right">Tevkif Edilen (360)</th>
                <th style="text-align:right">İndirilecek (191)</th></tr>
            {sat}
            <tr style="font-weight:700;border-top:2px solid #888;"><td>TOPLAM</td>
              <td style="text-align:right">{_tl(tev['toplam_matrah'])}</td><td></td>
              <td style="text-align:right">{_tl(tev['toplam_kdv'])}</td><td></td>
              <td style="text-align:right">{_tl(tev['toplam_tevkif'])}</td>
              <td style="text-align:right">{_tl(tev['toplam_indirilecek'])}</td></tr>
          </table>
          <p style="margin-top:24px;line-height:1.8;"><strong>Beyan Özeti</strong><br>
            2 No.lu KDV Beyannamesi (sorumlu sıfatıyla ödenecek tevkifat): <strong>{_tl(tev['toplam_tevkif'])}</strong><br>
            1 No.lu KDV Beyannamesi indirilecek KDV (bu hizmetlerden): <strong>{_tl(tev['toplam_indirilecek'])}</strong></p>
          <p style="margin-top:24px;font-size:11px;color:var(--text-muted);">
            Bu taslak yüklenen tevkifat listesinden üretilmiştir; beyan öncesi kontrol amaçlıdır.
            Nihai onay ve beyan kullanıcıya aittir.</p>
        </div>"""
    return f"""<!DOCTYPE html><html lang="tr"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Tevkifat Beyanname Taslağı — {m['unvan']}</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700;800&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<link rel="stylesheet" href="/static/stil.css">
<style>@media print{{.no-print{{display:none}}}}</style>
</head><body><div class="container">
  <header><div class="logo-area"><h1><i class="fa-solid fa-scissors"></i> Tevkifat Beyanname Taslağı</h1>
    <p>{m['unvan']} · {m['id']} · Dönem: {donem}</p></div>
    <div class="header-meta no-print">
      <button class="btn-sec" onclick="window.close()"><i class="fa-solid fa-xmark"></i> Kapat</button>
      <button class="btn" onclick="window.print()"><i class="fa-solid fa-print"></i> Yazdır / PDF</button>
    </div></header>
  <main class="content-container"><section class="panel">{govde}</section></main>
  <footer><p>Ay Kapanış OS &copy; 2026 · 2 No.lu KDV Beyanname Taslağı</p></footer>
</div></body></html>"""


def api_fis_islem(body):
    """Tek fis icin onay/gonderme islemi; son onay kullanicidadir.
    islem: onayla | gonder | reddet | geri. Modulu yeniden calistirir."""
    musteri_id = body.get("m"); donem = body.get("d")
    anahtar = body.get("anahtar"); islem = body.get("islem")
    HARITA = {"onayla": "onaylandi", "gonder": "gonderildi",
              "reddet": "reddedildi", "geri": "taslak"}
    yeni = HARITA.get(islem)
    if not yeni:
        return {"hata": "Geçersiz işlem."}
    if depo.donem_kilitli_mi(musteri_id, donem):
        return {"hata": "Dönem kilitli — fiş işlemi yapılamaz."}
    # Onay/gonderme/red sadece mudur yetkisinde; "geri" (taslaga al) herkese acik
    if islem in ("onayla", "gonder", "reddet") and not depo.yetkili_mi("onay"):
        return {"hata": "Fiş onay/gönderme yetkisi yalnızca Muhasebe Müdüründe."}
    # Gondermeden once onay sarti
    if islem == "gonder":
        mevcut = depo.fis_durumlari(musteri_id, donem).get(anahtar, {}).get("durum")
        if mevcut != "onaylandi":
            return {"hata": "ERP'ye göndermeden önce fiş onaylanmalı."}
    k = depo.aktif_kullanici()
    depo.fis_durum_guncelle(musteri_id, donem, anahtar, yeni, k["ad"] if k else "")
    mod = M.getir("m6_fis")
    sonuc = mod.calistir(musteri_id, donem) if mod else {}
    return {"ok": True, "html": mod.panel_html(sonuc) if mod else ""}


def api_mutabakat_modu(body):
    """Musterinin Akilli Mutabakat sahipligini ac/kapat; modulu yeniden calistirir."""
    musteri_id = body.get("m"); donem = body.get("d")
    deger = bool(body.get("deger"))
    depo.musteri_guncelle(musteri_id, akilli_mutabakat=deger)
    mod = M.getir("m3_cari")
    sonuc = mod.calistir(musteri_id, donem) if mod else {}
    return {"ok": True, "html": mod.panel_html(sonuc) if mod else ""}


# --------------------------------------------------------------------------- #
# HTTP katmani
# --------------------------------------------------------------------------- #
def _dosya_oku(yol):
    with open(yol, encoding="utf-8") as f:
        return f.read()


def _hata_logla(istek, e):
    """Sunucu hatasini stdout'a yazar (Railway log gormesi icin) — canli teshis."""
    import traceback
    print(f"[HATA] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {istek}: {e!r}", flush=True)
    traceback.print_exc()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _gonder(self, data, ctype="application/json; charset=utf-8", code=200):
        if isinstance(data, (dict, list)):
            data = json.dumps(data, ensure_ascii=False)
        data = data.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _oturum_kur(self, token, hedef="/"):
        """Basarili giriste cerez koyar ve hedefe yonlendirir."""
        guvenli = "; Secure" if BULUT else ""
        self.send_response(302)
        self.send_header("Set-Cookie", f"oturum={token}; Path=/; HttpOnly; SameSite=Lax{guvenli}")
        self.send_header("Location", hedef)
        self.end_headers()

    def _yonlendir(self, hedef):
        self.send_response(302)
        self.send_header("Location", hedef)
        self.end_headers()

    def do_GET(self):
        u = urlparse(self.path)
        p, q = u.path, parse_qs(u.query)
        try:
            # --- Giris kapisi: /giris, /cikis ve /static disinda her sey oturum ister ---
            if p == "/giris":
                return self._gonder(_giris_sayfa(hata=bool(q.get("hata"))),
                                    "text/html; charset=utf-8")
            if p == "/cikis":
                ck = http.cookies.SimpleCookie(self.headers.get("Cookie", ""))
                t = ck.get("oturum")
                if t:
                    _OTURUMLAR.discard(t.value)
                return self._yonlendir("/giris")
            if not p.startswith("/static/") and not _oturum_gecerli(self):
                if p.startswith("/api/"):
                    return self._gonder({"hata": "Oturum gerekli.", "giris": True}, code=401)
                return self._yonlendir("/giris")

            if p in ("/", "/index.html"):
                return self._gonder(_dosya_oku(os.path.join(TPL, "ofis_panosu.html")),
                                    "text/html; charset=utf-8")
            if p in ("/kokpit", "/kokpit.html"):
                return self._gonder(_dosya_oku(os.path.join(TPL, "kapanis_kokpit.html")),
                                    "text/html; charset=utf-8")
            if p == "/rapor":
                return self._gonder(rapor_sayfa((q.get("m") or [""])[0],
                                                (q.get("d") or [""])[0],
                                                (q.get("tip") or ["bilanco"])[0]),
                                    "text/html; charset=utf-8")
            if p == "/kapanis_rapor":
                return self._gonder(kapanis_rapor_sayfa((q.get("m") or [""])[0],
                                                        (q.get("d") or [""])[0]),
                                    "text/html; charset=utf-8")
            if p == "/cari_mektup":
                return self._gonder(cari_mektup_sayfa((q.get("m") or [""])[0],
                                                      (q.get("d") or [""])[0],
                                                      (q.get("cari") or [""])[0]),
                                    "text/html; charset=utf-8")
            if p == "/tevkifat_beyan":
                return self._gonder(tevkifat_beyan_sayfa((q.get("m") or [""])[0],
                                                         (q.get("d") or [""])[0]),
                                    "text/html; charset=utf-8")
            if p.startswith("/static/"):
                ad = os.path.basename(p[len("/static/"):])
                yol = os.path.join(STATIC, ad)
                if os.path.exists(yol):
                    ctype = "text/css" if ad.endswith(".css") else "application/octet-stream"
                    return self._gonder(_dosya_oku(yol), ctype + "; charset=utf-8")
                return self._gonder({"hata": "bulunamadi"}, code=404)
            if p == "/api/ofis":
                return self._gonder(api_ofis((q.get("d") or [None])[0]))
            if p == "/api/kokpit":
                return self._gonder(api_kokpit((q.get("m") or [""])[0], (q.get("d") or [""])[0]))
            if p == "/api/kullanicilar":
                return self._gonder(api_kullanicilar())
            if p == "/api/ayarlar":
                return self._gonder(api_ayarlar_oku())
            if p == "/api/modul":
                return self._gonder(api_modul((q.get("m") or [""])[0],
                                              (q.get("d") or [""])[0],
                                              (q.get("kod") or [""])[0]))
        except Exception as e:
            _hata_logla(f"GET {self.path}", e)
            return self._gonder({"hata": str(e)}, code=500)
        return self._gonder({"hata": "bulunamadi"}, code=404)

    def do_POST(self):
        p = urlparse(self.path).path
        n = int(self.headers.get("Content-Length", 0))
        ham = self.rfile.read(n)
        # --- Giris formu (urlencoded), JSON'dan ONCE ele alinir ---
        if p == "/giris":
            parola = (parse_qs(ham.decode("utf-8", "replace")).get("parola") or [""])[0]
            if _auth_aktif() and secrets.compare_digest(parola, GIRIS_PAROLASI):
                t = secrets.token_urlsafe(32)
                _OTURUMLAR.add(t)
                return self._oturum_kur(t, "/")
            return self._yonlendir("/giris?hata=1")
        if not _oturum_gecerli(self):
            return self._gonder({"hata": "Oturum gerekli.", "giris": True}, code=401)
        body = json.loads(ham or b"{}")
        try:
            if p == "/api/musteri_ekle":
                return self._gonder(api_musteri_ekle(body))
            if p == "/api/yukle":
                return self._gonder(api_yukle(body))
            if p == "/api/mutabakat_modu":
                return self._gonder(api_mutabakat_modu(body))
            if p == "/api/fis_islem":
                return self._gonder(api_fis_islem(body))
            if p == "/api/aktif_kullanici":
                return self._gonder(api_aktif_kullanici(body))
            if p == "/api/donem_kilit":
                return self._gonder(api_donem_kilit(body))
            if p == "/api/ayarlar":
                return self._gonder(api_ayarlar_yaz(body))
        except Exception as e:
            _hata_logla(f"POST {p}", e)
            return self._gonder({"hata": str(e)}, code=500)
        return self._gonder({"hata": "bulunamadi"}, code=404)


def main(port=None):
    # Railway/bulut PORT'u env ile verir; yerelde 5050.
    port = port or int(os.environ.get("PORT", 5050))
    # Bulutta 0.0.0.0'a baglanmak zorunlu; yerelde sadece localhost.
    bulut = bool(os.environ.get("PORT"))
    host = os.environ.get("HOST") or ("0.0.0.0" if bulut else "127.0.0.1")
    seed()
    srv = ThreadingHTTPServer((host, port), Handler)
    url = f"http://localhost:{port}"
    print(f"Ay Kapanis OS calisiyor:  {host}:{port}", flush=True)
    print("Kapatmak icin Ctrl+C.", flush=True)
    if not bulut:                       # tarayiciyi yalniz yerelde ac
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nKapatiliyor...")
        srv.shutdown()


# --------------------------------------------------------------------------- #
# Demo/seed verisi (ilk calistirmada ornek musteriler olusturur)
# --------------------------------------------------------------------------- #
def seed():
    if not depo.kullanicilari_getir():
        depo.kullanici_ekle("Ayşe Yılmaz (Müdür)", "mudur")
        depo.kullanici_ekle("Mehmet Demir", "eleman")
    if depo.musterileri_getir():
        return
    ornekler = [
        ("ÖRNEK SANAYİ A.Ş.", "1234567890", "Logo Tiger"),
        ("DEMİR ÇELİK TİC. LTD.", "2345678901", "Mikro"),
        ("GÜL PLASTİK SAN. A.Ş.", "3456789012", "Netsis"),
        ("CEYHAN LOJİSTİK A.Ş.", "4567890123", "Dosya Yükleme"),
    ]
    kodlar = M.kodlar()
    for unvan, vno, erp in ornekler:
        m = depo.musteri_ekle(unvan, vno, erp)
        d = depo.donem_getir(m["id"], AKTIF_DONEM, kodlar)
        d["son_tarih"] = "2026-06-26"
        depo.donem_kaydet(m["id"], AKTIF_DONEM, d)


if __name__ == "__main__":
    main()
