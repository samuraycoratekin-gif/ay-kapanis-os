# -*- coding: utf-8 -*-
"""M5 - Banka Ekstre Esleme (Asama 4).

Iki dosya: rol="banka" (banka ekstresi) ve rol="defter" (ERP 102 banka hareketleri).
Tutar+tarih eslestirmesi; eslesmeyenlere fis onerisi, komisyon/masraf tespiti.
"""
from core.moduller import Modul, kaydet
from core import depo, banka_oku, banka_analiz, kredi_oku, kredi_analiz

AD = "Banka Ekstre Eşleme"
ACIKLAMA = "Banka ekstresi ↔ ERP 102 banka hareketleri eşleştirilir; eşleşmeyenlere fiş önerilir."


def _kredi_oku(musteri_id, donem):
    """Kredi odeme plani (bagimsiz slot) varsa analiz et; yoksa None."""
    kredi_yol = depo.yuklenen_bul(musteri_id, donem, "m5_banka", rol="kredi")
    if not kredi_yol:
        return None
    try:
        krediler = kredi_oku.oku(kredi_yol)
        return kredi_analiz.analiz(krediler, donem)
    except Exception as e:
        return {"hata": str(e)}


def _kredi_bulgu(kredi):
    return kredi["bulgu"] if (kredi and not kredi.get("hata")) else 0


def calistir(musteri_id, donem):
    banka_yol = depo.yuklenen_bul(musteri_id, donem, "m5_banka", rol="banka")
    defter_yol = depo.yuklenen_bul(musteri_id, donem, "m5_banka", rol="defter")
    kredi = _kredi_oku(musteri_id, donem)
    kbulgu = _kredi_bulgu(kredi)
    if not (banka_yol and defter_yol):
        if kredi is None:
            durum, ilerleme = "bekliyor", 0
        elif kredi.get("hata"):
            durum, ilerleme = "hata", 0
        else:
            durum, ilerleme = (("uyari", 40) if kbulgu else ("tamam", 40))
        depo.modul_durum_guncelle(musteri_id, donem, "m5_banka",
                                  durum=durum, ilerleme=ilerleme, bulgu_sayisi=kbulgu)
        return {"hazir": False, "banka": bool(banka_yol), "defter": bool(defter_yol),
                "kredi": kredi}
    try:
        banka = banka_oku.oku(banka_yol, kaynak="banka")
        defter = banka_oku.oku(defter_yol, kaynak="defter")
        r = banka_analiz.esle(banka, defter)
    except Exception as e:
        depo.modul_durum_guncelle(musteri_id, donem, "m5_banka",
                                  durum="hata", ilerleme=0, bulgu_sayisi=0)
        return {"hazir": True, "hata": str(e), "kredi": kredi}
    toplam_bulgu = r["sorunlu"] + kbulgu
    depo.modul_durum_guncelle(musteri_id, donem, "m5_banka",
                              durum=("tamam" if toplam_bulgu == 0 else "uyari"),
                              ilerleme=(100 if toplam_bulgu == 0 else 60),
                              bulgu_sayisi=toplam_bulgu)
    r["hazir"] = True
    r["kredi"] = kredi
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
            _slot("kredi", "Kredi Ödeme Planı (opsiyonel)", bool(sonuc.get("kredi"))) +
            '</div><p id="yukleme-durum" style="margin-top:14px;font-size:12px;color:var(--accent-cyan);"></p>' +
            _kredi_blok(sonuc.get("kredi")))


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


def _kredi_slot_yeniden():
    var = True
    return ('<button class="btn-sec" onclick="document.getElementById(\'banka-kredi\').click()"><i class="fa-solid fa-rotate"></i> Kredi planını değiştir</button>'
            '<input type="file" id="banka-kredi" accept=".xls,.xlsx,.xlsm" style="display:none" onchange="yukleDosya(\'m5_banka\',\'banka-kredi\',\'kredi\')">')


def _kredi_blok(kredi):
    """Banka kredileri bolumu (m5 icine gomulu). kredi None ise kisa davet."""
    if not kredi:
        return ('<div class="filtre-bolum" data-grup="all" style="margin-top:24px;">'
                '<h3 style="font-family:\'Outfit\',sans-serif;font-size:16px;margin-bottom:8px;">'
                '<i class="fa-solid fa-landmark" style="color:var(--accent-gold)"></i> Banka Kredileri</h3>'
                '<p style="font-size:13px;color:var(--text-muted);">Kredi ödeme planı (amortisman tablosu) yüklerseniz '
                '300/400/303 sınıflaması, 400→303 reclass, dönem faizi (780/660) ve dövizli kur farkı (656/646) '
                'kontrolleri ve dönem fiş <strong>önerileri</strong> burada çıkar.</p></div>')
    if kredi.get("hata"):
        return ('<div class="filtre-bolum" data-grup="all" style="margin-top:24px;">'
                '<h3 style="font-family:\'Outfit\',sans-serif;font-size:16px;margin-bottom:8px;">'
                '<i class="fa-solid fa-landmark" style="color:var(--accent-gold)"></i> Banka Kredileri</h3>'
                f'<p style="color:var(--accent-rose);font-size:13px;">Kredi planı okuma hatası: {kredi["hata"]}</p>'
                f'<div style="margin-top:8px;">{_kredi_slot_yeniden()}</div></div>')

    t = kredi["toplam"]
    sat = ""
    for k in kredi["krediler"]:
        tip = ('<span class="badge neutral">uzun → 400/303</span>' if k["tip"] == "uzun"
               else ('<span class="badge neutral">kısa → 300</span>' if k["tip"] == "kisa"
                     else '<span class="badge warn">?</span>'))
        dv = "" if k["doviz"] in ("TL", "TRY", "") else f' <span class="badge warn">{k["doviz"]}</span>'
        sat += (f'<tr><td><strong>{k["ad"]}</strong>{dv}</td><td>{tip}</td>'
                f'<td style="text-align:right">{_tl(k["kalan"])}</td>'
                f'<td style="text-align:right">{_tl(k["cari"])}</td>'
                f'<td style="text-align:right">{_tl(k["uzun"])}</td>'
                f'<td style="text-align:right">{_tl(k["donem_faiz"])}</td></tr>')
    tablo = (f'<div style="overflow-x:auto;"><table>'
             f'<tr><th>Kredi</th><th>Tür</th><th>Kalan Anapara</th><th>Cari Kısım (≤12 ay)</th>'
             f'<th>Uzun Vade (>12 ay)</th><th>Dönem Faizi</th></tr>{sat}'
             f'<tr style="font-weight:600;"><td>TOPLAM</td><td></td>'
             f'<td style="text-align:right">{_tl(t["kalan"])}</td>'
             f'<td style="text-align:right">{_tl(t["cari"])}</td>'
             f'<td style="text-align:right">{_tl(t["uzun"])}</td>'
             f'<td style="text-align:right">{_tl(t["donem_faiz"])}</td></tr></table></div>')

    oneri = ""
    if kredi["oneriler"]:
        li = "".join(f'<li style="margin:5px 0;color:var(--text-muted);font-size:13px;">'
                     f'<span class="badge warn" style="margin-right:6px;">{o["hesap"]}</span>{o["ac"]}</li>'
                     for o in kredi["oneriler"])
        oneri = (f'<h4 style="font-family:\'Outfit\',sans-serif;font-size:14px;margin:14px 0 6px;">'
                 f'<i class="fa-solid fa-wand-magic-sparkles" style="color:var(--accent-cyan)"></i> '
                 f'Dönem Fiş Önerileri <span class="badge">{len(kredi["oneriler"])}</span></h4>'
                 f'<ul style="padding-left:18px;margin:0;">{li}</ul>'
                 f'<p style="margin-top:8px;font-size:12px;color:var(--text-muted);">Bu öneriler kontrol amaçlıdır; '
                 f'fiş otomatik atılmaz, son onay ve kayıt sizdedir.</p>')
    else:
        oneri = ('<div class="notif-pill" style="margin-top:12px;"><div class="circle-icon-badge"></div>'
                 '<span>Kredilerde dönem sonu için ek işlem (reclass/faiz/kur) gerekmiyor.</span></div>')

    return (f'<div class="filtre-bolum" data-grup="all" style="margin-top:24px;">'
            f'<h3 style="font-family:\'Outfit\',sans-serif;font-size:16px;margin-bottom:4px;">'
            f'<i class="fa-solid fa-landmark" style="color:var(--accent-gold)"></i> Banka Kredileri '
            f'<span class="badge {"warn" if kredi["bulgu"] else "success"}" style="margin-left:8px;">{kredi["bulgu"]} öneri</span></h3>'
            f'<p style="margin-bottom:10px;font-size:12px;color:var(--text-muted);">Dönem sonu: {kredi["donem_sonu"]} · '
            f'cari/uzun ayrımı bu tarihten itibaren 12 aylık pencereye göre.</p>'
            f'{tablo}{oneri}<div style="margin-top:10px;">{_kredi_slot_yeniden()}</div></div>')


def panel_html(sonuc):
    if not sonuc.get("hazir"):
        return _yukleme(sonuc)
    kredi_blok = _kredi_blok(sonuc.get("kredi"))
    if sonuc.get("hata"):
        return _baslik() + _yeniden() + f'<p style="margin-top:16px;color:var(--accent-rose);">Okuma hatası: {sonuc["hata"]}</p>' + kredi_blok

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
                '<span>Banka ekstresi ile defter tam eşleşti.</span></div>' + kredi_blok)

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
    return ust + stat + bloklar + oneri + kredi_blok


kaydet(Modul("m5_banka", AD, "fa-money-bill-transfer", 4, calistir, panel_html))
