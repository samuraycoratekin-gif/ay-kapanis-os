# -*- coding: utf-8 -*-
"""M5 - Banka Ekstre Esleme (Asama 4).

Iki dosya: rol="banka" (banka ekstresi) ve rol="defter" (ERP 102 banka hareketleri).
Tutar+tarih eslestirmesi; eslesmeyenlere fis onerisi, komisyon/masraf tespiti.
"""
from core.moduller import Modul, kaydet
from core import depo, banka_oku, banka_analiz

AD = "Banka Ekstre Eşleme"
ACIKLAMA = "Banka ekstresi ↔ ERP 102 banka hareketleri eşleştirilir; eşleşmeyenlere fiş önerilir."


def calistir(musteri_id, donem):
    banka_yol = depo.yuklenen_bul(musteri_id, donem, "m5_banka", rol="banka")
    defter_yol = depo.yuklenen_bul(musteri_id, donem, "m5_banka", rol="defter")
    if not (banka_yol and defter_yol):
        depo.modul_durum_guncelle(musteri_id, donem, "m5_banka",
                                  durum="bekliyor", ilerleme=0, bulgu_sayisi=0)
        return {"hazir": False, "banka": bool(banka_yol), "defter": bool(defter_yol)}
    try:
        banka = banka_oku.oku(banka_yol, kaynak="banka")
        defter = banka_oku.oku(defter_yol, kaynak="defter")
        r = banka_analiz.esle(banka, defter)
    except Exception as e:
        depo.modul_durum_guncelle(musteri_id, donem, "m5_banka",
                                  durum="hata", ilerleme=0, bulgu_sayisi=0)
        return {"hazir": True, "hata": str(e)}
    sorunlu = r["sorunlu"]
    depo.modul_durum_guncelle(musteri_id, donem, "m5_banka",
                              durum=("tamam" if sorunlu == 0 else "uyari"),
                              ilerleme=(100 if sorunlu == 0 else 60),
                              bulgu_sayisi=sorunlu)
    r["hazir"] = True
    return r


# --------------------------------------------------------------------------- #
def _tl(v):
    return f"{v:,.2f} TL".replace(",", "X").replace(".", ",").replace("X", ".")


def _baslik():
    return f"""
    <div class="panel-header">
      <div class="panel-title"><h2><i class="fa-solid fa-money-bill-transfer"></i> {AD}</h2>
      <p>{ACIKLAMA}</p></div>
      <div class="panel-header-icon"><i class="fa-solid fa-money-bill-transfer"></i></div>
    </div>"""


def _slot(rol, etiket, var):
    iid = f"banka-{rol}"
    durum = ('<span style="color:var(--accent-emerald)"><i class="fa-solid fa-circle-check"></i> yüklendi</span>'
             if var else '<span style="color:var(--text-muted)">bekliyor</span>')
    return f"""
    <div style="flex:1;min-width:240px;text-align:center;padding:28px 18px;border:2px dashed rgba(255,255,255,0.1);border-radius:16px;background:rgba(7,10,19,0.3);">
      <i class="fa-solid fa-file-invoice" style="font-size:32px;color:var(--accent-cyan);margin-bottom:12px;"></i>
      <p style="font-weight:600;margin-bottom:4px;">{etiket}</p>
      <p style="margin-bottom:14px;font-size:12px;">{durum}</p>
      <input type="file" id="{iid}" accept=".xls,.xlsx,.xlsm" style="display:none" onchange="yukleDosya('m5_banka','{iid}','{rol}')">
      <button class="btn-sec" onclick="document.getElementById('{iid}').click()"><i class="fa-solid fa-upload"></i> {'Değiştir' if var else 'Yükle'}</button>
    </div>"""


def _yukleme(sonuc):
    return (_baslik() +
            '<div style="display:flex;gap:16px;flex-wrap:wrap;">' +
            _slot("banka", "Banka Ekstresi", sonuc.get("banka")) +
            _slot("defter", "ERP 102 Banka Hareketleri", sonuc.get("defter")) +
            '</div><p id="yukleme-durum" style="margin-top:14px;font-size:12px;color:var(--accent-cyan);"></p>')


def _yeniden():
    return ('<div style="margin:8px 0 4px;display:flex;gap:8px;">'
            '<button class="btn-sec" onclick="document.getElementById(\'banka-banka\').click()"><i class="fa-solid fa-rotate"></i> Ekstreyi değiştir</button>'
            '<input type="file" id="banka-banka" accept=".xls,.xlsx,.xlsm" style="display:none" onchange="yukleDosya(\'m5_banka\',\'banka-banka\',\'banka\')">'
            '<button class="btn-sec" onclick="document.getElementById(\'banka-defter\').click()"><i class="fa-solid fa-rotate"></i> Defteri değiştir</button>'
            '<input type="file" id="banka-defter" accept=".xls,.xlsx,.xlsm" style="display:none" onchange="yukleDosya(\'m5_banka\',\'banka-defter\',\'defter\')"></div>')


def _liste(grup, baslik, ikon, renk, kalemler, satir):
    if kalemler:
        sat = "".join(satir(x) for x in kalemler)
        govde = f'<div style="overflow-x:auto;"><table>{sat}</table></div>'
        rozet = "warn"
    else:
        govde = ('<div class="notif-pill" style="margin-top:8px;"><div class="circle-icon-badge"></div>'
                 '<span>Bu kategoride bulgu yok.</span></div>')
        rozet = "success"
    return (f'<div class="filtre-bolum" data-grup="{grup}" style="margin-top:20px;"><h3 style="font-family:\'Outfit\',sans-serif;font-size:16px;margin-bottom:12px;">'
            f'<i class="fa-solid {ikon}" style="color:{renk}"></i> {baslik} '
            f'<span class="badge {rozet}" style="margin-left:8px;">{len(kalemler)}</span></h3>{govde}</div>')


def _bolum_coklu(sonuc):
    coklu = sonuc.get("coklu") or []
    if not coklu:
        return ""
    sat = ""
    for c in coklu:
        tek = c["tek"]
        cok_det = " + ".join(_tl(abs(x["tutar"])) for x in c["cok"])
        cok_ack = "; ".join((x["aciklama"] or "—") for x in c["cok"])
        sat += (f'<tr><td><span class="badge neutral">{c["yon"]}</span></td><td>{tek["tarih"]}</td>'
                f'<td><strong>{tek["aciklama"] or "—"}</strong> = {_tl(c["tutar"])}</td>'
                f'<td style="font-size:12px;color:var(--text-muted)">{c["adet"]} kalem: {cok_det}<br>{cok_ack}</td></tr>')
    return (f'<div class="filtre-bolum" data-grup="all" style="margin-top:20px;">'
            f'<h3 style="font-family:\'Outfit\',sans-serif;font-size:16px;margin-bottom:12px;">'
            f'<i class="fa-solid fa-layer-group" style="color:var(--accent-emerald)"></i> Toplu Hareket Eşleşmeleri (1:N / N:1) '
            f'<span class="badge success" style="margin-left:8px;">{len(coklu)}</span></h3>'
            f'<p style="margin-bottom:10px;font-size:13px;color:var(--text-muted)">Tek banka/defter satırı, karşı tarafta '
            f'birden çok kalemin toplamıyla eşleşti — yanlış "eksik kayıt" uyarısı verilmedi.</p>'
            f'<div style="overflow-x:auto;"><table>'
            f'<tr><th>Yön</th><th>Tarih</th><th>Toplu Hareket</th><th>Karşılığı</th></tr>{sat}</table></div></div>')


def panel_html(sonuc):
    if not sonuc.get("hazir"):
        return _yukleme(sonuc)
    if sonuc.get("hata"):
        return _baslik() + _yeniden() + f'<p style="margin-top:16px;color:var(--accent-rose);">Okuma hatası: {sonuc["hata"]}</p>'

    ust = _baslik() + _yeniden()
    stat = f"""
    <div class="stats-grid" style="margin-bottom:8px;">
      <div class="stat-card emerald filtre-kart aktif" data-hedef="all" onclick="bulguFiltrele('all', this)"><div class="stat-header"><span>Eşleşen</span><i class="fa-solid fa-circle-check" style="color:var(--accent-emerald)"></i></div><div class="stat-val">{sonuc['eslesen']}</div><div class="stat-desc"><span class="ipucu">{('+' + str(sonuc.get('coklu_sayisi',0)) + ' toplu') if sonuc.get('coklu_sayisi') else 'Tümünü göster'}</span></div></div>
      <div class="stat-card rose filtre-kart" data-hedef="banka_fazla" onclick="bulguFiltrele('banka_fazla', this)"><div class="stat-header"><span>Defterde Yok</span><i class="fa-solid fa-triangle-exclamation" style="color:var(--accent-rose)"></i></div><div class="stat-val">{len(sonuc['banka_fazla'])}</div><div class="stat-desc"><span class="ipucu">Görmek için tıkla</span></div></div>
      <div class="stat-card gold filtre-kart" data-hedef="komisyon" onclick="bulguFiltrele('komisyon', this)"><div class="stat-header"><span>Komisyon/Masraf</span><i class="fa-solid fa-coins" style="color:var(--accent-gold)"></i></div><div class="stat-val">{len(sonuc['komisyon'])}</div><div class="stat-desc"><span class="ipucu">Görmek için tıkla</span></div></div>
      <div class="stat-card filtre-kart" data-hedef="defter_fazla" onclick="bulguFiltrele('defter_fazla', this)"><div class="stat-header"><span>Bankada Yok</span><i class="fa-solid fa-ban" style="color:var(--accent-cyan)"></i></div><div class="stat-val">{len(sonuc['defter_fazla'])}</div><div class="stat-desc"><span class="ipucu">Görmek için tıkla</span></div></div>
    </div>"""

    coklu_blok = _bolum_coklu(sonuc)
    if sonuc["sorunlu"] == 0:
        return (ust + stat + coklu_blok +
                '<div class="notif-pill" style="margin-top:16px;"><div class="circle-icon-badge"></div>'
                '<span>Banka ekstresi ile defter tam eşleşti.</span></div>')

    bloklar = coklu_blok
    bloklar += _liste("banka_fazla", "Kaydı Olmayan Banka Hareketleri (fiş önerisi)", "fa-triangle-exclamation", "var(--accent-rose)",
                      sonuc["banka_fazla"],
                      lambda x: f'<tr><td>{x["tarih"]}</td><td>{x["aciklama"] or "—"}</td>'
                                f'<td style="color:{"var(--accent-emerald)" if x["tutar"]>0 else "var(--accent-rose)"}">{_tl(x["tutar"])}</td>'
                                f'<td>{"GİRİŞ" if x["tutar"]>0 else "ÇIKIŞ"}</td></tr>')
    bloklar += _liste("komisyon", "Komisyon / Masraf → Gider Fişi", "fa-coins", "var(--accent-gold)",
                      sonuc["komisyon"],
                      lambda x: f'<tr><td>{x["tarih"]}</td><td>{x["aciklama"] or "—"}</td>'
                                f'<td>{_tl(abs(x["tutar"]))}</td><td><span class="badge warn">770/780</span></td></tr>')
    bloklar += _liste("defter_fazla", "Bankada Görünmeyen Defter Kayıtları", "fa-ban", "var(--accent-cyan)",
                      sonuc["defter_fazla"],
                      lambda x: f'<tr><td>{x["tarih"]}</td><td>{x["aciklama"] or "—"}</td>'
                                f'<td>{_tl(x["tutar"])}</td><td>—</td></tr>')

    if sonuc.get("oneriler"):
        sat = "".join(f'<li style="margin:5px 0;color:var(--text-muted);font-size:13px;">{o["ac"]}</li>' for o in sonuc["oneriler"])
        oneri = (f'<div style="margin-top:20px;"><h3 style="font-family:\'Outfit\',sans-serif;font-size:16px;margin-bottom:10px;">'
                 f'<i class="fa-solid fa-wand-magic-sparkles" style="color:var(--accent-cyan)"></i> Otomatik Fiş Önerileri '
                 f'<span class="badge">{len(sonuc["oneriler"])}</span></h3>'
                 f'<ul style="padding-left:18px;margin:0;">{sat}</ul>'
                 f'<p style="margin-top:8px;font-size:12px;color:var(--text-muted);">Fişler son aşamada önizlenip onayınızla ERP\'ye gönderilecek.</p></div>')
    else:
        oneri = ""
    return ust + stat + bloklar + oneri


kaydet(Modul("m5_banka", AD, "fa-money-bill-transfer", 4, calistir, panel_html))
