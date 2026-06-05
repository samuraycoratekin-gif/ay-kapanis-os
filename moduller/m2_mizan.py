# -*- coding: utf-8 -*-
"""M2 - Mizan Saglik Taramasi.

Yuklenen mizani (xls/xlsx) okur, 4 onayli kurala gore tarar, bulgu doner.
Yuklu dosya yoksa yukleme alani gosterir.
"""
from core.moduller import Modul, kaydet
from core import depo, mizan_oku, mizan_analiz

AD = "Mizan Sağlık Taraması"
ACIKLAMA = "Mizanı yükle; ters bakiyeler, kapanmamış geçici hesaplar ve anormal sapmalar anında listelensin."


def calistir(musteri_id, donem):
    yol = depo.yuklenen_bul(musteri_id, donem, "m2_mizan")
    if not yol:
        depo.modul_durum_guncelle(musteri_id, donem, "m2_mizan",
                                  durum="bekliyor", ilerleme=0, bulgu_sayisi=0)
        return {"hazir": False}
    try:
        mizan = mizan_oku.oku(yol)
        r = mizan_analiz.analiz_et(mizan)
    except Exception as e:
        depo.modul_durum_guncelle(musteri_id, donem, "m2_mizan",
                                  durum="hata", ilerleme=0, bulgu_sayisi=0)
        return {"hazir": True, "hata": str(e)}
    bulgu = r["toplam_bulgu"]
    depo.modul_durum_guncelle(musteri_id, donem, "m2_mizan",
                              durum=("tamam" if bulgu == 0 else "uyari"),
                              ilerleme=(100 if bulgu == 0 else 60),
                              bulgu_sayisi=bulgu)
    r["hazir"] = True
    return r


# --------------------------------------------------------------------------- #
def _tl(v):
    return f"{v:,.2f} TL".replace(",", "X").replace(".", ",").replace("X", ".")


def _trend_mini(aylar, degerler, guncel):
    """Aylik hareket yogunlugu mini bar grafigi (goreli; guncel ay altin)."""
    if not aylar or not degerler or len(degerler) != len(aylar):
        return ""
    mx = max(degerler) or 1
    barlar = "".join(
        f'<div class="trend-bar{" guncel" if a == guncel else ""}" '
        f'style="height:{max(6, round(v / mx * 100))}%;" title="{a}: {_tl(v)}"></div>'
        for a, v in zip(aylar, degerler))
    eksen = "".join(f'<span>{str(a)[:3]}</span>' for a in aylar)
    return (f'<div style="margin:12px 0 4px;"><div style="font-size:12px;color:var(--text-muted);margin-bottom:2px;">'
            f'<i class="fa-solid fa-chart-column" style="color:var(--accent-cyan)"></i> Aylık Hareket Yoğunluğu '
            f'<span style="opacity:.7">(göreli; güncel ay altın)</span></div>'
            f'<div class="trend-mini">{barlar}</div><div class="trend-eksen">{eksen}</div></div>')


def _spark(seri):
    """Tek hesabin aylik hareket sparkline'i (son ay vurgulu)."""
    if not seri:
        return ""
    mx = max((abs(v) for v in seri), default=0) or 1
    son = len(seri) - 1
    parcalar = []
    for i, v in enumerate(seri):
        cls = ' class="son"' if i == son else ''
        h = max(2, round(abs(v) / mx * 22))
        parcalar.append(f'<i{cls} style="height:{h}px;"></i>')
    return f'<span class="spark" title="aylık hareket trendi">{"".join(parcalar)}</span>'


def _yukleme_alani():
    return f"""
    <div class="panel-header">
      <div class="panel-title"><h2><i class="fa-solid fa-heart-pulse"></i> {AD}</h2>
      <p>{ACIKLAMA}</p></div>
      <div class="panel-header-icon"><i class="fa-solid fa-file-arrow-up"></i></div>
    </div>
    <div style="text-align:center; padding:40px 20px; border:2px dashed rgba(255,255,255,0.1);
                border-radius:16px; background:rgba(7,10,19,0.3);">
      <i class="fa-solid fa-cloud-arrow-up" style="font-size:42px; color:var(--accent-cyan); margin-bottom:16px;"></i>
      <p style="margin-bottom:18px; color:var(--text-muted);">Mizan dosyasını yükleyin (.xls / .xlsx). ERP'den aldığınız kümüle mizan veya standart mizan.</p>
      <input type="file" id="mizan-dosya" accept=".xls,.xlsx,.xlsm" style="display:none" onchange="yukleDosya('m2_mizan','mizan-dosya')">
      <button class="btn" onclick="document.getElementById('mizan-dosya').click()">
        <i class="fa-solid fa-upload"></i> Mizan Seç ve Yükle
      </button>
      <p id="yukleme-durum" style="margin-top:14px; font-size:12px; color:var(--accent-cyan);"></p>
    </div>
    """


def _bulgu_tablo(grup, baslik, ikon, renk, bulgular, sutunlar):
    if not bulgular:
        govde = ('<div class="notif-pill" style="margin-top:12px;">'
                 '<div class="circle-icon-badge"></div>'
                 f'<span>Bu kategoride bulgu yok.</span></div>')
    else:
        satirlar = "".join(
            "<tr>" + "".join(f"<td>{h(x)}</td>" for h in sutunlar) + "</tr>"
            for x in bulgular
        )
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
        return _yukleme_alani()
    if sonuc.get("hata"):
        return (_yukleme_alani() +
                f'<p style="margin-top:16px;color:var(--accent-rose);">Okuma hatası: {sonuc["hata"]}</p>')

    b = sonuc["bulgular"]
    ust = f"""
    <div class="panel-header">
      <div class="panel-title"><h2><i class="fa-solid fa-heart-pulse"></i> {AD}</h2>
      <p>Kaynak: {sonuc['kaynak']} · {sonuc['format']} format · {sonuc['hesap_sayisi']} ana hesap · {sonuc['satir_sayisi']} satır · dönem: {sonuc['guncel_ay'] or '—'}</p></div>
      <div class="panel-header-icon"><i class="fa-solid fa-heart-pulse"></i></div>
    </div>
    <div class="stats-grid" style="margin-bottom:8px;">
      <div class="stat-card rose filtre-kart" data-hedef="ters" onclick="bulguFiltrele('ters', this)"><div class="stat-header"><span>Ters Bakiye</span><i class="fa-solid fa-arrow-right-arrow-left" style="color:var(--accent-rose)"></i></div><div class="stat-val">{len(b['ters'])}</div><div class="stat-desc"><span class="ipucu">Görmek için tıkla</span></div></div>
      <div class="stat-card gold filtre-kart" data-hedef="gecici" onclick="bulguFiltrele('gecici', this)"><div class="stat-header"><span>Kapanmamış Geçici</span><i class="fa-solid fa-lock-open" style="color:var(--accent-gold)"></i></div><div class="stat-val">{len(b['gecici'])}</div><div class="stat-desc"><span class="ipucu">Görmek için tıkla</span></div></div>
      <div class="stat-card filtre-kart" data-hedef="sapma" onclick="bulguFiltrele('sapma', this)"><div class="stat-header"><span>Anormal Sapma</span><i class="fa-solid fa-chart-line" style="color:var(--accent-cyan)"></i></div><div class="stat-val">{len(b['sapma'])}</div><div class="stat-desc"><span class="ipucu">Görmek için tıkla</span></div></div>
      <div class="stat-card gold filtre-kart" data-hedef="bos_hesap" onclick="bulguFiltrele('bos_hesap', this)"><div class="stat-header"><span>Boş Zorunlu Hesap</span><i class="fa-solid fa-circle-exclamation" style="color:var(--accent-gold)"></i></div><div class="stat-val">{len(b.get('bos_hesap', []))}</div><div class="stat-desc"><span class="ipucu">Görmek için tıkla</span></div></div>
      <div class="stat-card emerald filtre-kart aktif" data-hedef="all" onclick="bulguFiltrele('all', this)"><div class="stat-header"><span>Toplam Bulgu</span><i class="fa-solid fa-list-check" style="color:var(--accent-emerald)"></i></div><div class="stat-val">{sonuc['toplam_bulgu']}</div><div class="stat-desc"><span class="ipucu">Tümünü göster</span></div></div>
    </div>
    <div style="margin:8px 0 4px;"><button class="btn-sec" onclick="document.getElementById('mizan-yeni').click()"><i class="fa-solid fa-rotate"></i> Farklı Mizan Yükle</button>
    <input type="file" id="mizan-yeni" accept=".xls,.xlsx,.xlsm" style="display:none" onchange="yukleDosya('m2_mizan','mizan-yeni')"></div>
    {_trend_mini(sonuc.get("aylar", []), sonuc.get("aylik_hareket", []), sonuc.get("guncel_ay"))}
    """

    if sonuc["toplam_bulgu"] == 0:
        return ust + '<div class="notif-pill" style="margin-top:20px;"><div class="circle-icon-badge"></div><span>Tebrikler — mizan temiz, bulgu yok.</span></div>'

    t_ters = _bulgu_tablo("ters", "Ters Bakiyeler", "fa-arrow-right-arrow-left", "var(--accent-rose)", b["ters"], [
        lambda x: f'<span class="badge err">{x["ana"]}</span>',
        lambda x: f'<strong>{x["ad"]}</strong>',
        lambda x: f'Beklenen: {x["beklenen"]} → Gerçek: <span style="color:var(--accent-rose)">{x["gercek"]}</span>',
        lambda x: _tl(abs(x["bakiye"])),
    ])
    t_gecici = _bulgu_tablo("gecici", "Kapanmamış Geçici Hesaplar", "fa-lock-open", "var(--accent-gold)", b["gecici"], [
        lambda x: f'<span class="badge warn">{x["ana"]}</span>',
        lambda x: f'<strong>{x["ad"]}</strong>',
        lambda x: _tl(x["bakiye"]),
        lambda x: '<span style="color:var(--text-muted)">mahsup/yansıtma bekliyor</span>',
    ])
    t_sapma = _bulgu_tablo("sapma", "Anormal Aylık Sapmalar", "fa-chart-line", "var(--accent-cyan)", b["sapma"], [
        lambda x: f'<span class="badge neutral">{x["ana"]}</span>',
        lambda x: f'<strong>{x["ad"]}</strong>',
        lambda x: f'{sonuc["guncel_ay"]}: {_tl(x["guncel"])}',
        lambda x: (f'önceki ort. {_tl(x["ort_onceki"])} · {x["kat"]:.1f}×' if x["kat"] else 'önceki aylarda hareket yok')
        + (f'<br><span style="color:var(--text-muted);font-size:11px;">↳ karşı bacak: {x["karsi"]}</span>' if x.get("karsi") else ''),
        lambda x: _spark(x.get("seri", [])),
    ])
    t_bos = _bulgu_tablo("bos_hesap", "Boş / Hareketsiz Zorunlu Hesaplar", "fa-circle-exclamation", "var(--accent-gold)", b.get("bos_hesap", []), [
        lambda x: f'<span class="badge warn">{x["ana"]}</span>',
        lambda x: f'<strong>{x["ad"]}</strong>',
        lambda x: ('<span style="color:var(--accent-rose)">mizanda yok</span>' if x["durum"] == "yok"
                   else '<span style="color:var(--text-muted)">bakiye/hareket yok</span>'),
        lambda x: x["ac"],
    ])
    return ust + t_ters + t_gecici + t_sapma + t_bos


kaydet(Modul("m2_mizan", AD, "fa-heart-pulse", 1, calistir, panel_html))
