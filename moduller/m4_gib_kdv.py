# -*- coding: utf-8 -*-
"""M4 - e-Fatura & KDV Otomasyonu (Asama 3).

Iki bolum tek panelde:
  1) KDV Pozisyonu & Beyanname Taslagi  -> M2'de yuklenen mizandan otomatik.
  2) GIB e-Fatura Karsilastirmasi        -> GIB listesi + defter alis (opsiyonel yukleme).
"""
from core.moduller import Modul, kaydet
from core import depo, mizan_oku, cari_oku, kdv_analiz, varlik_oku

AD = "e-Fatura & KDV Otomasyonu"
ACIKLAMA = "Mizandan KDV pozisyonu + beyanname taslağı; GİB listesiyle işlenmemiş fatura avı."


def calistir(musteri_id, donem):
    sonuc = {"hazir": True}

    # --- 1) KDV pozisyonu (mizandan) ---
    mizan_yol = depo.yuklenen_bul(musteri_id, donem, "m2_mizan")
    kdv = None
    if mizan_yol:
        try:
            mizan = mizan_oku.oku(mizan_yol)
            kdv = kdv_analiz.mizandan_kdv(mizan)
        except Exception as e:
            kdv = {"hata": str(e)}
    sonuc["mizan_var"] = bool(mizan_yol)
    sonuc["kdv"] = kdv

    # --- 2) GIB karsilastirmasi (opsiyonel) ---
    gib_yol = depo.yuklenen_bul(musteri_id, donem, "m4_gib_kdv", rol="gib")
    defter_yol = depo.yuklenen_bul(musteri_id, donem, "m4_gib_kdv", rol="defter")
    sonuc["gib_dosya"] = bool(gib_yol)
    sonuc["defter_dosya"] = bool(defter_yol)
    gib = None
    if gib_yol and defter_yol:
        try:
            gib_k = cari_oku.oku(gib_yol)
            defter_k = cari_oku.oku(defter_yol)
            gib = kdv_analiz.gib_karsilastir(gib_k, defter_k)
        except Exception as e:
            gib = {"hata": str(e)}
    sonuc["gib"] = gib

    # --- 3) KDV Tevkifati (opsiyonel yukleme) ---
    tev_yol = depo.yuklenen_bul(musteri_id, donem, "m4_gib_kdv", rol="tevkifat")
    sonuc["tevkifat_dosya"] = bool(tev_yol)
    tev = None
    if tev_yol:
        try:
            tev = kdv_analiz.tevkifat(varlik_oku.tevkifat_oku(tev_yol))
        except Exception as e:
            tev = {"hata": str(e)}
    sonuc["tevkifat"] = tev

    # --- 4) KDV matrah/oran tutarlilik denetimi (opsiyonel yukleme) ---
    matrah_yol = depo.yuklenen_bul(musteri_id, donem, "m4_gib_kdv", rol="kdv_matrah")
    sonuc["matrah_dosya"] = bool(matrah_yol)
    matrah = None
    if matrah_yol:
        try:
            kalemler = varlik_oku.kdv_matrah_oku(matrah_yol)
            matrah = kdv_analiz.matrah_oran_denetim(kalemler, kdv_pozisyon=kdv)
        except Exception as e:
            matrah = {"hata": str(e)}
    sonuc["matrah_denetim"] = matrah
    sonuc["_mid"], sonuc["_donem"] = musteri_id, donem

    # --- durum/bulgu ---
    bulgu = 0
    if kdv and not kdv.get("hata"):
        bulgu += len(kdv.get("uyarilar", []))
    if gib and not gib.get("hata"):
        bulgu += gib.get("sorunlu", 0)
    if tev and not tev.get("hata"):
        bulgu += len(tev.get("uyarilar", []))
    if matrah and not matrah.get("hata"):
        bulgu += matrah.get("bulgu", 0)

    if not mizan_yol and not (gib_yol and defter_yol):
        depo.modul_durum_guncelle(musteri_id, donem, "m4_gib_kdv",
                                  durum="bekliyor", ilerleme=0, bulgu_sayisi=0)
    else:
        depo.modul_durum_guncelle(musteri_id, donem, "m4_gib_kdv",
                                  durum=("tamam" if bulgu == 0 else "uyari"),
                                  ilerleme=(100 if bulgu == 0 else 60),
                                  bulgu_sayisi=bulgu)
    return sonuc


# --------------------------------------------------------------------------- #
def _tl(v):
    return f"{v:,.2f} TL".replace(",", "X").replace(".", ",").replace("X", ".")


def _baslik():
    return f"""
    <div class="panel-header">
      <div class="panel-title"><h2><i class="fa-solid fa-building-columns"></i> {AD}</h2>
      <p>{ACIKLAMA}</p></div>
      <div class="panel-header-icon"><i class="fa-solid fa-building-columns"></i></div>
    </div>"""


def _bolum_kdv(sonuc):
    h3 = ('<h3 style="font-family:\'Outfit\',sans-serif;font-size:17px;margin:8px 0 14px;">'
          '<i class="fa-solid fa-receipt" style="color:var(--accent-cyan)"></i> '
          'KDV Pozisyonu &amp; Beyanname Taslağı</h3>')
    if not sonuc.get("mizan_var"):
        return (h3 + '<div class="notif-pill"><div class="circle-icon-badge" style="background:var(--accent-gold)"></div>'
                '<span>KDV taslağı için önce <strong>Mizan Sağlık Taraması</strong> sekmesinden mizanı yükleyin. '
                'KDV pozisyonu aynı mizandan otomatik hesaplanır.</span></div>')
    kdv = sonuc.get("kdv") or {}
    if kdv.get("hata"):
        return h3 + f'<p style="color:var(--accent-rose)">Mizan okunamadı: {kdv["hata"]}</p>'
    if not kdv.get("var"):
        u = kdv.get("uyarilar", [{}])
        return h3 + f'<div class="notif-pill"><div class="circle-icon-badge" style="background:var(--accent-gold)"></div><span>{u[0].get("ac","KDV hesapları bulunamadı.")}</span></div>'

    sonuc_renk = "var(--accent-rose)" if kdv["sonuc_tip"] == "ODENECEK" else "var(--accent-emerald)"
    sonuc_et = "Ödenecek KDV" if kdv["sonuc_tip"] == "ODENECEK" else "Sonraki Döneme Devreden KDV"
    stat = f"""
    <div class="stats-grid" style="margin-bottom:8px;">
      <div class="stat-card"><div class="stat-header"><span>Hesaplanan KDV (391)</span><i class="fa-solid fa-arrow-up" style="color:var(--accent-rose)"></i></div><div class="stat-val" style="font-size:20px">{_tl(kdv['hesaplanan'])}</div><div class="stat-desc">{kdv['ay'] or '—'} dönemi</div></div>
      <div class="stat-card emerald"><div class="stat-header"><span>İndirilecek KDV (191)</span><i class="fa-solid fa-arrow-down" style="color:var(--accent-emerald)"></i></div><div class="stat-val" style="font-size:20px">{_tl(kdv['indirilecek'])}</div></div>
      <div class="stat-card gold"><div class="stat-header"><span>Devreden KDV (190)</span><i class="fa-solid fa-rotate-left" style="color:var(--accent-gold)"></i></div><div class="stat-val" style="font-size:20px">{_tl(kdv['devreden_onceki'])}</div><div class="stat-desc">önceki dönemden</div></div>
      <div class="stat-card"><div class="stat-header"><span>{sonuc_et}</span><i class="fa-solid fa-file-invoice-dollar" style="color:{sonuc_renk}"></i></div><div class="stat-val" style="font-size:20px;color:{sonuc_renk}">{_tl(kdv['sonuc_tutar'])}</div></div>
    </div>
    <div style="overflow-x:auto;margin-top:6px;"><table>
      <tr><th>KDV Beyanname Taslağı ({kdv['ay'] or '—'})</th><th style="text-align:right">Tutar</th></tr>
      <tr><td>Hesaplanan KDV (391)</td><td style="text-align:right">{_tl(kdv['hesaplanan'])}</td></tr>
      <tr><td>İndirilecek KDV (191)</td><td style="text-align:right">{_tl(kdv['indirilecek'])}</td></tr>
      <tr><td>Önceki Dönemden Devreden KDV (190)</td><td style="text-align:right">{_tl(kdv['devreden_onceki'])}</td></tr>
      <tr><td><strong>{sonuc_et}</strong></td><td style="text-align:right;color:{sonuc_renk}"><strong>{_tl(kdv['sonuc_tutar'])}</strong></td></tr>
    </table></div>
    <p style="margin-top:8px;font-size:12px;color:var(--text-muted);">Taslak mizandaki hesap toplamlarından üretildi; matrah satırları (KDV-1) için fatura detayı gerekir. Beyan öncesi kontrol amaçlıdır.</p>"""

    devir = _devir_teyit(kdv)

    uyari = ""
    # devir uyarisi (tip=='devir') zaten teyit kutusunda gosterildi; listede tekrarlama
    digerleri = [u for u in kdv.get("uyarilar", []) if u.get("tip") != "devir"]
    if digerleri:
        sat = "".join(f'<li style="margin:6px 0;color:var(--text-muted);">{u["ac"]}</li>' for u in digerleri)
        uyari = (f'<div style="margin-top:16px;"><h4 style="font-size:14px;margin-bottom:6px;">'
                 f'<i class="fa-solid fa-triangle-exclamation" style="color:var(--accent-gold)"></i> '
                 f'KDV Kontrol Uyarıları <span class="badge warn">{len(digerleri)}</span></h4>'
                 f'<ul style="padding-left:18px;margin:0;">{sat}</ul></div>')
    return h3 + stat + devir + uyari


def _devir_teyit(kdv):
    """190 Devreden KDV yasam dongusu teyidi (190/191/391 zinciri)."""
    durum = kdv.get("devir_durum")
    if not durum or durum == "yok":
        return ""
    renk, ikon, etiket = {
        "uygun":    ("var(--accent-emerald)", "fa-circle-check",        "190 Devreden KDV — Doğru"),
        "bekliyor": ("var(--accent-cyan)",    "fa-clock",               "190 Devreden KDV — Mahsup Bekliyor"),
        "ac":       ("var(--accent-gold)",    "fa-circle-plus",         "190 Devreden KDV — Hesap Açılmalı"),
        "uyumsuz":  ("var(--accent-rose)",    "fa-triangle-exclamation","190 Devreden KDV — Uyumsuz"),
    }.get(durum, ("var(--accent-gold)", "fa-circle-info", "190 Devreden KDV"))
    zincir = (f'<div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:10px 0 2px;font-size:13px;">'
              f'<span class="badge neutral">önceki devreden {_tl(kdv["devreden_onceki"])}</span>'
              f'<span style="color:var(--text-muted)">+</span>'
              f'<span class="badge neutral">indirilecek {_tl(kdv["indirilecek"])}</span>'
              f'<span style="color:var(--text-muted)">−</span>'
              f'<span class="badge neutral">hesaplanan {_tl(kdv["hesaplanan"])}</span>'
              f'<span style="color:var(--text-muted)">=</span>'
              f'<span class="badge" style="background:{renk};color:#0b0e16;">'
              f'sonraki döneme devreden {_tl(kdv["beklenen_devreden"])}</span></div>')
    return (f'<div style="margin-top:16px;padding:14px 16px;border:1px solid rgba(255,255,255,0.08);'
            f'border-left:3px solid {renk};border-radius:12px;background:rgba(7,10,19,0.3);">'
            f'<h4 style="font-size:14px;margin:0 0 4px;"><i class="fa-solid {ikon}" style="color:{renk}"></i> {etiket}</h4>'
            f'{zincir}'
            f'<p style="margin:8px 0 0;font-size:13px;color:var(--text-muted);">{kdv.get("devir_ac","")}</p></div>')


def _gib_slot(rol, etiket, var):
    iid = f"gib-{rol}"
    durum = ('<span style="color:var(--accent-emerald)"><i class="fa-solid fa-circle-check"></i> yüklendi</span>'
             if var else '<span style="color:var(--text-muted)">bekliyor</span>')
    return f"""
    <div style="flex:1;min-width:220px;text-align:center;padding:22px 16px;border:2px dashed rgba(255,255,255,0.1);border-radius:14px;background:rgba(7,10,19,0.3);">
      <i class="fa-solid fa-file-excel" style="font-size:28px;color:var(--accent-cyan);margin-bottom:10px;"></i>
      <p style="font-weight:600;margin-bottom:4px;">{etiket}</p>
      <p style="margin-bottom:12px;font-size:12px;">{durum}</p>
      <input type="file" id="{iid}" accept=".xls,.xlsx,.xlsm" style="display:none" onchange="yukleDosya('m4_gib_kdv','{iid}','{rol}')">
      <button class="btn-sec" onclick="document.getElementById('{iid}').click()"><i class="fa-solid fa-upload"></i> {'Değiştir' if var else 'Yükle'}</button>
    </div>"""


def _bolum_gib(sonuc):
    h3 = ('<h3 style="font-family:\'Outfit\',sans-serif;font-size:17px;margin:26px 0 14px;">'
          '<i class="fa-solid fa-magnifying-glass-dollar" style="color:var(--accent-cyan)"></i> '
          'GİB e-Fatura Karşılaştırması</h3>'
          '<p style="margin-bottom:12px;font-size:13px;color:var(--text-muted);">GİB e-Fatura listesi ile defter alış faturalarını karşılaştırır; işlenmemiş alışları (kaybolan indirilecek KDV) yakalar.</p>')
    slotlar = ('<div style="display:flex;gap:14px;flex-wrap:wrap;">'
               + _gib_slot("gib", "GİB e-Fatura Listesi", sonuc.get("gib_dosya"))
               + _gib_slot("defter", "Defter Alış Faturaları", sonuc.get("defter_dosya"))
               + '</div><p id="yukleme-durum" style="margin-top:10px;font-size:12px;color:var(--accent-cyan);"></p>')
    gib = sonuc.get("gib")
    if not gib:
        return h3 + slotlar
    if gib.get("hata"):
        return h3 + slotlar + f'<p style="color:var(--accent-rose);margin-top:10px;">Okuma hatası: {gib["hata"]}</p>'

    stat = f"""
    <div class="stats-grid" style="margin:14px 0 8px;">
      <div class="stat-card emerald filtre-kart aktif" data-hedef="all" onclick="bulguFiltrele('all', this)"><div class="stat-header"><span>Eşleşen</span><i class="fa-solid fa-circle-check" style="color:var(--accent-emerald)"></i></div><div class="stat-val">{gib['eslesen']}</div><div class="stat-desc"><span class="ipucu">Tümünü göster</span></div></div>
      <div class="stat-card rose filtre-kart" data-hedef="eksik" onclick="bulguFiltrele('eksik', this)"><div class="stat-header"><span>Defterde Yok</span><i class="fa-solid fa-file-circle-xmark" style="color:var(--accent-rose)"></i></div><div class="stat-val">{len(gib['eksik_defter'])}</div><div class="stat-desc"><span class="ipucu">Görmek için tıkla</span></div></div>
      <div class="stat-card gold filtre-kart" data-hedef="tutar" onclick="bulguFiltrele('tutar', this)"><div class="stat-header"><span>Tutar Farkı</span><i class="fa-solid fa-scale-unbalanced" style="color:var(--accent-gold)"></i></div><div class="stat-val">{len(gib['tutar_farki'])}</div><div class="stat-desc"><span class="ipucu">Görmek için tıkla</span></div></div>
      <div class="stat-card filtre-kart" data-hedef="fazla" onclick="bulguFiltrele('fazla', this)"><div class="stat-header"><span>Tahmini Kayıp KDV</span><i class="fa-solid fa-sack-dollar" style="color:var(--accent-rose)"></i></div><div class="stat-val" style="font-size:18px">{_tl(gib['tahmini_kayip_kdv'])}</div><div class="stat-desc"><span class="ipucu">GİB fazlası için tıkla</span></div></div>
    </div>"""

    def liste(grup, baslik, ikon, renk, kalemler):
        if kalemler:
            sat = "".join(f'<li style="margin:5px 0;color:var(--text-muted);font-size:13px;">{k["ac"]}</li>' for k in kalemler)
            govde = f'<ul style="padding-left:18px;margin:0;">{sat}</ul>'
            rozet = "warn"
        else:
            govde = ('<div class="notif-pill" style="margin-top:8px;"><div class="circle-icon-badge"></div>'
                     '<span>Bu kategoride bulgu yok.</span></div>')
            rozet = "success"
        return (f'<div class="filtre-bolum" data-grup="{grup}" style="margin-top:14px;"><h4 style="font-size:14px;margin-bottom:6px;">'
                f'<i class="fa-solid {ikon}" style="color:{renk}"></i> {baslik} '
                f'<span class="badge {rozet}">{len(kalemler)}</span></h4>{govde}</div>')

    blok = (liste("eksik", "GİB'de Var, Defterde Yok (işlenmemiş alış)", "fa-file-circle-xmark", "var(--accent-rose)", gib["eksik_defter"])
            + liste("tutar", "Tutar Farkı (kayıt hatası)", "fa-scale-unbalanced", "var(--accent-gold)", gib["tutar_farki"])
            + liste("fazla", "Defterde Var, GİB'de Yok (iptal/hayali şüphesi)", "fa-circle-question", "var(--text-muted)", gib["fazla_defter"]))

    earsiv = gib.get("earsiv_defter") or []
    if earsiv:
        sat = "".join(f'<li style="margin:5px 0;color:var(--text-muted);font-size:13px;">{k["ac"]}</li>' for k in earsiv)
        blok += (f'<div class="filtre-bolum" data-grup="earsiv" style="margin-top:14px;"><h4 style="font-size:14px;margin-bottom:6px;">'
                 f'<i class="fa-solid fa-file-shield" style="color:var(--accent-cyan)"></i> '
                 f'e-Arşiv / Kağıt Fatura (beklenen — anomali değil) '
                 f'<span class="badge">{len(earsiv)}</span></h4>'
                 f'<ul style="padding-left:18px;margin:0;">{sat}</ul>'
                 f'<p style="margin-top:6px;font-size:12px;color:var(--text-muted);">Belge tipi e-Arşiv/kağıt '
                 f'olduğu için GİB e-Fatura listesinde görünmezler; "Defterde Var, GİB\'de Yok" anomali sayısından çıkarıldı.</p></div>')
    return h3 + slotlar + stat + blok


def _bolum_tevkifat(sonuc):
    h3 = ('<h3 style="font-family:\'Outfit\',sans-serif;font-size:17px;margin:26px 0 14px;">'
          '<i class="fa-solid fa-scissors" style="color:var(--accent-cyan)"></i> '
          'KDV Tevkifatı (2 No.lu Beyanname Kontrolü)</h3>'
          '<p style="margin-bottom:12px;font-size:13px;color:var(--text-muted);">Kısmi tevkifata tabi '
          'alış hizmetlerini yükleyin; alıcı sorumlu sıfatıyla tevkif edilen KDV (→ 360 Ödenecek Vergi/Fonlar, '
          '2 No.lu KDV beyannamesi) ile satıcıya ödenen indirilecek KDV ayrımı hesaplanır. '
          'Oran boş bırakılan kalemlerde standart GİB oran tablosu uygulanır.</p>')
    slot = ('<div style="display:flex;gap:14px;flex-wrap:wrap;">'
            + _gib_slot("tevkifat", "Tevkifat Listesi (işlem türü + matrah + oran)", sonuc.get("tevkifat_dosya"))
            + '</div>')
    tev = sonuc.get("tevkifat")
    if not tev:
        return h3 + slot
    if tev.get("hata"):
        return h3 + slot + f'<p style="color:var(--accent-rose);margin-top:10px;">Okuma hatası: {tev["hata"]}</p>'

    stat = f"""
    <div class="stats-grid" style="margin:14px 0 8px;">
      <div class="stat-card"><div class="stat-header"><span>Toplam Matrah</span><i class="fa-solid fa-layer-group" style="color:var(--accent-cyan)"></i></div><div class="stat-val" style="font-size:18px">{_tl(tev['toplam_matrah'])}</div><div class="stat-desc">{tev['kalem_sayisi']} kalem</div></div>
      <div class="stat-card"><div class="stat-header"><span>Hesaplanan KDV</span><i class="fa-solid fa-percent" style="color:var(--accent-gold)"></i></div><div class="stat-val" style="font-size:18px">{_tl(tev['toplam_kdv'])}</div></div>
      <div class="stat-card rose"><div class="stat-header"><span>Tevkif Edilen → 360</span><i class="fa-solid fa-scissors" style="color:var(--accent-rose)"></i></div><div class="stat-val" style="font-size:18px;color:var(--accent-rose)">{_tl(tev['toplam_tevkif'])}</div><div class="stat-desc">2 No.lu KDV beyannamesi</div></div>
      <div class="stat-card emerald"><div class="stat-header"><span>Satıcıya / İndirilecek (191)</span><i class="fa-solid fa-arrow-down" style="color:var(--accent-emerald)"></i></div><div class="stat-val" style="font-size:18px;color:var(--accent-emerald)">{_tl(tev['toplam_indirilecek'])}</div></div>
    </div>"""

    sat = "".join(
        f'<tr><td>{s["islem"]}</td><td style="text-align:right">{_tl(s["matrah"])}</td>'
        f'<td style="text-align:center">%{int(s["kdv_orani"])}</td>'
        f'<td style="text-align:right">{_tl(s["kdv"])}</td>'
        f'<td style="text-align:center">{s["oran_metin"]}'
        f'{" <span class=\'badge warn\'>varsayılan</span>" if s["kaynak"]=="varsayilan" else ""}</td>'
        f'<td style="text-align:right;color:var(--accent-rose)">{_tl(s["tevkif"])}</td>'
        f'<td style="text-align:right;color:var(--accent-emerald)">{_tl(s["indirilecek"])}</td></tr>'
        for s in tev["satirlar"])
    tablo = f"""
    <div style="overflow-x:auto;margin-top:6px;"><table>
      <tr><th>İşlem Türü</th><th style="text-align:right">Matrah</th><th style="text-align:center">KDV%</th>
          <th style="text-align:right">Hesaplanan KDV</th><th style="text-align:center">Tevkifat Oranı</th>
          <th style="text-align:right">Tevkif Edilen (360)</th><th style="text-align:right">İndirilecek (191)</th></tr>
      {sat}
      <tr style="font-weight:700;border-top:2px solid rgba(255,255,255,0.15)"><td>TOPLAM</td>
        <td style="text-align:right">{_tl(tev['toplam_matrah'])}</td><td></td>
        <td style="text-align:right">{_tl(tev['toplam_kdv'])}</td><td></td>
        <td style="text-align:right;color:var(--accent-rose)">{_tl(tev['toplam_tevkif'])}</td>
        <td style="text-align:right;color:var(--accent-emerald)">{_tl(tev['toplam_indirilecek'])}</td></tr>
    </table></div>"""

    uyari = ""
    if tev.get("uyarilar"):
        lst = "".join(f'<li style="margin:6px 0;color:var(--text-muted);">{u["ac"]}</li>' for u in tev["uyarilar"])
        uyari = (f'<div style="margin-top:14px;"><h4 style="font-size:14px;margin-bottom:6px;">'
                 f'<i class="fa-solid fa-triangle-exclamation" style="color:var(--accent-gold)"></i> '
                 f'Tevkifat Uyarıları <span class="badge warn">{len(tev["uyarilar"])}</span></h4>'
                 f'<ul style="padding-left:18px;margin:0;">{lst}</ul></div>')

    mid, donem = sonuc.get("_mid", ""), sonuc.get("_donem", "")
    yazdir = (f'<div style="margin-top:14px;"><a class="btn-sec" target="_blank" '
              f'href="/tevkifat_beyan?m={mid}&d={donem}"><i class="fa-solid fa-print"></i> '
              f'2 No.lu Beyanname Taslağını Yazdır</a></div>')
    return h3 + slot + stat + tablo + uyari + yazdir


def _bolum_matrah(sonuc):
    h3 = ('<h3 style="font-family:\'Outfit\',sans-serif;font-size:17px;margin:26px 0 14px;">'
          '<i class="fa-solid fa-list-check" style="color:var(--accent-cyan)"></i> '
          'KDV Matrah / Oran Tutarlılık Denetimi</h3>'
          '<p style="margin-bottom:12px;font-size:13px;color:var(--text-muted);">Satış/alış faturalarının '
          'matrah ve oran dökümünü yükleyin; her satırda <strong>matrah×oran = KDV</strong> kontrolü, oran dışı/anormal '
          'oran taraması ve beyan toplamlarının mizandaki 391 (hesaplanan) / 191 (indirilecek) hareketleriyle '
          'örtüşmesi denetlenir.</p>')
    slot = ('<div style="display:flex;gap:14px;flex-wrap:wrap;">'
            + _gib_slot("kdv_matrah", "KDV Matrah Dökümü (tür + matrah + oran)", sonuc.get("matrah_dosya"))
            + '</div>')
    m = sonuc.get("matrah_denetim")
    if not m:
        return h3 + slot
    if m.get("hata"):
        return h3 + slot + f'<p style="color:var(--accent-rose);margin-top:10px;">Okuma hatası: {m["hata"]}</p>'

    stat = f"""
    <div class="stats-grid" style="margin:14px 0 8px;">
      <div class="stat-card"><div class="stat-header"><span>Satış Matrahı</span><i class="fa-solid fa-arrow-up" style="color:var(--accent-rose)"></i></div><div class="stat-val" style="font-size:18px">{_tl(m['satis']['matrah'])}</div><div class="stat-desc">Hesaplanan {_tl(m['satis']['kdv'])}</div></div>
      <div class="stat-card emerald"><div class="stat-header"><span>Alış Matrahı</span><i class="fa-solid fa-arrow-down" style="color:var(--accent-emerald)"></i></div><div class="stat-val" style="font-size:18px">{_tl(m['alis']['matrah'])}</div><div class="stat-desc">İndirilecek {_tl(m['alis']['kdv'])}</div></div>
      <div class="stat-card gold"><div class="stat-header"><span>Oran Uyarısı</span><i class="fa-solid fa-percent" style="color:var(--accent-gold)"></i></div><div class="stat-val">{len(m['oran_uyari'])}</div><div class="stat-desc">{m['kalem_sayisi']} kalem tarandı</div></div>
      <div class="stat-card rose"><div class="stat-header"><span>Satır Farkı</span><i class="fa-solid fa-scale-unbalanced" style="color:var(--accent-rose)"></i></div><div class="stat-val">{len(m['satir_uyari'])}</div><div class="stat-desc">matrah×oran ≠ KDV</div></div>
    </div>"""

    # mizan karsilastirma tablosu
    if m.get("mizan_var") and m["karsilastirma"]:
        sat = ""
        for k in m["karsilastirma"]:
            rozet = ('<span class="badge success">uyumlu</span>' if k["uyumlu"]
                     else '<span class="badge warn">sapma</span>')
            renk = "var(--accent-emerald)" if k["uyumlu"] else "var(--accent-rose)"
            sat += (f'<tr><td>{k["etiket"]}</td>'
                    f'<td style="text-align:right">{_tl(k["beyan_matrah"])}</td>'
                    f'<td style="text-align:right">{_tl(k["beyan_kdv"])}</td>'
                    f'<td style="text-align:right">{_tl(k["mizan_kdv"])}</td>'
                    f'<td style="text-align:right;color:{renk}">{_tl(k["fark"])}</td>'
                    f'<td style="text-align:center">{rozet}</td></tr>')
        kiyas = f"""
        <div style="overflow-x:auto;margin-top:6px;"><table>
          <tr><th>Beyan ↔ Mizan</th><th style="text-align:right">Beyan Matrah</th>
              <th style="text-align:right">Beyan KDV</th><th style="text-align:right">Mizan KDV</th>
              <th style="text-align:right">Fark</th><th style="text-align:center">Durum</th></tr>
          {sat}
        </table></div>
        <p style="margin-top:6px;font-size:12px;color:var(--text-muted);">Tolerans: ±%{m['tolerans']['yuzde']:g} ve en az {_tl(m['tolerans']['tutar'])} birlikte aşılırsa sapma sayılır. Eşikleri Tarama Ayarları'ndan değiştirebilirsiniz.</p>"""
    elif not m.get("mizan_var"):
        kiyas = ('<div class="notif-pill" style="margin-top:10px;"><div class="circle-icon-badge" style="background:var(--accent-gold)"></div>'
                 '<span>Beyan ↔ mizan karşılaştırması için Mizan Sağlık Taraması sekmesinden mizanı yükleyin.</span></div>')
    else:
        kiyas = ""

    def liste(grup, baslik, ikon, renk, kalemler):
        if kalemler:
            sat = "".join(f'<li style="margin:5px 0;color:var(--text-muted);font-size:13px;">{k["ac"]}</li>' for k in kalemler)
            govde = f'<ul style="padding-left:18px;margin:0;">{sat}</ul>'
            rozet = "warn"
        else:
            govde = ('<div class="notif-pill" style="margin-top:8px;"><div class="circle-icon-badge"></div>'
                     '<span>Bu kategoride bulgu yok.</span></div>')
            rozet = "success"
        return (f'<div style="margin-top:14px;"><h4 style="font-size:14px;margin-bottom:6px;">'
                f'<i class="fa-solid {ikon}" style="color:{renk}"></i> {baslik} '
                f'<span class="badge {rozet}">{len(kalemler)}</span></h4>{govde}</div>')

    bloklar = (liste("satir", "Satır KDV ≠ Matrah×Oran", "fa-scale-unbalanced", "var(--accent-rose)", m["satir_uyari"])
               + liste("oran", "Oran Dışı / Doğrulanacak Oran", "fa-percent", "var(--accent-gold)", m["oran_uyari"]))
    return h3 + slot + stat + kiyas + bloklar


def panel_html(sonuc):
    if not sonuc.get("hazir"):
        return _baslik()
    return (_baslik() + _bolum_kdv(sonuc) + _bolum_gib(sonuc)
            + _bolum_tevkifat(sonuc) + _bolum_matrah(sonuc))


kaydet(Modul("m4_gib_kdv", AD, "fa-building-columns", 3, calistir, panel_html))
