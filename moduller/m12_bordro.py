# -*- coding: utf-8 -*-
"""M12 - Bordro <-> Muhasebe Mutabakati.

Bordro icmali (puantaj ozeti) yuklenir; toplamlari mizan hesap hareketleriyle
karsilastirilir: net ucret<->335, SGK<->361, gelir vergisi+damga<->360,
personel gideri<->720/730/740/760/770. Mizan yoksa ic tutarlilik kontrol edilir.
"""
from core.moduller import Modul, kaydet
from core import depo, mizan_oku, bordro_oku, bordro_analiz, sgk_oku

AD = "Bordro ↔ Muhasebe Mutabakatı"
ACIKLAMA = "Bordro icmalini yükle; net ücret/SGK/vergi ve personel gideri mizandaki 335/361/360 ve gider hesaplarıyla mutabık mı kontrol edilsin."


def _sgk_oku(musteri_id, donem, bordro):
    """SGK rapor dokumu (rol='sgk') varsa bordro ile capraz kontrol; yoksa None."""
    sgk_yol = depo.yuklenen_bul(musteri_id, donem, "m12_bordro", rol="sgk")
    if not sgk_yol:
        return None
    try:
        sgk = sgk_oku.oku(sgk_yol)
        return sgk_oku.analiz(sgk, bordro)
    except Exception as e:
        return {"hata": str(e)}


def calistir(musteri_id, donem):
    yol = depo.yuklenen_bul(musteri_id, donem, "m12_bordro", rol="icmal")
    if not yol:
        depo.modul_durum_guncelle(musteri_id, donem, "m12_bordro",
                                  durum="bekliyor", ilerleme=0, bulgu_sayisi=0)
        return {"hazir": False}
    try:
        bordro = bordro_oku.oku(yol)
        mizan = None
        mizan_yol = depo.yuklenen_bul(musteri_id, donem, "m2_mizan")
        if mizan_yol:
            mizan = mizan_oku.oku(mizan_yol)
        r = bordro_analiz.karsilastir(bordro, mizan)
        sgk = _sgk_oku(musteri_id, donem, bordro)
    except Exception as e:
        depo.modul_durum_guncelle(musteri_id, donem, "m12_bordro",
                                  durum="hata", ilerleme=0, bulgu_sayisi=0)
        return {"hazir": True, "hata": str(e)}
    sgk_bulgu = sgk["bulgu"] if (sgk and not sgk.get("hata")) else 0
    bulgu = r["bulgu"] + sgk_bulgu
    depo.modul_durum_guncelle(musteri_id, donem, "m12_bordro",
                              durum=("tamam" if bulgu == 0 else "uyari"),
                              ilerleme=(100 if bulgu == 0 else 60),
                              bulgu_sayisi=bulgu)
    r["hazir"] = True
    r["sgk"] = sgk
    return r


# --------------------------------------------------------------------------- #
def _tl(v):
    return f"{v:,.2f} TL".replace(",", "X").replace(".", ",").replace("X", ".")


def _yukleme_alani():
    return f"""
    <div class="panel-header">
      <div class="panel-title"><h2><i class="fa-solid fa-users-gear"></i> {AD}</h2>
      <p>{ACIKLAMA}</p></div>
      <div class="panel-header-icon"><i class="fa-solid fa-file-arrow-up"></i></div>
    </div>
    <div style="text-align:center; padding:40px 20px; border:2px dashed rgba(255,255,255,0.1);
                border-radius:16px; background:rgba(7,10,19,0.3);">
      <i class="fa-solid fa-cloud-arrow-up" style="font-size:42px; color:var(--accent-cyan); margin-bottom:16px;"></i>
      <p style="margin-bottom:18px; color:var(--text-muted);">Bordro icmal dosyasını yükleyin (.xls / .xlsx). Brüt, SGK işçi/işveren, işsizlik, gelir vergisi, damga, net sütunları beklenir.</p>
      <input type="file" id="bordro-dosya" accept=".xls,.xlsx,.xlsm" style="display:none" onchange="yukleDosya('m12_bordro','bordro-dosya','icmal')">
      <button class="btn" onclick="document.getElementById('bordro-dosya').click()">
        <i class="fa-solid fa-upload"></i> Bordro İcmali Seç ve Yükle
      </button>
      <p id="yukleme-durum" style="margin-top:14px; font-size:12px; color:var(--accent-cyan);"></p>
    </div>
    <div style="text-align:center; padding:24px 20px; margin-top:14px; border:2px dashed rgba(255,255,255,0.1);
                border-radius:16px; background:rgba(7,10,19,0.3);">
      <i class="fa-solid fa-notes-medical" style="font-size:32px; color:var(--accent-gold); margin-bottom:10px;"></i>
      <p style="margin-bottom:14px; color:var(--text-muted); font-size:13px;">İsteğe bağlı: SGK istirahat/rapor dökümü (.xls / .xlsx). Personel, rapor başlangıç/bitiş, gün sayısı sütunları beklenir. SGK gün ↔ bordro çapraz kontrolü yapılır.</p>
      <input type="file" id="sgk-dosya" accept=".xls,.xlsx,.xlsm" style="display:none" onchange="yukleDosya('m12_bordro','sgk-dosya','sgk')">
      <button class="btn-sec" onclick="document.getElementById('sgk-dosya').click()">
        <i class="fa-solid fa-upload"></i> SGK Rapor Dökümü Yükle
      </button>
    </div>"""


def _kiyas_satir(k):
    rozet = ('<span class="badge success">uyumlu</span>' if k["uyumlu"]
             else '<span class="badge err">fark</span>')
    fark_renk = "var(--text-muted)" if k["uyumlu"] else "var(--accent-rose)"
    return (f'<tr><td>{rozet}</td><td><strong>{k["kalem"]}</strong></td>'
            f'<td><span class="badge neutral">{k["hesap"]}</span></td>'
            f'<td style="text-align:right">{_tl(k["icmal"])}</td>'
            f'<td style="text-align:right">{_tl(k["mizan"])}</td>'
            f'<td style="text-align:right;color:{fark_renk}">{_tl(k["fark"])}</td></tr>')


def _soft_satir(k):
    rozet = ('<span class="badge success">karşılıyor</span>' if k["uyumlu"]
             else '<span class="badge warn">eksik?</span>')
    return (f'<tr><td>{rozet}</td><td><strong>{k["kalem"]}</strong> '
            f'<span class="badge neutral">{k["hesap"]}</span></td>'
            f'<td style="text-align:right">{_tl(k["icmal"])}</td>'
            f'<td style="text-align:right">{_tl(k["mizan"])}</td>'
            f'<td style="color:var(--text-muted);font-size:12px">{k["ac"]}</td></tr>')


def _sgk_blok(sgk):
    """SGK rapor capraz kontrol bolumu (m12 icine gomulu)."""
    if not sgk:
        return ('<div class="filtre-bolum" data-grup="all" style="margin-top:24px;">'
                '<h3 style="font-family:\'Outfit\',sans-serif;font-size:16px;margin-bottom:8px;">'
                '<i class="fa-solid fa-notes-medical" style="color:var(--accent-gold)"></i> SGK Rapor Kontrolü</h3>'
                '<p style="font-size:13px;color:var(--text-muted);">SGK istirahat/rapor dökümü yüklerseniz; raporlu personel, '
                'eksik gün (kod 01) bildirimi, ilk 2 gün işveren / SGK gün ayrımı ve bordro çapraz eşleşmesi burada kontrol edilir.</p></div>')
    if sgk.get("hata"):
        return ('<div class="filtre-bolum" data-grup="all" style="margin-top:24px;">'
                '<h3 style="font-family:\'Outfit\',sans-serif;font-size:16px;margin-bottom:8px;">'
                '<i class="fa-solid fa-notes-medical" style="color:var(--accent-gold)"></i> SGK Rapor Kontrolü</h3>'
                f'<p style="color:var(--accent-rose);font-size:13px;">SGK dökümü okuma hatası: {sgk["hata"]}</p></div>')

    sat = ""
    for s in sgk["satirlar"]:
        tarih = (f'{s["baslangic"] or "—"} → {s["bitis"] or "—"}')
        rozet = ""
        if s["bordroda"] is False:
            rozet = ' <span class="badge err">bordroda yok</span>'
        elif s["bordroda"] is True:
            rozet = ' <span class="badge success">bordroda</span>'
        sat += (f'<tr><td><strong>{s["ad"]}</strong>{rozet}</td>'
                f'<td><span class="badge neutral">{s["tur_etiket"]}</span></td>'
                f'<td style="font-size:12px;color:var(--text-muted)">{tarih}</td>'
                f'<td style="text-align:right">{s["gun"]}</td>'
                f'<td style="text-align:right">{s["isveren_gun"]}</td>'
                f'<td style="text-align:right">{s["sgk_gun"]}</td></tr>')
    tablo = (f'<div style="overflow-x:auto;"><table>'
             f'<tr><th>Personel</th><th>Tür</th><th>Tarih</th><th>Rapor Günü</th>'
             f'<th>İşveren (ilk 2)</th><th>SGK Günü</th></tr>{sat}'
             f'<tr style="font-weight:600;"><td>TOPLAM</td><td></td><td></td>'
             f'<td style="text-align:right">{sgk["toplam_gun"]}</td>'
             f'<td style="text-align:right">{sgk["toplam_isveren_gun"]}</td>'
             f'<td style="text-align:right">{sgk["toplam_sgk_gun"]}</td></tr></table></div>')

    if sgk["uyarilar"]:
        li = "".join(f'<li style="margin:5px 0;color:var(--text-muted);font-size:13px;">{u["ac"]}</li>'
                     for u in sgk["uyarilar"])
        uyari = (f'<h4 style="font-family:\'Outfit\',sans-serif;font-size:14px;margin:14px 0 6px;">'
                 f'<i class="fa-solid fa-triangle-exclamation" style="color:var(--accent-gold)"></i> '
                 f'Yapılacaklar / Uyarılar <span class="badge">{len(sgk["uyarilar"])}</span></h4>'
                 f'<ul style="padding-left:18px;margin:0;">{li}</ul>'
                 f'<p style="margin-top:8px;font-size:12px;color:var(--text-muted);">Kontrol amaçlıdır; '
                 f'fiş/bildirim otomatik yapılmaz, son onay ve kayıt sizdedir.</p>')
    else:
        uyari = ('<div class="notif-pill" style="margin-top:12px;"><div class="circle-icon-badge"></div>'
                 '<span>SGK rapor günleri ile bordro tutarlı görünüyor.</span></div>')

    return (f'<div class="filtre-bolum" data-grup="all" style="margin-top:24px;">'
            f'<h3 style="font-family:\'Outfit\',sans-serif;font-size:16px;margin-bottom:6px;">'
            f'<i class="fa-solid fa-notes-medical" style="color:var(--accent-gold)"></i> SGK Rapor Kontrolü '
            f'<span class="badge {"warn" if sgk["bulgu"] else "success"}" style="margin-left:8px;">{sgk["bulgu"]} uyarı</span></h3>'
            f'<p style="margin-bottom:10px;font-size:12px;color:var(--text-muted);">{sgk["personel_sayisi"]} raporlu personel · '
            f'toplam {sgk["toplam_gun"]} gün · SGK eksik gün bildirimi: {sgk["toplam_eksik_gun"]} gün (kod 01).</p>'
            f'{tablo}{uyari}</div>')


def panel_html(sonuc):
    if not sonuc.get("hazir"):
        return _yukleme_alani()
    if sonuc.get("hata"):
        return (_yukleme_alani() +
                f'<p style="margin-top:16px;color:var(--accent-rose);">Okuma hatası: {sonuc["hata"]}</p>')

    t = sonuc["toplam"]
    k_uyumsuz = sum(1 for k in sonuc["karsilastirma"] if not k["uyumlu"])
    s_uyumsuz = sum(1 for k in sonuc["soft"] if not k["uyumlu"])
    kaynak = ("mizan ile mutabakat" if sonuc["mizan_var"]
              else "mizan yok — yalnızca iç tutarlılık")
    ust = f"""
    <div class="panel-header">
      <div class="panel-title"><h2><i class="fa-solid fa-users-gear"></i> {AD}</h2>
      <p>{sonuc['personel_sayisi']} personel · brüt {_tl(t['brut'])} · net {_tl(t['net'])} · {kaynak}</p></div>
      <div class="panel-header-icon"><i class="fa-solid fa-users-gear"></i></div>
    </div>
    <div class="stats-grid" style="margin-bottom:8px;">
      <div class="stat-card {'rose' if k_uyumsuz else 'emerald'} filtre-kart" data-hedef="kesin" onclick="bulguFiltrele('kesin', this)"><div class="stat-header"><span>Mutabakat Farkı</span><i class="fa-solid fa-scale-balanced" style="color:var(--accent-rose)"></i></div><div class="stat-val">{k_uyumsuz}</div><div class="stat-desc"><span class="ipucu">335/361 kesin</span></div></div>
      <div class="stat-card gold filtre-kart" data-hedef="soft" onclick="bulguFiltrele('soft', this)"><div class="stat-header"><span>Tahakkuk Uyarısı</span><i class="fa-solid fa-triangle-exclamation" style="color:var(--accent-gold)"></i></div><div class="stat-val">{s_uyumsuz}</div><div class="stat-desc"><span class="ipucu">360/gider soft</span></div></div>
      <div class="stat-card {'rose' if sonuc['ic_kontrol'] else ''} filtre-kart" data-hedef="ic" onclick="bulguFiltrele('ic', this)"><div class="stat-header"><span>İç Tutarlılık</span><i class="fa-solid fa-calculator" style="color:var(--accent-cyan)"></i></div><div class="stat-val">{len(sonuc['ic_kontrol'])}</div><div class="stat-desc"><span class="ipucu">brüt−kesinti=net</span></div></div>
      <div class="stat-card emerald filtre-kart aktif" data-hedef="all" onclick="bulguFiltrele('all', this)"><div class="stat-header"><span>Toplam Bulgu</span><i class="fa-solid fa-list-check" style="color:var(--accent-emerald)"></i></div><div class="stat-val">{sonuc['bulgu']}</div><div class="stat-desc"><span class="ipucu">Tümünü göster</span></div></div>
    </div>
    <div style="margin:8px 0 4px;display:flex;gap:8px;flex-wrap:wrap;"><button class="btn-sec" onclick="document.getElementById('bordro-yeni').click()"><i class="fa-solid fa-rotate"></i> Farklı Bordro Yükle</button>
    <input type="file" id="bordro-yeni" accept=".xls,.xlsx,.xlsm" style="display:none" onchange="yukleDosya('m12_bordro','bordro-yeni','icmal')">
    <button class="btn-sec" onclick="document.getElementById('sgk-yeni').click()"><i class="fa-solid fa-notes-medical"></i> SGK Rapor Dökümü</button>
    <input type="file" id="sgk-yeni" accept=".xls,.xlsx,.xlsm" style="display:none" onchange="yukleDosya('m12_bordro','sgk-yeni','sgk')"></div>"""

    bloklar = ""
    # Kesin mutabakat (335/361)
    if sonuc["karsilastirma"]:
        sat = "".join(_kiyas_satir(k) for k in sonuc["karsilastirma"])
        bloklar += f"""<div class="filtre-bolum" data-grup="kesin" style="margin-top:24px;">
          <h3 style="font-family:'Outfit',sans-serif;font-size:16px;margin-bottom:12px;">
          <i class="fa-solid fa-scale-balanced" style="color:var(--accent-cyan)"></i> Bordro ↔ Mizan Mutabakatı
          <span class="badge {'warn' if k_uyumsuz else 'success'}" style="margin-left:8px;">{k_uyumsuz} fark</span></h3>
          <div style="overflow-x:auto;"><table>
          <tr><th>Durum</th><th>Kalem</th><th>Hesap</th><th>Bordro</th><th>Mizan</th><th>Fark</th></tr>{sat}</table></div></div>"""
    # Soft (360 / gider)
    if sonuc["soft"]:
        sat = "".join(_soft_satir(k) for k in sonuc["soft"])
        bloklar += f"""<div class="filtre-bolum" data-grup="soft" style="margin-top:24px;">
          <h3 style="font-family:'Outfit',sans-serif;font-size:16px;margin-bottom:12px;">
          <i class="fa-solid fa-triangle-exclamation" style="color:var(--accent-gold)"></i> Tahakkuk Kontrolü (karışık hesaplar — soft)
          <span class="badge {'warn' if s_uyumsuz else 'success'}" style="margin-left:8px;">{s_uyumsuz}</span></h3>
          <div style="overflow-x:auto;"><table>
          <tr><th>Durum</th><th>Kalem</th><th>Bordro</th><th>Mizan</th><th>Açıklama</th></tr>{sat}</table></div></div>"""
    # Ic kontrol
    if sonuc["ic_kontrol"]:
        sat = "".join(f'<tr><td><span class="badge err">tutarsız</span></td><td>{x["ac"]}</td></tr>'
                      for x in sonuc["ic_kontrol"])
        bloklar += f"""<div class="filtre-bolum" data-grup="ic" style="margin-top:24px;">
          <h3 style="font-family:'Outfit',sans-serif;font-size:16px;margin-bottom:12px;">
          <i class="fa-solid fa-calculator" style="color:var(--accent-rose)"></i> Bordro İç Tutarlılığı
          <span class="badge warn" style="margin-left:8px;">{len(sonuc['ic_kontrol'])}</span></h3>
          <div style="overflow-x:auto;"><table>{sat}</table></div></div>"""

    if not sonuc["mizan_var"]:
        bloklar += ('<div class="notif-pill" style="margin-top:16px;">'
                    '<i class="fa-solid fa-circle-info" style="color:var(--accent-cyan)"></i>'
                    '<span>Mizan yüklenirse net/SGK/vergi mutabakatı da otomatik yapılır.</span></div>')

    if sonuc["bulgu"] == 0 and sonuc["mizan_var"]:
        bloklar += ('<div class="notif-pill" style="margin-top:16px;"><div class="circle-icon-badge"></div>'
                    '<span>Bordro ve muhasebe mutabık — fark yok.</span></div>')
    return ust + bloklar + _sgk_blok(sonuc.get("sgk"))


kaydet(Modul("m12_bordro", AD, "fa-users-gear", 3, calistir, panel_html))
