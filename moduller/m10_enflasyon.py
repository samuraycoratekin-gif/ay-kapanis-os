# -*- coding: utf-8 -*-
"""M10 - Enflasyon Duzeltmesi (VUK muk. 298) Kontrol & Tahmin.

Mizandan beslenir; ek yukleme gerekmez. Parasal/parasal-olmayan ayrim, net parasal
pozisyon kar/zarari, parasal-olmayan duzeltme kaba tahmini, 698 kapanis kontrolu.
Kesin duzeltme kiymet bazinda yapilir; bu modul tahmin + kontrol amaclidir.
"""
from core.moduller import Modul, kaydet
from core import depo, mizan_oku, enflasyon

AD = "Enflasyon Düzeltmesi"
ACIKLAMA = "Parasal/parasal-olmayan ayrımı, net parasal pozisyon kâr/zararı ve 698 düzeltme hesabı kontrolü (VUK mük. 298)."


def calistir(musteri_id, donem):
    yol = depo.yuklenen_bul(musteri_id, donem, "m2_mizan")
    if not yol:
        depo.modul_durum_guncelle(musteri_id, donem, "m10_enflasyon",
                                  durum="bekliyor", ilerleme=0, bulgu_sayisi=0)
        return {"hazir": False}
    try:
        mizan = mizan_oku.oku(yol)
        r = enflasyon.analiz_et(mizan)
    except Exception as e:
        depo.modul_durum_guncelle(musteri_id, donem, "m10_enflasyon",
                                  durum="hata", ilerleme=0, bulgu_sayisi=0)
        return {"hazir": True, "hata": str(e)}
    bulgu = len(r["uyarilar"])
    depo.modul_durum_guncelle(musteri_id, donem, "m10_enflasyon",
                              durum=("tamam" if bulgu == 0 else "uyari"),
                              ilerleme=(100 if bulgu == 0 else 70),
                              bulgu_sayisi=bulgu)
    r["hazir"] = True
    return r


# --------------------------------------------------------------------------- #
def _tl(v):
    return f"{v:,.2f} TL".replace(",", "X").replace(".", ",").replace("X", ".")


def _yukleme_uyari():
    return f"""
    <div class="panel-header">
      <div class="panel-title"><h2><i class="fa-solid fa-arrow-trend-up"></i> {AD}</h2>
      <p>{ACIKLAMA}</p></div>
      <div class="panel-header-icon"><i class="fa-solid fa-arrow-trend-up"></i></div>
    </div>
    <div class="notif-pill" style="margin-top:16px;">
      <i class="fa-solid fa-circle-info" style="color:var(--accent-cyan)"></i>
      <span>Bu modül mizandan beslenir. Önce <strong>Mizan Sağlık Taraması</strong> sekmesinden mizanı yükleyin.</span>
    </div>"""


def _tablo(satirlar_html, basliklar):
    bas = "".join(f"<th>{b}</th>" for b in basliklar)
    return f'<div style="overflow-x:auto;"><table><tr>{bas}</tr>{satirlar_html}</table></div>'


def panel_html(sonuc):
    if not sonuc.get("hazir"):
        return _yukleme_uyari()
    if sonuc.get("hata"):
        return (_yukleme_uyari() +
                f'<p style="margin-top:16px;color:var(--accent-rose);">Okuma hatası: {sonuc["hata"]}</p>')

    kat = sonuc["katsayi"]
    kat_str = (f"{kat:.4f}" if kat else "—")
    ufe_str = (f"{sonuc['son_ufe']:.1f} / {sonuc['bas_ufe']:.1f}" if sonuc.get("son_ufe") else "—")
    ppk = sonuc["parasal_poz_kar"]
    if ppk is None:
        ppk_str, ppk_renk, ppk_alt = "—", "var(--accent-cyan)", "katsayı yok"
    elif ppk >= 0:
        ppk_str, ppk_renk, ppk_alt = _tl(ppk), "var(--accent-emerald)", "satın alma gücü kazancı"
    else:
        ppk_str, ppk_renk, ppk_alt = _tl(ppk), "var(--accent-rose)", "satın alma gücü kaybı"
    pol_d = sonuc["pol_duzeltme"]
    pol_d_str = (_tl(pol_d) if pol_d is not None else "—")
    b698 = sonuc["b698"]
    b698_str = (_tl(b698) if abs(b698) > 1 else "kapalı")

    ust = f"""
    <div class="panel-header">
      <div class="panel-title"><h2><i class="fa-solid fa-arrow-trend-up"></i> {AD}</h2>
      <p>Dönem katsayısı {kat_str} · Yİ-ÜFE (son/yıl başı) {ufe_str} · {sonuc['pol_kalem_sayisi']} parasal olmayan hesap</p></div>
      <div class="panel-header-icon"><i class="fa-solid fa-arrow-trend-up"></i></div>
    </div>
    <div class="stats-grid" style="margin-bottom:8px;">
      <div class="stat-card filtre-kart" data-hedef="poz" onclick="bulguFiltrele('poz', this)"><div class="stat-header"><span>Net Parasal Pozisyon</span><i class="fa-solid fa-scale-unbalanced" style="color:var(--accent-cyan)"></i></div><div class="stat-val" style="font-size:20px;">{_tl(sonuc['net_parasal'])}</div><div class="stat-desc"><span class="ipucu">aktif−pasif</span></div></div>
      <div class="stat-card filtre-kart" data-hedef="poz" onclick="bulguFiltrele('poz', this)"><div class="stat-header"><span>Parasal Poz. K/Z (tahmini)</span><i class="fa-solid fa-coins" style="color:{ppk_renk}"></i></div><div class="stat-val" style="font-size:20px;color:{ppk_renk}">{ppk_str}</div><div class="stat-desc"><span class="ipucu">{ppk_alt}</span></div></div>
      <div class="stat-card gold filtre-kart" data-hedef="pol" onclick="bulguFiltrele('pol', this)"><div class="stat-header"><span>Düzeltme Tahmini (PO)</span><i class="fa-solid fa-wand-magic-sparkles" style="color:var(--accent-gold)"></i></div><div class="stat-val" style="font-size:20px;">{pol_d_str}</div><div class="stat-desc"><span class="ipucu">698→580 kaba tahmin</span></div></div>
      <div class="stat-card {'rose' if abs(b698)>1 else ''} filtre-kart" data-hedef="uyari" onclick="bulguFiltrele('uyari', this)"><div class="stat-header"><span>698 Durumu</span><i class="fa-solid fa-lock-open" style="color:var(--accent-rose)"></i></div><div class="stat-val" style="font-size:20px;">{b698_str}</div><div class="stat-desc"><span class="ipucu">{len(sonuc['uyarilar'])} uyarı</span></div></div>
      <div class="stat-card emerald filtre-kart aktif" data-hedef="all" onclick="bulguFiltrele('all', this)"><div class="stat-header"><span>Parasal Olmayan Toplam</span><i class="fa-solid fa-list-check" style="color:var(--accent-emerald)"></i></div><div class="stat-val" style="font-size:20px;">{_tl(sonuc['pol_toplam'])}</div><div class="stat-desc"><span class="ipucu">Tümünü göster</span></div></div>
    </div>
    <div class="notif-pill" style="margin-top:4px;"><i class="fa-solid fa-triangle-exclamation" style="color:var(--accent-gold)"></i>
      <span>{sonuc['kaynak_notu']} Kesin düzeltme kıymet bazında ve edinim tarihine göre yapılır; buradaki düzeltme <strong>YTD kaba tahmindir</strong>.</span></div>
    """

    # Uyarilar
    if sonuc["uyarilar"]:
        u_sat = "".join(
            f'<tr><td><span class="badge warn">{u["tip"]}</span></td><td>{u["ac"]}</td></tr>'
            for u in sonuc["uyarilar"])
        u_blok = f"""<div class="filtre-bolum" data-grup="uyari" style="margin-top:24px;">
          <h3 style="font-family:'Outfit',sans-serif;font-size:16px;margin-bottom:12px;">
          <i class="fa-solid fa-triangle-exclamation" style="color:var(--accent-gold)"></i> Uyarılar
          <span class="badge warn" style="margin-left:8px;">{len(sonuc['uyarilar'])}</span></h3>
          {_tablo(u_sat, ["Tip", "Açıklama"])}</div>"""
    else:
        u_blok = ('<div class="filtre-bolum" data-grup="uyari" style="margin-top:24px;">'
                  '<div class="notif-pill"><div class="circle-icon-badge"></div>'
                  '<span>Enflasyon düzeltmesi açısından uyarı yok.</span></div></div>')

    # Net parasal pozisyon ozeti
    poz_sat = (f'<tr><td>Parasal aktif</td><td style="text-align:right">{_tl(sonuc["parasal_aktif"])}</td></tr>'
               f'<tr><td>Parasal pasif</td><td style="text-align:right">{_tl(sonuc["parasal_pasif"])}</td></tr>'
               f'<tr><td><strong>Net parasal pozisyon</strong></td><td style="text-align:right"><strong>{_tl(sonuc["net_parasal"])}</strong></td></tr>')
    poz_blok = f"""<div class="filtre-bolum" data-grup="poz" style="margin-top:24px;">
      <h3 style="font-family:'Outfit',sans-serif;font-size:16px;margin-bottom:12px;">
      <i class="fa-solid fa-scale-unbalanced" style="color:var(--accent-cyan)"></i> Net Parasal Pozisyon</h3>
      <p style="color:var(--text-muted);font-size:13px;margin-bottom:8px;">Net parasal AKTİF → enflasyonda satın alma gücü <em>kaybı</em>; net parasal PASİF → <em>kazanç</em>.</p>
      {_tablo(poz_sat, ["Kalem", "Tutar"])}</div>"""

    # Parasal olmayan kalemler + duzeltme tahmini
    if sonuc["pol_kalemler"]:
        pol_sat = "".join(
            f'<tr><td><span class="badge neutral">{x["ana"]}</span></td><td><strong>{x["ad"]}</strong></td>'
            f'<td style="text-align:right">{_tl(x["bakiye"])}</td>'
            f'<td style="text-align:right;color:var(--accent-gold)">{(_tl(x["duzeltme"]) if x["duzeltme"] is not None else "—")}</td></tr>'
            for x in sonuc["pol_kalemler"])
        pol_blok = f"""<div class="filtre-bolum" data-grup="pol" style="margin-top:24px;">
          <h3 style="font-family:'Outfit',sans-serif;font-size:16px;margin-bottom:12px;">
          <i class="fa-solid fa-wand-magic-sparkles" style="color:var(--accent-gold)"></i> Parasal Olmayan Kıymetler — Düzeltme Tahmini
          <span class="badge neutral" style="margin-left:8px;">{sonuc['pol_kalem_sayisi']}</span></h3>
          {_tablo(pol_sat, ["Hesap", "Ad", "Bakiye", "Düzeltme (tahmini)"])}</div>"""
    else:
        pol_blok = ('<div class="filtre-bolum" data-grup="pol" style="margin-top:24px;">'
                    '<div class="notif-pill"><div class="circle-icon-badge"></div>'
                    '<span>Mizanda parasal olmayan (düzeltmeye tabi) kıymet bulunamadı.</span></div></div>')

    return ust + u_blok + poz_blok + pol_blok


kaydet(Modul("m10_enflasyon", AD, "fa-arrow-trend-up", 8, calistir, panel_html))
