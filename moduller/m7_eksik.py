# -*- coding: utf-8 -*-
"""M7 - Eksik Belge Avcisi.

En yuksek 'vay, bunu unutmusum' etkisi. Uc kaynaktan beslenir:
  1) Duzenli Gider Takibi  -> M2 mizanindaki aylik hareketlerden (kira/elektrik/
     telefon/danismanlik gecen aylar vardi, bu ay yok).
  2) GIB'de Var Defterde Yok -> M4'e yuklenen GIB e-Fatura listesinden (caprez besleme).
  3) Tahakkuk Eksigi -> ileride (SGK/vergi tahakkuk verisi gerekli).
"""
from core.moduller import Modul, kaydet
from core import depo, mizan_oku, cari_oku, kdv_analiz, eksik_analiz

AD = "Eksik Belge Avcısı"
ACIKLAMA = "Olması gereken ama bu dönem gelmemiş belgeleri yakalar — en yüksek 'vay, bunu unutmuşum' etkisi."


def calistir(musteri_id, donem):
    sonuc = {"hazir": False}

    # 1) Duzenli gider + SGK/vergi tahakkuk eksigi (ikisi de mizandan)
    mizan_yol = depo.yuklenen_bul(musteri_id, donem, "m2_mizan")
    dg = th = None
    if mizan_yol:
        try:
            mizan = mizan_oku.oku(mizan_yol)
            dg = eksik_analiz.duzenli_gider(mizan)
            th = eksik_analiz.tahakkuk_eksigi(mizan)
            sonuc["hazir"] = True
        except Exception as e:
            dg = th = {"hata": str(e)}
    sonuc["duzenli"] = dg
    sonuc["tahakkuk"] = th
    sonuc["mizan_var"] = bool(mizan_yol)

    # 2) GIB eksik (M4'ten besle)
    gib_yol = depo.yuklenen_bul(musteri_id, donem, "m4_gib_kdv", rol="gib")
    defter_yol = depo.yuklenen_bul(musteri_id, donem, "m4_gib_kdv", rol="defter")
    gib = None
    if gib_yol and defter_yol:
        try:
            gib = kdv_analiz.gib_karsilastir(cari_oku.oku(gib_yol), cari_oku.oku(defter_yol))
            sonuc["hazir"] = True
        except Exception as e:
            gib = {"hata": str(e)}
    sonuc["gib"] = gib

    # durum / bulgu
    bulgu = 0
    if dg and dg.get("yeterli_veri"):
        bulgu += len(dg.get("eksikler", []))
    if th and th.get("yeterli_veri"):
        bulgu += len(th.get("eksikler", []))
    if gib and not gib.get("hata"):
        bulgu += len(gib.get("eksik_defter", []))
    depo.modul_durum_guncelle(musteri_id, donem, "m7_eksik",
                              durum=("uyari" if bulgu else ("tamam" if sonuc["hazir"] else "bekliyor")),
                              ilerleme=(100 if sonuc["hazir"] else 0),
                              bulgu_sayisi=bulgu)
    return sonuc


# --------------------------------------------------------------------------- #
def _tl(v):
    try:
        return f"{v:,.0f} TL".replace(",", ".")
    except Exception:
        return "—"


def _baslik():
    return f"""
    <div class="panel-header">
      <div class="panel-title"><h2><i class="fa-solid fa-magnifying-glass"></i> {AD}</h2>
      <p>{ACIKLAMA}</p></div>
      <div class="panel-header-icon"><i class="fa-solid fa-magnifying-glass"></i></div>
    </div>"""


def _bolum_duzenli(sonuc):
    h3 = ('<h3 style="font-size:17px;margin:8px 0 12px;"><i class="fa-solid fa-repeat" '
          'style="color:var(--accent-cyan)"></i> Düzenli Gider Takibi</h3>')
    if not sonuc.get("mizan_var"):
        return (h3 + '<div class="notif-pill"><div class="circle-icon-badge" style="background:var(--accent-gold)"></div>'
                '<span>Önce <strong>Mizan & Anomali</strong> sekmesinden mizanı yükleyin; düzenli giderler '
                'aylık hareketlerden otomatik taranır.</span></div>')
    dg = sonuc.get("duzenli") or {}
    if dg.get("hata"):
        return h3 + f'<p style="color:var(--accent-rose)">Mizan okunamadı: {dg["hata"]}</p>'
    if not dg.get("yeterli_veri"):
        return (h3 + '<div class="notif-pill"><div class="circle-icon-badge"></div>'
                '<span>Düzenli gider analizi için en az 3 aylık hareket içeren kümüle mizan gerekir.</span></div>')

    eksik = dg["eksikler"]
    ozet = (f'<p style="margin-bottom:12px;font-size:13px;color:var(--text-muted)">'
            f'<strong>{dg["kapanis"].title()}</strong> ayı, önceki {dg["gecmis_ay"]} ayla karşılaştırıldı. '
            f'Düzenli hareket eden ama bu ay durağan kalan hesaplar aşağıda.</p>')
    if not eksik:
        return (h3 + ozet + '<div class="notif-pill"><div class="circle-icon-badge" style="background:var(--accent-emerald)"></div>'
                '<span>Düzenli giderlerin tamamı bu dönem de işlenmiş görünüyor — eksik yok.</span></div>')

    sat = "".join(
        f'<tr><td><span class="badge neutral">{e["ana"]}</span></td><td>{e["ad"] or "—"}</td>'
        f'<td style="text-align:center">{e["gecmis_ay"]}/{e["toplam_ay"]} ay</td>'
        f'<td style="text-align:right">{_tl(e["beklenen"])}</td>'
        f'<td style="text-align:right"><span style="color:var(--accent-rose)">{_tl(e["bu_ay"])}</span></td>'
        f'<td><span class="badge warn"><i class="fa-solid fa-triangle-exclamation"></i> bu ay yok</span></td></tr>'
        for e in eksik)
    tablo = (f'<div style="overflow-x:auto"><table>'
             f'<tr><th>Hesap</th><th>Açıklama</th><th style="text-align:center">Geçmiş</th>'
             f'<th style="text-align:right">Beklenen (aylık ort.)</th><th style="text-align:right">Bu Ay</th>'
             f'<th>Durum</th></tr>{sat}</table></div>')
    return h3 + ozet + tablo


def _bolum_gib(sonuc):
    h3 = ('<h3 style="font-size:17px;margin:24px 0 12px;"><i class="fa-solid fa-file-circle-xmark" '
          'style="color:var(--accent-rose)"></i> GİB\'de Var, Defterde Yok</h3>')
    gib = sonuc.get("gib")
    if not gib:
        return (h3 + '<div class="notif-pill"><div class="circle-icon-badge"></div>'
                '<span>Bu bölüm <strong>e-Fatura & KDV Otomasyonu</strong> sekmesinden beslenir. '
                'Oradaki GİB listesi + defter alış dosyalarını yükleyince işlenmemiş alış faturaları burada da listelenir.</span></div>')
    if gib.get("hata"):
        return h3 + f'<p style="color:var(--accent-rose)">Okuma hatası: {gib["hata"]}</p>'
    eksik = gib.get("eksik_defter", [])
    if not eksik:
        return (h3 + '<div class="notif-pill"><div class="circle-icon-badge" style="background:var(--accent-emerald)"></div>'
                '<span>GİB e-Fatura listesindeki tüm alışlar deftere işlenmiş.</span></div>')
    sat = "".join(f'<li style="margin:5px 0;color:var(--text-muted);font-size:13px;">{k["ac"]}</li>' for k in eksik)
    return (h3 + f'<p style="margin-bottom:8px;font-size:13px;color:var(--text-muted)">İşlenmemiş alış = kaybolan indirilecek KDV. '
            f'Tahmini kayıp KDV: <strong style="color:var(--accent-rose)">{_tl(gib.get("tahmini_kayip_kdv",0))}</strong></p>'
            f'<ul style="padding-left:18px;margin:0;">{sat}</ul>')


def _bolum_tahakkuk(sonuc):
    h3 = ('<h3 style="font-size:17px;margin:24px 0 12px;"><i class="fa-solid fa-clock" '
          'style="color:var(--accent-gold)"></i> SGK / Vergi Tahakkuk Eksiği</h3>')
    if not sonuc.get("mizan_var"):
        return (h3 + '<div class="notif-pill"><div class="circle-icon-badge" style="background:var(--accent-gold)"></div>'
                '<span>Mizan yüklenince 361 SGK, 360 gelir stopajı/damga ve 368 tahakkuklarının '
                'bu dönem işlenip işlenmediği aylık hareketlerden otomatik kontrol edilir.</span></div>')
    th = sonuc.get("tahakkuk") or {}
    if th.get("hata"):
        return h3 + f'<p style="color:var(--accent-rose)">Mizan okunamadı: {th["hata"]}</p>'
    if not th.get("yeterli_veri"):
        return (h3 + '<div class="notif-pill"><div class="circle-icon-badge"></div>'
                '<span>Tahakkuk kontrolü için en az 3 aylık hareket içeren kümüle mizan gerekir.</span></div>')
    eksik = th["eksikler"]
    if not eksik:
        return (h3 + '<div class="notif-pill"><div class="circle-icon-badge" style="background:var(--accent-emerald)"></div>'
                '<span>SGK ve vergi tahakkukları bu dönem de düzenli işlenmiş — eksik görünmüyor.</span></div>')
    op = ('<strong style="color:var(--accent-rose)">Operasyon bu ay sürüyor</strong> (gider hareketi var); '
          'buna rağmen aşağıdaki tahakkuklar durmuş — fişi unutulmuş olabilir.'
          if eksik[0].get("op_aktif") else
          'Aşağıdaki yükümlülükler önceki aylarda düzenliyken bu dönem durmuş.')
    ozet = (f'<p style="margin-bottom:12px;font-size:13px;color:var(--text-muted)">'
            f'<strong>{th["kapanis"].title()}</strong> ayı, önceki {th["gecmis_ay"]} ayla karşılaştırıldı. {op}</p>')
    sat = "".join(
        f'<tr><td><span class="badge neutral">{e["ana"]}</span></td><td>{e["tur"] or e["ad"]}</td>'
        f'<td style="text-align:center">{e["gecmis_ay"]}/{e["toplam_ay"]} ay</td>'
        f'<td style="text-align:right">{_tl(e["beklenen"])}</td>'
        f'<td style="text-align:right"><span style="color:var(--accent-rose)">{_tl(e["bu_ay"])}</span></td>'
        f'<td><span class="badge warn"><i class="fa-solid fa-triangle-exclamation"></i> tahakkuk yok</span></td></tr>'
        for e in eksik)
    tablo = (f'<div style="overflow-x:auto"><table>'
             f'<tr><th>Hesap</th><th>Yükümlülük</th><th style="text-align:center">Geçmiş</th>'
             f'<th style="text-align:right">Beklenen (aylık ort.)</th><th style="text-align:right">Bu Ay</th>'
             f'<th>Durum</th></tr>{sat}</table></div>')
    uyari = ('<div class="notif-pill" style="margin-top:12px;"><i class="fa-solid fa-circle-info" '
             'style="color:var(--accent-cyan)"></i><span>Bu bir <strong>iç tutarlılık uyarısıdır</strong>; '
             'kayıt önerilmez. Beyanname öncesi tahakkuk fişlerini kontrol edin — son onay sizde.</span></div>')
    return h3 + ozet + tablo + uyari


def panel_html(sonuc):
    ust = _baslik()
    dg = sonuc.get("duzenli") or {}
    th = sonuc.get("tahakkuk") or {}
    gib = sonuc.get("gib") or {}
    n_dg = len(dg.get("eksikler", [])) if dg.get("yeterli_veri") else 0
    n_th = len(th.get("eksikler", [])) if th.get("yeterli_veri") else 0
    n_gib = len(gib.get("eksik_defter", [])) if gib and not gib.get("hata") else 0
    toplam_tutar = dg.get("toplam_beklenen", 0) + th.get("toplam_beklenen", 0)
    stat = f"""
    <div class="stats-grid" style="margin-bottom:8px;">
      <div class="stat-card gold filtre-kart aktif" data-hedef="all" onclick="bulguFiltrele('all', this)"><div class="stat-header"><span>Tahmini Eksik Tutar</span><i class="fa-solid fa-sack-dollar" style="color:var(--accent-gold)"></i></div><div class="stat-val" style="font-size:20px">{_tl(toplam_tutar)}</div><div class="stat-desc"><span class="ipucu">Tümünü göster</span></div></div>
      <div class="stat-card rose filtre-kart" data-hedef="duzenli" onclick="bulguFiltrele('duzenli', this)"><div class="stat-header"><span>Eksik Düzenli Gider</span><i class="fa-solid fa-repeat" style="color:var(--accent-rose)"></i></div><div class="stat-val">{n_dg}</div><div class="stat-desc"><span class="ipucu">Görmek için tıkla</span></div></div>
      <div class="stat-card gold filtre-kart" data-hedef="tahakkuk" onclick="bulguFiltrele('tahakkuk', this)"><div class="stat-header"><span>SGK/Vergi Tahakkuk Eksiği</span><i class="fa-solid fa-clock" style="color:var(--accent-gold)"></i></div><div class="stat-val">{n_th}</div><div class="stat-desc"><span class="ipucu">Görmek için tıkla</span></div></div>
      <div class="stat-card filtre-kart" data-hedef="gib" onclick="bulguFiltrele('gib', this)"><div class="stat-header"><span>GİB'de Var Defterde Yok</span><i class="fa-solid fa-file-circle-xmark" style="color:var(--accent-cyan)"></i></div><div class="stat-val">{n_gib}</div><div class="stat-desc"><span class="ipucu">Görmek için tıkla</span></div></div>
    </div>"""
    return (ust + stat +
            f'<div class="filtre-bolum" data-grup="duzenli">{_bolum_duzenli(sonuc)}</div>' +
            f'<div class="filtre-bolum" data-grup="tahakkuk">{_bolum_tahakkuk(sonuc)}</div>' +
            f'<div class="filtre-bolum" data-grup="gib">{_bolum_gib(sonuc)}</div>')


kaydet(Modul("m7_eksik", AD, "fa-magnifying-glass", 11, calistir, panel_html))
