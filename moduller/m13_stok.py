# -*- coding: utf-8 -*-
"""M13 - Stok & Maliyet Kontrolu.

Mizandan (M2 ile ayni dosya) beslenir; ek yukleme gerekmez. Negatif stok,
brut kar marji makuliyeti, atil stok devir hizi, 158/159 kontrolleri.
"""
from core.moduller import Modul, kaydet
from core import depo, mizan_oku, stok_analiz

AD = "Stok & Maliyet Kontrolü"
ACIKLAMA = "Mizandan negatif stok, brüt kâr marjı tutarlılığı, atıl/yavaş devreden stok ve 158/159 kontrolü."


def calistir(musteri_id, donem):
    yol = depo.yuklenen_bul(musteri_id, donem, "m2_mizan")
    if not yol:
        depo.modul_durum_guncelle(musteri_id, donem, "m13_stok",
                                  durum="bekliyor", ilerleme=0, bulgu_sayisi=0)
        return {"hazir": False}
    try:
        mizan = mizan_oku.oku(yol)
        r = stok_analiz.analiz_et(mizan)
    except Exception as e:
        depo.modul_durum_guncelle(musteri_id, donem, "m13_stok",
                                  durum="hata", ilerleme=0, bulgu_sayisi=0)
        return {"hazir": True, "hata": str(e)}
    if not r.get("stok_var"):
        depo.modul_durum_guncelle(musteri_id, donem, "m13_stok",
                                  durum="tamam", ilerleme=100, bulgu_sayisi=0)
        r["hazir"] = True
        return r
    bulgu = r["toplam_bulgu"]
    depo.modul_durum_guncelle(musteri_id, donem, "m13_stok",
                              durum=("tamam" if bulgu == 0 else "uyari"),
                              ilerleme=(100 if bulgu == 0 else 60),
                              bulgu_sayisi=bulgu)
    r["hazir"] = True
    return r


# --------------------------------------------------------------------------- #
def _tl(v):
    return f"{v:,.2f} TL".replace(",", "X").replace(".", ",").replace("X", ".")


def _yukleme_uyari():
    return f"""
    <div class="panel-header">
      <div class="panel-title"><h2><i class="fa-solid fa-boxes-stacked"></i> {AD}</h2>
      <p>{ACIKLAMA}</p></div>
      <div class="panel-header-icon"><i class="fa-solid fa-boxes-stacked"></i></div>
    </div>
    <div class="notif-pill" style="margin-top:16px;">
      <i class="fa-solid fa-circle-info" style="color:var(--accent-cyan)"></i>
      <span>Bu modül mizandan beslenir. Önce <strong>Mizan Sağlık Taraması</strong> sekmesinden mizanı yükleyin.</span>
    </div>"""


def _bulgu_tablo(grup, baslik, ikon, renk, bulgular, sutunlar):
    if not bulgular:
        govde = ('<div class="notif-pill" style="margin-top:12px;">'
                 '<div class="circle-icon-badge"></div>'
                 '<span>Bu kategoride bulgu yok.</span></div>')
    else:
        satirlar = "".join(
            "<tr>" + "".join(f"<td>{h(x)}</td>" for h in sutunlar) + "</tr>"
            for x in bulgular)
        govde = f'<div style="overflow-x:auto;"><table>{satirlar}</table></div>'
    return f"""
    <div class="filtre-bolum" data-grup="{grup}" style="margin-top:24px;">
      <h3 style="font-family:'Outfit',sans-serif; font-size:16px; margin-bottom:12px;">
        <i class="fa-solid {ikon}" style="color:{renk}"></i> {baslik}
        <span class="badge {'warn' if bulgular else 'success'}" style="margin-left:8px;">{len(bulgular)}</span>
      </h3>
      {govde}
    </div>"""


def panel_html(sonuc):
    if not sonuc.get("hazir"):
        return _yukleme_uyari()
    if sonuc.get("hata"):
        return (_yukleme_uyari() +
                f'<p style="margin-top:16px;color:var(--accent-rose);">Okuma hatası: {sonuc["hata"]}</p>')
    if not sonuc.get("stok_var"):
        return f"""
        <div class="panel-header">
          <div class="panel-title"><h2><i class="fa-solid fa-boxes-stacked"></i> {AD}</h2>
          <p>{ACIKLAMA}</p></div>
          <div class="panel-header-icon"><i class="fa-solid fa-boxes-stacked"></i></div>
        </div>
        <div class="notif-pill" style="margin-top:20px;"><div class="circle-icon-badge"></div>
        <span>Mizanda stok hesabı (150-157) bulunamadı — bu firma stok takibi yapmıyor olabilir.</span></div>"""

    b = sonuc["bulgular"]
    o = sonuc["ozet"]
    marj_str = (f"%{o['marj']:.1f}" if o["marj"] is not None else "—")
    ay_str = (f"{o['ay_stok']:.1f} ay" if o["ay_stok"] is not None else "—")
    ust = f"""
    <div class="panel-header">
      <div class="panel-title"><h2><i class="fa-solid fa-boxes-stacked"></i> {AD}</h2>
      <p>Net satış {_tl(o['net_satis'])} · SMM {_tl(o['smm'])} · brüt kâr {_tl(o['brut_kar'])} · marj {marj_str} · stok devir ≈ {ay_str}</p></div>
      <div class="panel-header-icon"><i class="fa-solid fa-boxes-stacked"></i></div>
    </div>
    <div class="stats-grid" style="margin-bottom:8px;">
      <div class="stat-card rose filtre-kart" data-hedef="negatif" onclick="bulguFiltrele('negatif', this)"><div class="stat-header"><span>Negatif Stok</span><i class="fa-solid fa-arrow-down" style="color:var(--accent-rose)"></i></div><div class="stat-val">{len(b['negatif'])}</div><div class="stat-desc"><span class="ipucu">Görmek için tıkla</span></div></div>
      <div class="stat-card gold filtre-kart" data-hedef="satis" onclick="bulguFiltrele('satis', this)"><div class="stat-header"><span>Maliyet/Marj Uyarısı</span><i class="fa-solid fa-percent" style="color:var(--accent-gold)"></i></div><div class="stat-val">{len(b['satis'])}</div><div class="stat-desc"><span class="ipucu">Görmek için tıkla</span></div></div>
      <div class="stat-card gold filtre-kart" data-hedef="atil" onclick="bulguFiltrele('atil', this)"><div class="stat-header"><span>Atıl / Yavaş Stok</span><i class="fa-solid fa-hourglass-half" style="color:var(--accent-gold)"></i></div><div class="stat-val">{len(b['atil'])}</div><div class="stat-desc"><span class="ipucu">Görmek için tıkla</span></div></div>
      <div class="stat-card filtre-kart" data-hedef="kontra_avans" onclick="bulguFiltrele('kontra_avans', this)"><div class="stat-header"><span>158/159 Kontrol</span><i class="fa-solid fa-scale-balanced" style="color:var(--accent-cyan)"></i></div><div class="stat-val">{len(b['kontra']) + len(b['avans'])}</div><div class="stat-desc"><span class="ipucu">Görmek için tıkla</span></div></div>
      <div class="stat-card emerald filtre-kart aktif" data-hedef="all" onclick="bulguFiltrele('all', this)"><div class="stat-header"><span>Toplam Bulgu</span><i class="fa-solid fa-list-check" style="color:var(--accent-emerald)"></i></div><div class="stat-val">{sonuc['toplam_bulgu']}</div><div class="stat-desc"><span class="ipucu">Tümünü göster</span></div></div>
    </div>"""

    if sonuc["toplam_bulgu"] == 0:
        return ust + '<div class="notif-pill" style="margin-top:20px;"><div class="circle-icon-badge"></div><span>Stok ve maliyet tutarlı — bulgu yok.</span></div>'

    t_neg = _bulgu_tablo("negatif", "Negatif Stok Bakiyeleri", "fa-arrow-down", "var(--accent-rose)", b["negatif"], [
        lambda x: f'<span class="badge err">{x["ana"]}</span>',
        lambda x: f'<strong>{x["ad"]}</strong>',
        lambda x: f'<span style="color:var(--accent-rose)">{_tl(abs(x["bakiye"]))} alacak</span>',
        lambda x: x["ac"],
    ])
    t_satis = _bulgu_tablo("satis", "Maliyet / Brüt Kâr Marjı Uyarıları", "fa-percent", "var(--accent-gold)", b["satis"], [
        lambda x: f'<span class="badge warn">{("marj %"+format(x["marj"],".1f")) if x.get("marj") is not None else "uyum"}</span>',
        lambda x: x["ac"],
    ])
    t_atil = _bulgu_tablo("atil", "Atıl / Yavaş Devreden Stok", "fa-hourglass-half", "var(--accent-gold)", b["atil"], [
        lambda x: (f'<span class="badge warn">{x["ay"]:.1f} ay</span>' if x.get("ay") else '<span class="badge warn">durağan</span>'),
        lambda x: x["ac"],
    ])
    kontra_avans = ([dict(x, _t="kontra") for x in b["kontra"]] +
                    [dict(x, _t="avans") for x in b["avans"]])
    t_ka = _bulgu_tablo("kontra_avans", "158 Değer Düşüklüğü / 159 Sipariş Avansı", "fa-scale-balanced", "var(--accent-cyan)", kontra_avans, [
        lambda x: f'<span class="badge {"err" if x["_t"]=="kontra" else "neutral"}">{x["ana"]}</span>',
        lambda x: f'<strong>{x["ad"]}</strong>',
        lambda x: _tl(x["bakiye"]),
        lambda x: x["ac"],
    ])
    return ust + t_neg + t_satis + t_atil + t_ka


kaydet(Modul("m13_stok", AD, "fa-boxes-stacked", 6, calistir, panel_html))
