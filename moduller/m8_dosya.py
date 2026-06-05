# -*- coding: utf-8 -*-
"""M8 - Kapanis Dosyasi + Audit Trail.

Tum modulleri yeniden calistirip kapanis hazirlik ozetini cikarir:
  - Kapanis Kontrol Listesi (her modul: durum, ilerleme, bulgu)
  - "Kapanisa hazir mi?" karari ve engelleyen kalemler
  - Audit Trail: fis onay/gonderme islemleri (kim-ne-zaman izi)
  - Tek tikla yazdirilabilir KAPANIS RAPORU (ayri sayfa)
"""
from core.moduller import Modul, kaydet, liste, getir
from core import depo

AD = "Kapanış Dosyası & Audit Trail"
ACIKLAMA = "Tüm modül bulgularını birleştiren kapanış raporu ve kim-ne-zaman-onayladı izi."

DURUM_ET = {"tamam": ("Tamamlandı", "success", "fa-circle-check"),
            "uyari": ("Bulgu Var", "warn", "fa-triangle-exclamation"),
            "bekliyor": ("Bekliyor", "neutral", "fa-hourglass")}


def calistir(musteri_id, donem):
    # Tum modulleri (M8 haric) yeniden calistir -> durumlar guncellensin
    fisler = []
    for mod in liste():
        if mod.kod == "m8_dosya":
            continue
        try:
            sonuc = mod.calistir(musteri_id, donem)
            if mod.kod == "m6_fis":
                fisler = sonuc.get("fisler", [])
        except Exception:
            pass

    durum = depo.donem_getir(musteri_id, donem, [m.kod for m in liste()])
    satirlar = []
    for mod in liste():
        if mod.kod == "m8_dosya":
            continue
        md = durum["moduller"].get(mod.kod, {})
        satirlar.append({
            "kod": mod.kod, "ad": mod.ad, "ikon": mod.ikon,
            "durum": md.get("durum", "bekliyor"),
            "ilerleme": md.get("ilerleme", 0),
            "bulgu": md.get("bulgu_sayisi", 0),
        })

    bulgulu = [s for s in satirlar if s["durum"] == "uyari" or s["bulgu"] > 0]
    bekleyen = [s for s in satirlar if s["durum"] == "bekliyor"]
    biten = [s for s in satirlar if s["durum"] == "tamam"]
    toplam_bulgu = sum(s["bulgu"] for s in satirlar)

    if not bulgulu and not bekleyen:
        karar = ("hazir", "Kapanışa Hazır",
                 "Tüm modüller tamamlandı ve çözülmemiş bulgu yok. Dönem kapatılabilir.")
    elif bulgulu:
        karar = ("engel", f"{len(bulgulu)} Modülde Çözülmemiş Bulgu",
                 "Aşağıdaki modüllerde bulgular giderilmeden kapanış önerilmez.")
    else:
        karar = ("eksik", f"{len(bekleyen)} Modül Henüz Başlamadı",
                 "Eksik modüllerin verisi yüklenip çalıştırılmalı.")

    # Audit trail: fis islemleri (kim-ne-zaman kayit)
    fis_kayit = depo.fis_durumlari(musteri_id, donem)
    audit = sorted(
        [{"baslik": f.get("baslik", f.get("anahtar", "")),
          "durum": f.get("durum", ""), "zaman": f.get("zaman", ""),
          "kullanici": fis_kayit.get(f.get("anahtar", ""), {}).get("kullanici", "")}
         for f in fisler if f.get("zaman")],
        key=lambda x: x["zaman"])

    return {
        "hazir": True, "satirlar": satirlar, "karar": karar,
        "biten": len(biten), "toplam": len(satirlar),
        "toplam_bulgu": toplam_bulgu, "genel_ilerleme": durum.get("genel_ilerleme", 0),
        "audit": audit, "bulgulu": bulgulu, "bekleyen": bekleyen,
        "son_tarih": durum.get("son_tarih"),
    }


# --------------------------------------------------------------------------- #
def _baslik():
    return f"""
    <div class="panel-header">
      <div class="panel-title"><h2><i class="fa-solid fa-folder-tree"></i> {AD}</h2>
      <p>{ACIKLAMA}</p></div>
      <div class="panel-header-icon"><i class="fa-solid fa-folder-tree"></i></div>
    </div>"""


KARAR_RENK = {"hazir": "emerald", "engel": "rose", "eksik": "gold"}
KARAR_IKON = {"hazir": "fa-circle-check", "engel": "fa-circle-xmark", "eksik": "fa-hourglass"}
FIS_ET = {"taslak": ("Taslak", "neutral"), "onaylandi": ("Onaylandı", "success"),
          "gonderildi": ("ERP'ye Gönderildi", "success"), "reddedildi": ("Reddedildi", "err")}


def _kontrol_tablosu(satirlar):
    sat = ""
    for s in satirlar:
        et, rozet, ikon = DURUM_ET.get(s["durum"], DURUM_ET["bekliyor"])
        bulgu_h = (f'<span style="color:var(--accent-rose)">{s["bulgu"]}</span>'
                   if s["bulgu"] else "—")
        sat += (f'<tr><td><i class="fa-solid {s["ikon"]}" style="color:var(--accent-cyan);width:18px"></i> {s["ad"]}</td>'
                f'<td style="text-align:center"><span class="badge {rozet}"><i class="fa-solid {ikon}"></i> {et}</span></td>'
                f'<td style="text-align:center">{s["ilerleme"]}%</td>'
                f'<td style="text-align:center">{bulgu_h}</td></tr>')
    return (f'<div style="overflow-x:auto"><table>'
            f'<tr><th>Modül</th><th style="text-align:center">Durum</th>'
            f'<th style="text-align:center">İlerleme</th><th style="text-align:center">Bulgu</th></tr>'
            f'{sat}</table></div>')


def _audit_listesi(audit):
    if not audit:
        return ('<div class="notif-pill"><div class="circle-icon-badge"></div>'
                '<span>Henüz onay/gönderme işlemi kaydı yok. Fiş Üretici sekmesinde fişler '
                'onaylanıp ERP\'ye gönderildikçe izleri burada zaman damgasıyla görünür.</span></div>')
    sat = ""
    for a in audit:
        et, rozet = FIS_ET.get(a["durum"], (a["durum"], "neutral"))
        kul = a.get("kullanici") or "—"
        sat += (f'<tr><td style="white-space:nowrap;color:var(--text-muted);font-size:12px">{a["zaman"]}</td>'
                f'<td>{a["baslik"]}</td>'
                f'<td><i class="fa-solid fa-user" style="color:var(--accent-cyan);font-size:11px"></i> {kul}</td>'
                f'<td><span class="badge {rozet}">{et}</span></td></tr>')
    return (f'<div style="overflow-x:auto"><table>'
            f'<tr><th>Zaman</th><th>İşlem / Fiş</th><th>Kullanıcı</th><th>Durum</th></tr>{sat}</table></div>')


def panel_html(sonuc):
    ust = _baslik()
    if not sonuc.get("hazir"):
        return ust
    k = sonuc["karar"]
    renk = KARAR_RENK.get(k[0], "gold")
    ikon = KARAR_IKON.get(k[0], "fa-hourglass")

    verdict = f"""
    <div class="notif-pill" style="margin-bottom:16px;border:1px solid var(--accent-{renk});">
      <div class="circle-icon-badge" style="background:var(--accent-{renk})"></div>
      <span><span class="badge {'success' if k[0]=='hazir' else ('err' if k[0]=='engel' else 'warn')}">
      <i class="fa-solid {ikon}"></i> {k[1]}</span> {k[2]}</span>
    </div>"""

    stat = f"""
    <div class="stats-grid" style="margin-bottom:8px;">
      <div class="stat-card"><div class="stat-header"><span>Genel İlerleme</span><i class="fa-solid fa-gauge-high" style="color:var(--accent-cyan)"></i></div><div class="stat-val">{sonuc['genel_ilerleme']}%</div></div>
      <div class="stat-card emerald"><div class="stat-header"><span>Biten Modül</span><i class="fa-solid fa-circle-check" style="color:var(--accent-emerald)"></i></div><div class="stat-val">{sonuc['biten']}/{sonuc['toplam']}</div></div>
      <div class="stat-card rose"><div class="stat-header"><span>Toplam Bulgu</span><i class="fa-solid fa-triangle-exclamation" style="color:var(--accent-rose)"></i></div><div class="stat-val">{sonuc['toplam_bulgu']}</div></div>
      <div class="stat-card gold"><div class="stat-header"><span>Audit Kaydı</span><i class="fa-solid fa-clock-rotate-left" style="color:var(--accent-gold)"></i></div><div class="stat-val">{len(sonuc['audit'])}</div></div>
    </div>"""

    btn = ('<div style="margin:18px 0;"><button class="btn" '
           'onclick="window.open(\'/kapanis_rapor\'+location.search,\'_blank\')">'
           '<i class="fa-solid fa-file-pdf"></i> Kapanış Raporunu Aç (Yazdır / PDF)</button></div>')

    h_kontrol = '<h3 style="font-size:17px;margin:18px 0 12px;"><i class="fa-solid fa-list-check" style="color:var(--accent-cyan)"></i> Kapanış Kontrol Listesi</h3>'
    h_audit = '<h3 style="font-size:17px;margin:24px 0 12px;"><i class="fa-solid fa-clock-rotate-left" style="color:var(--accent-gold)"></i> Audit Trail (Onay / Gönderme İzi)</h3>'

    return (ust + verdict + stat + btn + h_kontrol + _kontrol_tablosu(sonuc["satirlar"])
            + h_audit + _audit_listesi(sonuc["audit"]))


# --------------------------------------------------------------------------- #
# AYRI SAYFA: KAPANIS RAPORU
# --------------------------------------------------------------------------- #
def kapanis_rapor_govde(sonuc):
    if not sonuc.get("hazir"):
        return "<p>Rapor üretilemedi.</p>"
    k = sonuc["karar"]
    renk = KARAR_RENK.get(k[0], "gold")
    ikon = KARAR_IKON.get(k[0], "fa-hourglass")
    verdict = (f'<div class="notif-pill" style="margin-bottom:16px;border:1px solid var(--accent-{renk});">'
               f'<div class="circle-icon-badge" style="background:var(--accent-{renk})"></div>'
               f'<span><strong>{k[1]}</strong> — {k[2]}</span></div>')
    ozet = (f'<p style="color:var(--text-muted)">Genel ilerleme <strong>{sonuc["genel_ilerleme"]}%</strong> · '
            f'Biten modül <strong>{sonuc["biten"]}/{sonuc["toplam"]}</strong> · '
            f'Toplam bulgu <strong>{sonuc["toplam_bulgu"]}</strong>'
            + (f' · Hedef kapanış <strong>{sonuc["son_tarih"]}</strong>' if sonuc.get("son_tarih") else "")
            + '</p>')
    return f"""
    <h2><i class="fa-solid fa-folder-tree"></i> Dönem Kapanış Raporu</h2>
    {ozet}{verdict}
    <h3 style="margin-top:20px"><i class="fa-solid fa-list-check"></i> Kapanış Kontrol Listesi</h3>
    {_kontrol_tablosu(sonuc['satirlar'])}
    <h3 style="margin-top:22px"><i class="fa-solid fa-clock-rotate-left"></i> Audit Trail (Onay / Gönderme İzi)</h3>
    {_audit_listesi(sonuc['audit'])}
    <p style="margin-top:18px;font-size:12px;color:var(--text-muted)">
      Bu rapor, kapanış modüllerinin son çalıştırma sonuçlarını birleştirir. Tüm fiş onayları
      ve ERP gönderimleri kullanıcı onayıyla yapılmıştır; otomatik kayıt yoktur.</p>
    """


kaydet(Modul("m8_dosya", AD, "fa-folder-tree", 12, calistir, panel_html))
