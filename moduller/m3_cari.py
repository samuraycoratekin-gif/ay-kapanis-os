# -*- coding: utf-8 -*-
"""M3 - Cari Mutabakat.

HAFIF mod (varsayilan, Ay Kapanis OS tek basina): bizim defter + karsi ekstre
net bakiye karsilastirmasi. Kapanis icin "hangi cari incelenmeli" sinyali.

DERIN mod (musteri Akilli Mutabakat urunune de sahipse): komsu Mutabakat_AI
motoru belge duzeyinde EXACT/FUZZY/TUTAR_FARKI/SUBSET_SUM/EKSIK uretir.

Iki dosya yuklenir: rol="bizim" ve rol="karsi".
"""
import calendar
from core.moduller import Modul, kaydet
from core import depo, cari_oku, cari_analiz

AD = "Cari Mutabakat"


def _donem_sonu(donem):
    try:
        y, a = donem.split("-")[:2]
        son = calendar.monthrange(int(y), int(a))[1]
        from datetime import date
        return date(int(y), int(a), son)
    except Exception:
        return None
ACIKLAMA = "Bizim defter ile karşı tarafın ekstresi. Akıllı Mutabakat varsa belge düzeyinde derin analiz açılır."


def calistir(musteri_id, donem):
    bizim_yol = depo.yuklenen_bul(musteri_id, donem, "m3_cari", rol="bizim")
    karsi_yol = depo.yuklenen_bul(musteri_id, donem, "m3_cari", rol="karsi")
    m = depo.musteri_getir(musteri_id) or {}
    derin_acik = bool(m.get("akilli_mutabakat")) and cari_analiz.motor_var()

    if not (bizim_yol and karsi_yol):
        depo.modul_durum_guncelle(musteri_id, donem, "m3_cari",
                                  durum="bekliyor", ilerleme=0, bulgu_sayisi=0)
        return {"hazir": False, "bizim": bool(bizim_yol), "karsi": bool(karsi_yol),
                "derin_acik": derin_acik, "motor_var": cari_analiz.motor_var(),
                "mutabakat_sahip": bool(m.get("akilli_mutabakat"))}
    try:
        bizim = cari_oku.oku(bizim_yol)
        karsi = cari_oku.oku(karsi_yol)
        if derin_acik:
            r = cari_analiz.derin(bizim, karsi)
        else:
            r = cari_analiz.hafif(bizim, karsi)
        r["yaslandirma"] = cari_analiz.yaslandirma(bizim, _donem_sonu(donem))
    except Exception as e:
        depo.modul_durum_guncelle(musteri_id, donem, "m3_cari",
                                  durum="hata", ilerleme=0, bulgu_sayisi=0)
        return {"hazir": True, "hata": str(e), "derin_acik": derin_acik,
                "motor_var": cari_analiz.motor_var(),
                "mutabakat_sahip": bool(m.get("akilli_mutabakat"))}

    sorunlu = r["sorunlu"]
    depo.modul_durum_guncelle(musteri_id, donem, "m3_cari",
                              durum=("tamam" if sorunlu == 0 else "uyari"),
                              ilerleme=(100 if sorunlu == 0 else 60),
                              bulgu_sayisi=sorunlu)
    r["hazir"] = True
    r["derin_acik"] = derin_acik
    r["motor_var"] = cari_analiz.motor_var()
    r["mutabakat_sahip"] = bool(m.get("akilli_mutabakat"))
    r["_mid"] = musteri_id
    r["_donem"] = donem
    return r


# --------------------------------------------------------------------------- #
def _tl(v):
    return f"{v:,.2f} TL".replace(",", "X").replace(".", ",").replace("X", ".")


def _slot(rol, etiket, var):
    durum = ('<span style="color:var(--accent-emerald)"><i class="fa-solid fa-circle-check"></i> yüklendi</span>'
             if var else '<span style="color:var(--text-muted)">bekliyor</span>')
    iid = f"cari-{rol}"
    return f"""
    <div style="flex:1; min-width:240px; text-align:center; padding:28px 18px;
                border:2px dashed rgba(255,255,255,0.1); border-radius:16px; background:rgba(7,10,19,0.3);">
      <i class="fa-solid fa-file-excel" style="font-size:32px; color:var(--accent-cyan); margin-bottom:12px;"></i>
      <p style="font-weight:600; margin-bottom:4px;">{etiket}</p>
      <p style="margin-bottom:14px; font-size:12px;">{durum}</p>
      <input type="file" id="{iid}" accept=".xls,.xlsx,.xlsm" style="display:none"
             onchange="yukleDosya('m3_cari','{iid}','{rol}')">
      <button class="btn-sec" onclick="document.getElementById('{iid}').click()">
        <i class="fa-solid fa-upload"></i> {'Değiştir' if var else 'Yükle'}
      </button>
    </div>"""


def _baslik():
    return f"""
    <div class="panel-header">
      <div class="panel-title"><h2><i class="fa-solid fa-handshake"></i> {AD}</h2>
      <p>{ACIKLAMA}</p></div>
      <div class="panel-header-icon"><i class="fa-solid fa-handshake"></i></div>
    </div>"""


def _mod_serit(sonuc):
    """Hafif/derin mod durumu + capraz satis kopru seridi."""
    if sonuc.get("derin_acik"):
        return ('<div class="notif-pill" style="margin:8px 0 16px;">'
                '<div class="circle-icon-badge" style="background:var(--accent-emerald)"></div>'
                '<span><strong>Derin Mod aktif</strong> — Akıllı Mutabakat motoru belge düzeyinde eşleştiriyor.</span>'
                '<button class="btn-sec" style="margin-left:auto" onclick="mutabakatModu(false)">Hafif moda geç</button></div>')
    # hafif mod; sahiplik var ama motor yoksa veya kapaliysa farkli mesaj
    if sonuc.get("mutabakat_sahip") and not sonuc.get("motor_var"):
        ek = ' (Akıllı Mutabakat motoru bu bilgisayarda bulunamadı.)'
    else:
        ek = ''
    capraz = ''
    if not sonuc.get("mutabakat_sahip"):
        capraz = ('<button class="btn" style="margin-left:auto" onclick="mutabakatModu(true)">'
                  '<i class="fa-solid fa-bolt"></i> Derin analizi dene</button>')
    elif sonuc.get("motor_var"):
        capraz = ('<button class="btn" style="margin-left:auto" onclick="mutabakatModu(true)">'
                  '<i class="fa-solid fa-bolt"></i> Derin moda geç</button>')
    return (f'<div class="notif-pill" style="margin:8px 0 16px;">'
            f'<div class="circle-icon-badge" style="background:var(--accent-gold)"></div>'
            f'<span><strong>Hafif Mod</strong> — net bakiye farkı taraması.{ek} '
            f'Belge düzeyi eşleştirme için Akıllı Mutabakat gerekir.</span>{capraz}</div>')


def _yukleme_alani(sonuc):
    return (_baslik() + _mod_serit(sonuc) +
            '<div style="display:flex; gap:16px; flex-wrap:wrap;">' +
            _slot("bizim", "Bizim Defter / Ekstre", sonuc.get("bizim")) +
            _slot("karsi", "Karşı Taraf Ekstresi", sonuc.get("karsi")) +
            '</div>' +
            '<p id="yukleme-durum" style="margin-top:14px; font-size:12px; color:var(--accent-cyan);"></p>')


def _yeniden_serit():
    return ('<div style="margin:8px 0 4px; display:flex; gap:8px;">'
            '<button class="btn-sec" onclick="document.getElementById(\'cari-bizim\').click()"><i class="fa-solid fa-rotate"></i> Bizim defteri değiştir</button>'
            '<input type="file" id="cari-bizim" accept=".xls,.xlsx,.xlsm" style="display:none" onchange="yukleDosya(\'m3_cari\',\'cari-bizim\',\'bizim\')">'
            '<button class="btn-sec" onclick="document.getElementById(\'cari-karsi\').click()"><i class="fa-solid fa-rotate"></i> Karşı ekstreyi değiştir</button>'
            '<input type="file" id="cari-karsi" accept=".xls,.xlsx,.xlsm" style="display:none" onchange="yukleDosya(\'m3_cari\',\'cari-karsi\',\'karsi\')"></div>')


def _bos_pill(metin):
    return ('<div class="notif-pill" style="margin-top:12px;"><div class="circle-icon-badge"></div>'
            f'<span>{metin}</span></div>')


_KOVA_RENK = {"0-30": "var(--accent-emerald)", "31-60": "var(--accent-cyan)",
              "61-90": "var(--accent-gold)", "90+": "var(--accent-rose)",
              "tarihsiz": "var(--text-muted)"}


def _yaslandirma_blok(sonuc, mid, donem):
    y = sonuc.get("yaslandirma")
    if not y or not y.get("cariler"):
        return ""
    kovalar = y["kovalar"]
    ozet_kart = "".join(
        f'<div style="flex:1;min-width:130px;padding:12px 14px;border:1px solid rgba(255,255,255,0.08);'
        f'border-radius:12px;background:rgba(7,10,19,0.3);">'
        f'<div style="font-size:12px;color:var(--text-muted);">{e} gün</div>'
        f'<div style="font-size:16px;font-weight:700;color:{_KOVA_RENK[e]};">{_tl(kovalar[e])}</div></div>'
        for e in cari_analiz.KOVA_ETIKET)
    sat = ""
    for c in y["cariler"]:
        hucre = "".join(
            f'<td style="text-align:right;{("color:"+_KOVA_RENK[e]) if c["kovalar"][e] else "color:var(--text-muted)"}">'
            f'{_tl(c["kovalar"][e]) if c["kovalar"][e] else "—"}</td>'
            for e in cari_analiz.KOVA_ETIKET)
        gecmis = ('<span class="badge err">vadesi geçen</span>'
                  if c["en_eski_gun"] > 60 else
                  ('<span class="badge warn">izlenmeli</span>' if c["en_eski_gun"] > 30
                   else '<span class="badge success">güncel</span>'))
        mektup = (f'<a class="btn-sec" style="padding:4px 10px;font-size:12px;" target="_blank" '
                  f'href="/cari_mektup?m={mid}&d={donem}&cari={c["cari_kodu"]}">'
                  f'<i class="fa-solid fa-envelope"></i> Mektup</a>')
        sat += (f'<tr><td><span class="badge neutral">{c["cari_kodu"]}</span></td>'
                f'<td><strong>{c["cari_adi"]}</strong></td>{hucre}'
                f'<td style="text-align:right;font-weight:600;">{_tl(c["net"])}</td>'
                f'<td style="text-align:center;">{gecmis}</td><td>{mektup}</td></tr>')
    th = "".join(f'<th style="text-align:right">{e}</th>' for e in cari_analiz.KOVA_ETIKET)
    tablo = (f'<div style="overflow-x:auto;"><table>'
             f'<tr><th>Kod</th><th>Cari</th>{th}<th style="text-align:right">Net Açık</th>'
             f'<th style="text-align:center">Durum</th><th>Mutabakat</th></tr>{sat}</table></div>')
    toplu = (f'<div style="margin:10px 0;"><a class="btn" target="_blank" '
             f'href="/cari_mektup?m={mid}&d={donem}&cari=__hepsi__">'
             f'<i class="fa-solid fa-envelopes-bulk"></i> Tüm Carilere Mutabakat Mektubu (yazdır / PDF)</a></div>')
    return f"""
    <div class="filtre-bolum" data-grup="yaslandirma" style="margin-top:24px;">
      <h3 style="font-family:'Outfit',sans-serif;font-size:16px;margin-bottom:12px;">
        <i class="fa-solid fa-hourglass-half" style="color:var(--accent-gold)"></i> Cari Yaşlandırma
        <span style="font-size:12px;color:var(--text-muted);font-weight:400;margin-left:8px;">{y["bugun"]} itibarıyla</span></h3>
      <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px;">{ozet_kart}</div>
      {toplu}{tablo}
    </div>"""


def _panel_hafif(sonuc):
    stat = f"""
    <div class="stats-grid" style="margin-bottom:8px;">
      <div class="stat-card filtre-kart aktif" data-hedef="all" onclick="bulguFiltrele('all', this)"><div class="stat-header"><span>Toplam Cari</span><i class="fa-solid fa-users" style="color:var(--accent-cyan)"></i></div><div class="stat-val">{sonuc['cari_sayisi']}</div><div class="stat-desc"><span class="ipucu">Tümünü göster</span></div></div>
      <div class="stat-card emerald filtre-kart" data-hedef="mutabik" onclick="bulguFiltrele('mutabik', this)"><div class="stat-header"><span>Mutabık</span><i class="fa-solid fa-circle-check" style="color:var(--accent-emerald)"></i></div><div class="stat-val">{len(sonuc['mutabik'])}</div><div class="stat-desc"><span class="ipucu">Görmek için tıkla</span></div></div>
      <div class="stat-card rose filtre-kart" data-hedef="farkli" onclick="bulguFiltrele('farkli', this)"><div class="stat-header"><span>Bakiye Farklı</span><i class="fa-solid fa-not-equal" style="color:var(--accent-rose)"></i></div><div class="stat-val">{len(sonuc['farkli'])}</div><div class="stat-desc"><span class="ipucu">Görmek için tıkla</span></div></div>
      <div class="stat-card gold filtre-kart" data-hedef="tek_taraf" onclick="bulguFiltrele('tek_taraf', this)"><div class="stat-header"><span>Tek Tarafta</span><i class="fa-solid fa-user-slash" style="color:var(--accent-gold)"></i></div><div class="stat-val">{len(sonuc['tek_taraf'])}</div><div class="stat-desc"><span class="ipucu">Görmek için tıkla</span></div></div>
    </div>"""

    # Mutabik blok
    if sonuc["mutabik"]:
        satir = "".join(
            f'<tr><td><span class="badge success">{x["cari_kodu"]}</span></td><td><strong>{x["cari_adi"]}</strong></td>'
            f'<td>{_tl(x["net"])}</td><td>{_tl(x["net"])}</td></tr>'
            for x in sonuc["mutabik"])
        mut_govde = (f'<div style="overflow-x:auto;"><table>'
                     f'<tr><th>Kod</th><th>Cari</th><th>Bizim Net</th><th>Karşı Net</th></tr>{satir}</table></div>')
    else:
        mut_govde = _bos_pill("Mutabık cari yok.")
    b_mutabik = f"""
    <div class="filtre-bolum" data-grup="mutabik" style="margin-top:24px;"><h3 style="font-family:'Outfit',sans-serif;font-size:16px;margin-bottom:12px;">
      <i class="fa-solid fa-circle-check" style="color:var(--accent-emerald)"></i> Mutabık Cariler
      <span class="badge {'success' if sonuc['mutabik'] else 'warn'}" style="margin-left:8px;">{len(sonuc['mutabik'])}</span></h3>{mut_govde}</div>"""

    # Bakiye farkli blok
    if sonuc["farkli"]:
        satir = "".join(
            f'<tr><td><span class="badge err">{x["cari_kodu"]}</span></td><td><strong>{x["cari_adi"]}</strong></td>'
            f'<td>{_tl(x["bizim_net"])}</td><td>{_tl(x["karsi_net"])}</td>'
            f'<td style="color:var(--accent-rose)">{_tl(x["fark"])}</td></tr>'
            for x in sonuc["farkli"])
        f_govde = (f'<div style="overflow-x:auto;"><table>'
                   f'<tr><th>Kod</th><th>Cari</th><th>Bizim Net</th><th>Karşı Net</th><th>Fark</th></tr>{satir}</table></div>')
    else:
        f_govde = _bos_pill("Bakiye farklı cari yok.")
    b_farkli = f"""
    <div class="filtre-bolum" data-grup="farkli" style="margin-top:24px;"><h3 style="font-family:'Outfit',sans-serif;font-size:16px;margin-bottom:12px;">
      <i class="fa-solid fa-not-equal" style="color:var(--accent-rose)"></i> Bakiye Farklı Cariler
      <span class="badge {'warn' if sonuc['farkli'] else 'success'}" style="margin-left:8px;">{len(sonuc['farkli'])}</span></h3>{f_govde}</div>"""

    # Tek tarafta blok
    if sonuc["tek_taraf"]:
        satir = "".join(
            f'<tr><td><span class="badge neutral">{x["cari_kodu"]}</span></td><td><strong>{x["cari_adi"]}</strong></td>'
            f'<td>{"yalnız bizde" if x["taraf"]=="bizde" else "yalnız karşıda"}</td>'
            f'<td>{_tl(x["bizim_net"] if x["taraf"]=="bizde" else x["karsi_net"])}</td>'
            f'<td>{x["kalem"]} kalem</td></tr>'
            for x in sonuc["tek_taraf"])
        t_govde = (f'<div style="overflow-x:auto;"><table>'
                   f'<tr><th>Kod</th><th>Cari</th><th>Durum</th><th>Net</th><th>Kalem</th></tr>{satir}</table></div>')
    else:
        t_govde = _bos_pill("Tek tarafta görünen cari yok.")
    b_tek = f"""
    <div class="filtre-bolum" data-grup="tek_taraf" style="margin-top:24px;"><h3 style="font-family:'Outfit',sans-serif;font-size:16px;margin-bottom:12px;">
      <i class="fa-solid fa-user-slash" style="color:var(--accent-gold)"></i> Tek Tarafta Görünen Cariler
      <span class="badge {'warn' if sonuc['tek_taraf'] else 'success'}" style="margin-left:8px;">{len(sonuc['tek_taraf'])}</span></h3>{t_govde}</div>"""

    not_ = (f'<p style="margin-top:18px;color:var(--text-muted);font-size:13px;">Toplam tahmini açık: '
            f'<strong style="color:var(--accent-rose)">{_tl(sonuc["toplam_acik"])}</strong>. '
            f'Bu farkların hangi belgelerden kaynaklandığını görmek için Derin Mod (Akıllı Mutabakat) gerekir.</p>')
    return stat + b_mutabik + b_farkli + b_tek + not_


_DURUM_RENK = {"MUTABIK": ("success", "var(--accent-emerald)"),
               "TUTAR FARKLI": ("warn", "var(--accent-gold)"),
               "EKSIK BELGE": ("err", "var(--accent-rose)")}


_DURUM_GRUP = {"MUTABIK": "mutabik", "TUTAR FARKLI": "tutar", "EKSIK BELGE": "eksik"}


def _panel_derin(sonuc):
    s = sonuc["sayac"]
    stat = f"""
    <div class="stats-grid" style="margin-bottom:8px;">
      <div class="stat-card filtre-kart aktif" data-hedef="all" onclick="bulguFiltrele('all', this)"><div class="stat-header"><span>Toplam Cari</span><i class="fa-solid fa-users" style="color:var(--accent-cyan)"></i></div><div class="stat-val">{sonuc['cari_sayisi']}</div><div class="stat-desc"><span class="ipucu">Tümünü göster</span></div></div>
      <div class="stat-card emerald filtre-kart" data-hedef="mutabik" onclick="bulguFiltrele('mutabik', this)"><div class="stat-header"><span>Mutabık</span><i class="fa-solid fa-circle-check" style="color:var(--accent-emerald)"></i></div><div class="stat-val">{s.get('MUTABIK',0)}</div><div class="stat-desc"><span class="ipucu">Görmek için tıkla</span></div></div>
      <div class="stat-card gold filtre-kart" data-hedef="tutar" onclick="bulguFiltrele('tutar', this)"><div class="stat-header"><span>Tutar Farklı</span><i class="fa-solid fa-scale-unbalanced" style="color:var(--accent-gold)"></i></div><div class="stat-val">{s.get('TUTAR FARKLI',0)}</div><div class="stat-desc"><span class="ipucu">Görmek için tıkla</span></div></div>
      <div class="stat-card rose filtre-kart" data-hedef="eksik" onclick="bulguFiltrele('eksik', this)"><div class="stat-header"><span>Eksik Belge</span><i class="fa-solid fa-file-circle-xmark" style="color:var(--accent-rose)"></i></div><div class="stat-val">{s.get('EKSIK BELGE',0)}</div><div class="stat-desc"><span class="ipucu">Görmek için tıkla</span></div></div>
    </div>"""
    kartlar = ""
    for c in sonuc["cariler"]:
        grup = _DURUM_GRUP.get(c["durum"], "tutar")
        rozet, renk = _DURUM_RENK.get(c["durum"], ("neutral", "var(--text-muted)"))
        if c["durum"] == "MUTABIK":
            detay = '<li style="margin:4px 0;color:var(--text-muted);font-size:13px;">Belge düzeyinde mutabık.</li>'
        else:
            detay = "".join(
                f'<li style="margin:4px 0;color:var(--text-muted);font-size:13px;">{b["aciklama"]}</li>'
                for b in c["bulgular"] if b["tip"] not in ("EXACT", "FUZZY", "SUBSET_SUM"))
        kartlar += f"""
        <div class="filtre-bolum" data-grup="{grup}" style="margin-top:16px;padding:16px;border:1px solid rgba(255,255,255,0.08);border-radius:14px;background:rgba(7,10,19,0.3);">
          <div style="display:flex;align-items:center;gap:10px;">
            <span class="badge {rozet}">{c["durum"]}</span>
            <strong>{c["cari_kodu"]} · {c["cari_adi"]}</strong>
            <span style="margin-left:auto;color:{renk}">açık: {_tl(c["acik"])}</span></div>
          <ul style="margin:8px 0 0;padding-left:18px;">{detay}</ul></div>"""
    if not kartlar:
        kartlar = ('<div class="notif-pill" style="margin-top:16px;"><div class="circle-icon-badge"></div>'
                   '<span>Tüm cariler belge düzeyinde mutabık.</span></div>')
    return stat + kartlar


def panel_html(sonuc):
    if not sonuc.get("hazir"):
        return _yukleme_alani(sonuc)
    if sonuc.get("hata"):
        return (_baslik() + _yeniden_serit() +
                f'<p style="margin-top:16px;color:var(--accent-rose);">Okuma hatası: {sonuc["hata"]}</p>')
    ust = _baslik() + _mod_serit(sonuc) + _yeniden_serit()
    yas = _yaslandirma_blok(sonuc, sonuc.get("_mid", ""), sonuc.get("_donem", ""))
    if sonuc.get("mod") == "derin":
        return ust + _panel_derin(sonuc) + yas
    return ust + _panel_hafif(sonuc) + yas


kaydet(Modul("m3_cari", AD, "fa-handshake", 2, calistir, panel_html))
