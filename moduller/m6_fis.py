# -*- coding: utf-8 -*-
"""M6 - Kapanis Fisi Uretici & Onay Merkezi (Asama 5).

Mevcut verilerden kapanis fislerini uretir:
  - KDV Mahsup Fisi (mizandan, M2)
  - Banka Masraf/Komisyon Fisleri (M5 banka eslemesinden)
  (ileride: amortisman, kur farki, reeskont)

Her fis onizlenir -> kullanici ONAYLAR -> ERP'ye GONDERILIR. Otomatik kayit YOK;
son onay her zaman kullanicidadir.
"""
import calendar
from core.moduller import Modul, kaydet
from core import depo, mizan_oku, banka_oku, banka_analiz, fis_uret, varlik_oku

AD = "Fiş Üretici & Onay Merkezi"
ACIKLAMA = "Kapanış fişlerini hesaplar, önizler; siz onaylayınca ERP'ye gönderilir. Otomatik kayıt yok."

# Reeskont varsayilan yillik faiz (%). Senet listesinde 'faiz' sutunu varsa o kullanilir.
REESKONT_VARSAYILAN_FAIZ = 50.0


def _donem_sonu(donem):
    """'2026-04' -> '2026-04-30' (ayin son gunu)."""
    try:
        y, a = donem.split("-")[:2]
        son = calendar.monthrange(int(y), int(a))[1]
        return f"{y}-{a}-{son:02d}"
    except Exception:
        return f"{donem}-28"

DURUM_ET = {"taslak": ("Taslak", "neutral"), "onaylandi": ("Onaylandı", "success"),
            "gonderildi": ("ERP'ye Gönderildi", "success"), "reddedildi": ("Reddedildi", "err")}


def _adaylari_uret(musteri_id, donem):
    fisler = []
    mizan_yol = depo.yuklenen_bul(musteri_id, donem, "m2_mizan")
    if mizan_yol:
        try:
            mizan = mizan_oku.oku(mizan_yol)
            # Mahsup fisi DONEM SONU tarihli olmali (ay basi degil) — diger
            # kapanis fisleriyle ayni kural.
            f = fis_uret.kdv_mahsup_fisi(mizan, _donem_sonu(donem))
            if f:
                fisler.append(f)
            fisler.extend(fis_uret.yedi_a_virman_fisleri(mizan, _donem_sonu(donem)))
        except Exception:
            pass
    banka_yol = depo.yuklenen_bul(musteri_id, donem, "m5_banka", rol="banka")
    defter_yol = depo.yuklenen_bul(musteri_id, donem, "m5_banka", rol="defter")
    if banka_yol and defter_yol:
        try:
            banka = banka_oku.oku(banka_yol, kaynak="banka")
            defter = banka_oku.oku(defter_yol, kaynak="defter")
            r = banka_analiz.esle(banka, defter)
            fisler.extend(fis_uret.banka_komisyon_fisleri(r["komisyon"]))
        except Exception:
            pass

    tarih = _donem_sonu(donem)
    dem_yol = depo.yuklenen_bul(musteri_id, donem, "m6_fis", rol="demirbas")
    if dem_yol:
        try:
            f = fis_uret.amortisman_fisi(varlik_oku.demirbas_oku(dem_yol), tarih)
            if f:
                fisler.append(f)
        except Exception:
            pass
    dov_yol = depo.yuklenen_bul(musteri_id, donem, "m6_fis", rol="dovizli")
    if dov_yol:
        try:
            f = fis_uret.kur_farki_fisi(varlik_oku.dovizli_oku(dov_yol), tarih)
            if f:
                fisler.append(f)
        except Exception:
            pass
    sen_yol = depo.yuklenen_bul(musteri_id, donem, "m6_fis", rol="senet")
    if sen_yol:
        try:
            f = fis_uret.reeskont_fisi(varlik_oku.senet_oku(sen_yol), tarih,
                                       REESKONT_VARSAYILAN_FAIZ)
            if f:
                fisler.append(f)
        except Exception:
            pass
    return fisler


def calistir(musteri_id, donem):
    fisler = _adaylari_uret(musteri_id, donem)
    durumlar = depo.fis_durumlari(musteri_id, donem)
    for f in fisler:
        f["durum"] = durumlar.get(f["anahtar"], {}).get("durum", "taslak")
        f["zaman"] = durumlar.get(f["anahtar"], {}).get("zaman", "")

    bekleyen = sum(1 for f in fisler if f["durum"] in ("taslak", "onaylandi"))
    depo.modul_durum_guncelle(musteri_id, donem, "m6_fis",
                              durum=("tamam" if fisler and bekleyen == 0 else
                                     ("uyari" if fisler else "bekliyor")),
                              ilerleme=(100 if fisler and bekleyen == 0 else (40 if fisler else 0)),
                              bulgu_sayisi=bekleyen)
    slotlar = {rol: bool(depo.yuklenen_bul(musteri_id, donem, "m6_fis", rol=rol))
               for rol in ("demirbas", "dovizli", "senet")}
    return {"hazir": True, "fisler": fisler, "slotlar": slotlar}


# --------------------------------------------------------------------------- #
def _tl(v):
    return f"{v:,.2f} TL".replace(",", "X").replace(".", ",").replace("X", ".")


def _baslik():
    return f"""
    <div class="panel-header">
      <div class="panel-title"><h2><i class="fa-solid fa-stamp"></i> {AD}</h2>
      <p>{ACIKLAMA}</p></div>
      <div class="panel-header-icon"><i class="fa-solid fa-stamp"></i></div>
    </div>"""


def _fis_karti(f):
    et, rozet = DURUM_ET.get(f["durum"], ("Taslak", "neutral"))
    satir = "".join(
        f'<tr><td><span class="badge neutral">{s["hesap"]}</span></td><td>{s["ad"]}</td>'
        f'<td style="text-align:right">{_tl(s["borc"]) if s["borc"] else "—"}</td>'
        f'<td style="text-align:right">{_tl(s["alacak"]) if s["alacak"] else "—"}</td></tr>'
        for s in f["satirlar"])
    denk = ('<span style="color:var(--accent-emerald)"><i class="fa-solid fa-check"></i> denk</span>'
            if f["denk"] else '<span style="color:var(--accent-rose)">DENK DEĞİL</span>')
    a = f["anahtar"]
    if f["durum"] == "taslak":
        butonlar = (f'<button class="btn" onclick="fisIslem(\'{a}\',\'onayla\')"><i class="fa-solid fa-check"></i> Onayla</button>'
                    f'<button class="btn-sec" onclick="fisIslem(\'{a}\',\'reddet\')"><i class="fa-solid fa-xmark"></i> Reddet</button>')
    elif f["durum"] == "onaylandi":
        butonlar = (f'<button class="btn" onclick="fisIslem(\'{a}\',\'gonder\')"><i class="fa-solid fa-paper-plane"></i> ERP\'ye Gönder</button>'
                    f'<button class="btn-sec" onclick="fisIslem(\'{a}\',\'geri\')"><i class="fa-solid fa-rotate-left"></i> Onayı Geri Al</button>')
    elif f["durum"] == "gonderildi":
        butonlar = f'<span style="color:var(--accent-emerald)"><i class="fa-solid fa-circle-check"></i> {f["zaman"]} ERP\'ye gönderildi</span>'
    else:  # reddedildi
        butonlar = f'<button class="btn-sec" onclick="fisIslem(\'{a}\',\'geri\')"><i class="fa-solid fa-rotate-left"></i> Taslağa Al</button>'

    return f"""
    <div class="filtre-bolum" data-grup="{f['durum']}" style="margin-top:16px;padding:18px;border:1px solid rgba(255,255,255,0.08);border-radius:16px;background:rgba(7,10,19,0.3);">
      <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
        <i class="fa-solid fa-file-lines" style="color:var(--accent-cyan)"></i>
        <strong>{f["baslik"]}</strong>
        <span class="badge {rozet}">{et}</span>
        <span style="margin-left:auto;color:var(--text-muted);font-size:12px;">{f["tarih"]}</span>
      </div>
      <p style="margin:6px 0 10px;color:var(--text-muted);font-size:13px;">{f["aciklama"]}</p>
      <div style="overflow-x:auto;"><table>
        <tr><th>Hesap</th><th>Açıklama</th><th style="text-align:right">Borç</th><th style="text-align:right">Alacak</th></tr>
        {satir}
        <tr style="font-weight:600;"><td colspan="2" style="text-align:right">Toplam ({denk})</td>
          <td style="text-align:right">{_tl(f["borc_toplam"])}</td>
          <td style="text-align:right">{_tl(f["alacak_toplam"])}</td></tr>
      </table></div>
      <div style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap;">{butonlar}</div>
    </div>"""


def _slot(rol, etiket, aciklama, ikon, var):
    iid = f"m6-{rol}"
    durum = ('<span style="color:var(--accent-emerald)"><i class="fa-solid fa-circle-check"></i> yüklendi · fiş üretildi</span>'
             if var else '<span style="color:var(--text-muted)">bekliyor</span>')
    return f"""
    <div style="flex:1;min-width:220px;text-align:center;padding:22px 16px;border:2px dashed rgba(255,255,255,0.1);border-radius:16px;background:rgba(7,10,19,0.3);">
      <i class="fa-solid {ikon}" style="font-size:28px;color:var(--accent-cyan);margin-bottom:10px;"></i>
      <p style="font-weight:600;margin-bottom:2px;">{etiket}</p>
      <p style="font-size:11px;color:var(--text-muted);margin-bottom:8px;">{aciklama}</p>
      <p style="margin-bottom:12px;font-size:12px;">{durum}</p>
      <input type="file" id="{iid}" accept=".xls,.xlsx,.xlsm" style="display:none" onchange="yukleDosya('m6_fis','{iid}','{rol}')">
      <button class="btn-sec" onclick="document.getElementById('{iid}').click()"><i class="fa-solid fa-upload"></i> {'Değiştir' if var else 'Yükle'}</button>
    </div>"""


def _bekleyen_veri(slotlar=None):
    s = slotlar or {}
    kart = (_slot("demirbas", "Amortisman", "Sabit kıymet / demirbaş listesi (maliyet + oran/ömür).", "fa-building", s.get("demirbas")) +
            _slot("dovizli", "Kur Farkı Değerleme", "Dövizli hesap bakiyeleri + dönem sonu kuru.", "fa-money-bill-transfer", s.get("dovizli")) +
            _slot("senet", "Reeskont", "Vadeli senet/çek listesi (tutar + vade).", "fa-file-contract", s.get("senet")))
    return ('<div style="margin-top:22px;"><h4 style="font-size:14px;margin-bottom:8px;color:var(--text-muted);">'
            '<i class="fa-solid fa-cloud-arrow-up"></i> Ek Fiş Üreticiler — Liste Yükleyin</h4>'
            f'<div style="display:flex;gap:12px;flex-wrap:wrap;">{kart}</div>'
            '<p id="yukleme-durum" style="margin-top:10px;font-size:12px;color:var(--accent-cyan);"></p></div>')


def panel_html(sonuc):
    ust = _baslik()
    fisler = sonuc.get("fisler", [])
    if not fisler:
        return (ust + '<div class="notif-pill"><div class="circle-icon-badge" style="background:var(--accent-gold)"></div>'
                '<span>Henüz üretilebilir fiş yok. Mizan (KDV mahsup) ve banka ekstresi (komisyon) '
                'yükledikçe fişler burada belirir.</span></div>' + _bekleyen_veri(sonuc.get("slotlar")))

    n_taslak = sum(1 for f in fisler if f["durum"] == "taslak")
    n_onay = sum(1 for f in fisler if f["durum"] == "onaylandi")
    n_gond = sum(1 for f in fisler if f["durum"] == "gonderildi")
    stat = f"""
    <div class="stats-grid" style="margin-bottom:8px;">
      <div class="stat-card filtre-kart aktif" data-hedef="all" onclick="bulguFiltrele('all', this)"><div class="stat-header"><span>Üretilen Fiş</span><i class="fa-solid fa-file-lines" style="color:var(--accent-cyan)"></i></div><div class="stat-val">{len(fisler)}</div><div class="stat-desc"><span class="ipucu">Tümünü göster</span></div></div>
      <div class="stat-card gold filtre-kart" data-hedef="taslak" onclick="bulguFiltrele('taslak', this)"><div class="stat-header"><span>Onay Bekleyen</span><i class="fa-solid fa-hourglass-half" style="color:var(--accent-gold)"></i></div><div class="stat-val">{n_taslak}</div><div class="stat-desc"><span class="ipucu">Görmek için tıkla</span></div></div>
      <div class="stat-card emerald filtre-kart" data-hedef="onaylandi" onclick="bulguFiltrele('onaylandi', this)"><div class="stat-header"><span>Onaylandı</span><i class="fa-solid fa-check" style="color:var(--accent-emerald)"></i></div><div class="stat-val">{n_onay}</div><div class="stat-desc"><span class="ipucu">Görmek için tıkla</span></div></div>
      <div class="stat-card emerald filtre-kart" data-hedef="gonderildi" onclick="bulguFiltrele('gonderildi', this)"><div class="stat-header"><span>ERP'ye Gönderildi</span><i class="fa-solid fa-paper-plane" style="color:var(--accent-emerald)"></i></div><div class="stat-val">{n_gond}</div><div class="stat-desc"><span class="ipucu">Görmek için tıkla</span></div></div>
    </div>"""
    kartlar = "".join(_fis_karti(f) for f in fisler)
    return ust + stat + kartlar + _bekleyen_veri(sonuc.get("slotlar"))


kaydet(Modul("m6_fis", AD, "fa-stamp", 8, calistir, panel_html))
